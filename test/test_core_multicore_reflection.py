from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.reflection import (
    MAX_ROUTINE_CANDIDATES,
    MulticoreReflectionService,
    ReflectionCandidate,
    ReflectionConflictError,
    ReflectionRateLimited,
    ReflectionStateError,
    ReflectionStatus,
)

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def _candidate(owner, *, index: int = 0, content: str | None = None, **overrides):
    values = {
        "candidate_id": uuid4(),
        "owner_core_id": owner,
        "content": content or f"reflection candidate {index}",
        "evidence": (uuid4(),),
        "significance": 5,
        "kind": "routine",
    }
    values.update(overrides)
    return ReflectionCandidate(**values)


def test_empty_reflection_is_skipped_without_consuming_rate_limit(canonical_state_path):
    owner = uuid4()
    service = MulticoreReflectionService(canonical_state_path, owner)
    assert service.create_batch(owner, [], batch_key="empty", now=NOW) is None

    batch = service.create_batch(
        owner,
        [_candidate(owner)],
        batch_key="first-real-batch",
        now=NOW,
    )
    assert batch is not None
    assert batch.status is ReflectionStatus.PENDING
    assert batch.total_candidates == 1


def test_reflection_caps_candidates_and_token_budget(canonical_state_path):
    owner = uuid4()
    service = MulticoreReflectionService(canonical_state_path, owner)
    batch = service.create_batch(
        owner,
        [_candidate(owner, index=index) for index in range(30)],
        batch_key="bounded",
        now=NOW,
    )
    assert batch is not None
    assert batch.total_candidates == MAX_ROUTINE_CANDIDATES

    other_owner = uuid4()
    other_service = MulticoreReflectionService(canonical_state_path, other_owner)
    long_batch = other_service.create_batch(
        other_owner,
        [
            _candidate(other_owner, content="x" * 4000),
            _candidate(other_owner, content="y" * 4000),
        ],
        batch_key="token-budget",
        now=NOW,
        token_budget=1600,
    )
    assert long_batch is not None
    assert long_batch.total_candidates == 1
    assert long_batch.token_count <= 1600
    assert long_batch.token_budget == 1600


def test_reflection_batches_are_owner_isolated(canonical_state_path):
    mack = uuid4()
    nova = uuid4()
    mack_service = MulticoreReflectionService(canonical_state_path, mack)
    nova_service = MulticoreReflectionService(canonical_state_path, nova)

    with pytest.raises(PermissionError):
        mack_service.create_batch(
            mack,
            [_candidate(nova)],
            batch_key="cross-owner",
            now=NOW,
        )

    batch = mack_service.create_batch(
        mack,
        [_candidate(mack)],
        batch_key="mack-only",
        now=NOW,
    )
    assert batch is not None
    assert nova_service.get_batch(batch.batch_id) is None
    with pytest.raises(KeyError):
        nova_service.run(batch.batch_id, now=NOW)


def test_reflection_batch_creation_is_idempotent_and_conflict_aware(canonical_state_path):
    owner = uuid4()
    service = MulticoreReflectionService(canonical_state_path, owner)
    candidates = [_candidate(owner, index=0), _candidate(owner, index=1)]

    first = service.create_batch(owner, candidates, batch_key="daily", now=NOW)
    second = service.create_batch(owner, candidates, batch_key="daily", now=NOW)
    assert first is not None and second is not None
    assert first.batch_id == second.batch_id

    with pytest.raises(ReflectionConflictError):
        service.create_batch(
            owner,
            [_candidate(owner, content="different input")],
            batch_key="daily",
            now=NOW,
        )


def test_reflection_is_at_most_once_per_core_per_24_hours(canonical_state_path):
    owner = uuid4()
    service = MulticoreReflectionService(canonical_state_path, owner)
    service.create_batch(owner, [_candidate(owner)], batch_key="window-1", now=NOW)
    with pytest.raises(ReflectionRateLimited):
        service.create_batch(
            owner,
            [_candidate(owner)],
            batch_key="window-2",
            now=NOW + timedelta(hours=23),
        )
    allowed = service.create_batch(
        owner,
        [_candidate(owner)],
        batch_key="window-3",
        now=NOW + timedelta(hours=24, seconds=1),
    )
    assert allowed is not None


def test_reflection_checkpoint_cancel_resume_and_idempotent_completion(canonical_state_path):
    owner = uuid4()
    service = MulticoreReflectionService(canonical_state_path, owner)
    candidates = [_candidate(owner, index=index) for index in range(5)]
    batch = service.create_batch(owner, candidates, batch_key="resume-me", now=NOW)
    assert batch is not None

    running = service.run(
        batch.batch_id,
        now=NOW + timedelta(minutes=1),
        max_steps=2,
    )
    assert running.status is ReflectionStatus.RUNNING
    assert running.checkpoint == 2
    assert len(service.outputs(batch.batch_id)) == 2

    cancelled = service.cancel(batch.batch_id, now=NOW + timedelta(minutes=2))
    assert cancelled.status is ReflectionStatus.CANCELLED
    assert service.run(batch.batch_id, now=NOW + timedelta(minutes=3)).status is (
        ReflectionStatus.CANCELLED
    )

    resumed = service.resume(batch.batch_id, now=NOW + timedelta(minutes=4))
    assert resumed.status is ReflectionStatus.COMPLETED
    assert resumed.checkpoint == 5
    assert len(service.outputs(batch.batch_id)) == 5

    again = service.run(batch.batch_id, now=NOW + timedelta(minutes=5))
    assert again.status is ReflectionStatus.COMPLETED
    assert len(service.outputs(batch.batch_id)) == 5

    actions = [event.action for event in service.audit(batch.batch_id)]
    assert actions.count("candidate_reflected") == 5
    assert "batch_cancelled" in actions
    assert "batch_resumed" in actions
    assert actions[-1] == "batch_completed"

    with pytest.raises(ReflectionStateError):
        service.cancel(batch.batch_id, now=NOW + timedelta(minutes=6))


def test_reflection_cancel_after_is_durable_and_resumable(canonical_state_path):
    owner = uuid4()
    service = MulticoreReflectionService(canonical_state_path, owner)
    batch = service.create_batch(
        owner,
        [_candidate(owner, index=index) for index in range(3)],
        batch_key="cancel-after",
        now=NOW,
    )
    assert batch is not None
    cancelled = service.run(
        batch.batch_id,
        now=NOW + timedelta(minutes=1),
        cancel_after=1,
    )
    assert cancelled.status is ReflectionStatus.CANCELLED
    assert cancelled.checkpoint == 1
    completed = service.resume(batch.batch_id, now=NOW + timedelta(minutes=2))
    assert completed.status is ReflectionStatus.COMPLETED
    assert completed.checkpoint == 3


def test_important_corrections_require_confirmation_and_never_grant_authority(
    canonical_state_path,
):
    owner = uuid4()
    service = MulticoreReflectionService(canonical_state_path, owner)
    important = _candidate(owner, kind="correction", significance=9, content="Correct a belief")
    routine = _candidate(owner, significance=4)
    batch = service.create_batch(
        owner,
        [important, routine],
        batch_key="correction-window",
        now=NOW,
    )
    assert batch is not None
    assert batch.requires_confirmation is True
    assert str(important.candidate_id) in (batch.confirmation_prompt or "")
    assert batch.grants_authority is False
    assert batch.modifies_protected_identity is False
    assert batch.modifies_protected_memory is False

    completed = service.run(batch.batch_id, now=NOW + timedelta(minutes=1))
    assert completed.status is ReflectionStatus.COMPLETED
    outputs = {output.candidate_id: output for output in service.outputs(batch.batch_id)}
    assert outputs[important.candidate_id].requires_confirmation is True
    assert outputs[routine.candidate_id].requires_confirmation is False
    assert all(output.grants_authority is False for output in outputs.values())


def test_reflection_audit_attribution_is_explicit_and_denies_authority(canonical_state_path):
    owner = uuid4()
    service = MulticoreReflectionService(canonical_state_path, owner)
    batch = service.create_batch(
        owner,
        [_candidate(owner)],
        batch_key="audited",
        now=NOW,
        actor="reflection:window",
    )
    assert batch is not None
    service.run(
        batch.batch_id,
        now=NOW + timedelta(minutes=1),
        actor="reflection:window",
    )
    events = service.audit(batch.batch_id)
    assert events
    assert all(event.actor == "reflection:window" for event in events)
    assert all(event.grants_authority is False for event in events)
    assert all(event.owner_core_id == owner for event in events)
    created = events[0]
    assert created.action == "batch_created"
    assert created.detail["granted_authority"] is False
