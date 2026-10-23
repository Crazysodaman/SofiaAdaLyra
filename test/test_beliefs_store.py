"""Tests for the canonical conviction store and its owner-gated service.

The store is an append-only revision log with compare-and-swap protection;
the service is the only production writer and only the authenticated owner
principal may modify held positions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sofia.platform.application.beliefs import BeliefsService
from sofia.core.beliefs.model import (
    BeliefChangeKind,
    BeliefHolder,
    BeliefRecord,
    BeliefStance,
    BeliefVisibility,
)
from sofia.core.beliefs.store import ConvictionStore, BeliefConcurrencyError
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import local_sparks_principal
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

EVIDENCE = ("memory:session-2026-01-02", "conversation:turn-15")
COUNTER_EVIDENCE = ("conversation:turn-99",)


def aware(year: int = 2026, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def guest_principal() -> PrincipalContext:
    return PrincipalContext(
        principal_id="person:guest",
        audience_id="local:guest",
        audience_kind=AudienceKind.PRIVATE,
        display_name="Guest",
    )


@pytest.fixture()
def sofia_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(db_path)
    return db_path


@pytest.fixture()
def store(sofia_db: Path) -> ConvictionStore:
    return ConvictionStore(sofia_db)


@pytest.fixture()
def service(store: ConvictionStore) -> BeliefsService:
    return BeliefsService(store)


def _origin_payload(**overrides) -> dict:
    payload = {
        "topic": "rust over python",
        "statement": "Prefer Rust for new systems work.",
        "stance": BeliefStance.SUPPORT,
        "confidence": 0.8,
        "reason": "Documented migration outcomes.",
        "evidence_refs": EVIDENCE,
        "counterevidence_refs": (),
        "visibility": BeliefVisibility.OWNER_AUDIENCE_ONLY,
        "change_kind": BeliefChangeKind.ORIGIN,
        "now": aware(),
    }
    payload.update(overrides)
    return payload


def _record_payload(**overrides) -> dict:
    payload = dict(_origin_payload())
    payload["recorded_at"] = payload.pop("now")
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------- store level


def test_hold_creates_origin_and_readback(store: ConvictionStore) -> None:
    record = store.hold(
        holder=BeliefHolder.SOFIA,
        audience_id="local:text",
        expected_revision=None,
        **_origin_payload(),
    )
    assert record.revision == 1
    assert record.change_kind is BeliefChangeKind.ORIGIN
    assert record.recorded_at == aware()
    assert record.conviction_id.startswith("conviction:")
    current = store.current(
        holder=BeliefHolder.SOFIA,
        topic=record.topic,
        audience_id="local:text",
    )
    assert current == record
    by_id = store.by_conviction_id(record.conviction_id)
    assert by_id == record


def test_duplicate_natural_key_origin_is_rejected(store: ConvictionStore) -> None:
    store.hold(
        holder=BeliefHolder.SOFIA,
        audience_id="local:text",
        expected_revision=None,
        **_origin_payload(),
    )
    with pytest.raises(BeliefConcurrencyError):
        store.hold(
            holder=BeliefHolder.SOFIA,
            audience_id="local:text",
            expected_revision=None,
            **_origin_payload(statement="A second origin attempt."),
        )


def test_cas_revision_requires_matching_expected_revision(
    store: ConvictionStore,
) -> None:
    origin = store.hold(
        holder=BeliefHolder.SOFIA,
        audience_id="local:text",
        expected_revision=None,
        **_origin_payload(),
    )
    revised = store.hold(
        holder=BeliefHolder.SOFIA,
        audience_id="local:text",
        expected_revision=origin.revision,
        **_origin_payload(
            statement="Prefer Rust for new systems work.",
            stance=BeliefStance.UNCERTAIN,
            confidence=0.55,
            reason="New benchmark evidence arrived.",
            change_kind=BeliefChangeKind.RECONSIDER,
            now=aware(2026, 1, 3),
        ),
    )
    assert revised.revision == 2
    assert revised.change_kind is BeliefChangeKind.RECONSIDER
    history = store.history(origin.conviction_id)
    assert [record.revision for record in history] == [1, 2]
    assert history[0] == origin
    with pytest.raises(BeliefConcurrencyError):
        store.hold(
            holder=BeliefHolder.SOFIA,
            audience_id="local:text",
            expected_revision=1,
            **_origin_payload(change_kind=BeliefChangeKind.REVISE),
        )


def test_audience_scoping_keeps_records_separate(store: ConvictionStore) -> None:
    first = store.hold(
        holder=BeliefHolder.OWNER,
        audience_id="local:text",
        expected_revision=None,
        **_origin_payload(),
    )
    second = store.hold(
        holder=BeliefHolder.OWNER,
        audience_id="discord:dm:7",
        expected_revision=None,
        **_origin_payload(),
    )
    assert first.conviction_id != second.conviction_id
    assert store.current(
        holder=BeliefHolder.OWNER,
        topic=first.topic,
        audience_id="local:text",
    ).revision == 1
    assert store.current(
        holder=BeliefHolder.OWNER,
        topic=first.topic,
        audience_id="discord:dm:7",
    ).conviction_id == second.conviction_id


def test_reopen_continuity(sofia_db: Path) -> None:
    first = ConvictionStore(sofia_db)
    origin = first.hold(
        holder=BeliefHolder.SOFIA,
        audience_id="local:text",
        expected_revision=None,
        **_origin_payload(),
    )
    second = ConvictionStore(sofia_db)
    current = second.current(
        holder=BeliefHolder.SOFIA,
        topic=origin.topic,
        audience_id="local:text",
    )
    assert current == origin


def test_retrieval_respects_audience_isolation(store: ConvictionStore) -> None:
    store.hold(
        holder=BeliefHolder.SOFIA,
        audience_id="local:text",
        expected_revision=None,
        **_origin_payload(),
    )
    store.hold(
        holder=BeliefHolder.SOFIA,
        audience_id="local:text",
        expected_revision=None,
        **_origin_payload(
            topic="open source licensing",
            statement="Prefer permissive licenses.",
            visibility=BeliefVisibility.DISCLOSURE_SCOPED,
        ),
    )
    owner_matches = store.retrieve_relevant(
        query_text="what do you believe about rust",
        audience_id="local:text",
        owner_audience_id="local:text",
        minimum_score=0,
    )
    assert {match.record.topic for match in owner_matches} == {
        "rust over python",
        "open source licensing",
    }
    other_matches = store.retrieve_relevant(
        query_text="what do you believe about rust",
        audience_id="local:guest",
        owner_audience_id=None,
        minimum_score=0,
    )
    assert [match.record.topic for match in other_matches] == [
        "open source licensing"
    ]


def test_withdrawn_convictions_are_not_projected(store: ConvictionStore) -> None:
    origin = store.hold(
        holder=BeliefHolder.SOFIA,
        audience_id="local:text",
        expected_revision=None,
        **_origin_payload(),
    )
    store.hold(
        holder=BeliefHolder.SOFIA,
        audience_id="local:text",
        expected_revision=origin.revision,
        **_origin_payload(
            statement="Prefer Rust for new systems work.",
            stance=BeliefStance.WITHDRAWN,
            reason="The owner asked to drop the claim.",
            evidence_refs=EVIDENCE,
            counterevidence_refs=COUNTER_EVIDENCE,
            change_kind=BeliefChangeKind.RETRACT,
            now=aware(2026, 1, 5),
        ),
    )
    assert store.retrieve_relevant(
        query_text="rust systems work",
        audience_id="local:text",
        owner_audience_id="local:text",
    ) == ()
    current = store.current(
        holder=BeliefHolder.SOFIA,
        topic=origin.topic,
        audience_id="local:text",
    )
    assert current.stance is BeliefStance.WITHDRAWN


def test_retrieval_requires_bounded_input(store: ConvictionStore) -> None:
    with pytest.raises(ValueError):
        store.retrieve_relevant(
            query_text="   ",
            audience_id="local:text",
            owner_audience_id=None,
        )
    with pytest.raises(ValueError):
        store.retrieve_relevant(
            query_text="rust",
            audience_id="local:text",
            owner_audience_id=None,
            limit=0,
        )
    with pytest.raises(ValueError):
        store.retrieve_relevant(
            query_text="rust",
            audience_id="local:text",
            owner_audience_id=None,
            limit=26,
        )


def test_reconsideration_schedule_cycle(store: ConvictionStore) -> None:
    origin = store.hold(
        holder=BeliefHolder.SOFIA,
        audience_id="local:text",
        expected_revision=None,
        **_origin_payload(),
    )
    with pytest.raises(BeliefConcurrencyError):
        store.schedule_reconsideration(
            origin.conviction_id,
            due_at=aware(2026, 2, 1),
            note="Recheck after benchmark results.",
            expected_revision=2,
        )
    store.schedule_reconsideration(
        origin.conviction_id,
        due_at=aware(2026, 2, 1),
        note="Recheck after benchmark results.",
        expected_revision=origin.revision,
    )
    assert store.due_reconsiderations(now=aware(2026, 1, 31)) == ()
    due = store.due_reconsiderations(now=aware(2026, 2, 1))
    assert len(due) == 1
    assert due[0].conviction_id == origin.conviction_id
    assert due[0].note == "Recheck after benchmark results."
    store.clear_reconsideration(origin.conviction_id)
    assert store.due_reconsiderations(now=aware(2026, 2, 2)) == ()


def test_naive_timestamps_are_rejected(store: ConvictionStore) -> None:
    with pytest.raises(ValueError):
        store.hold(
            holder=BeliefHolder.SOFIA,
            audience_id="local:text",
            expected_revision=None,
            **_origin_payload(now=datetime(2026, 1, 1)),
        )


def test_first_revision_must_be_origin() -> None:
    with pytest.raises(ValueError):
        BeliefRecord(
            conviction_id="conviction:test-1",
            revision=1,
            holder=BeliefHolder.SOFIA,
            audience_id="local:text",
            **_record_payload(change_kind=BeliefChangeKind.REVISE),
        )
    with pytest.raises(ValueError):
        BeliefRecord(
            conviction_id="conviction:test-2",
            revision=2,
            holder=BeliefHolder.SOFIA,
            audience_id="local:text",
            **_record_payload(),
        )


# ------------------------------------------------------------- service level


def test_service_requires_authenticated_owner(service: BeliefsService) -> None:
    owner = local_sparks_principal()
    with pytest.raises(PermissionError):
        service.record_sofia_conviction(
            principal=guest_principal(),
            statement=_origin_payload()["statement"],
            confidence=_origin_payload()["confidence"],
            reason=_origin_payload()["reason"],
            evidence_refs=EVIDENCE,
            now=aware(),
            topic="rust over python",
            stance=BeliefStance.SUPPORT,
            counterevidence_refs=(),
            visibility=BeliefVisibility.OWNER_AUDIENCE_ONLY,
            expected_revision=None,
        )
    with pytest.raises(TypeError):
        service.record_sofia_conviction(
            principal=None,
            statement="x",
            confidence=0.5,
            reason="y",
            evidence_refs=EVIDENCE,
            now=aware(),
            topic="topic",
            stance=BeliefStance.SUPPORT,
            counterevidence_refs=(),
            visibility=BeliefVisibility.OWNER_AUDIENCE_ONLY,
            expected_revision=None,
        )
    assert service.store.current(
        holder=BeliefHolder.SOFIA,
        topic="rust over python",
        audience_id=owner.audience_id,
    ) is None


def test_owner_positions_are_attributed_not_absorbed(
    store: ConvictionStore,
    service: BeliefsService,
) -> None:
    principal = local_sparks_principal()
    owner_record = service.record_owner_position(
        principal=principal,
        statement="I want technical precision, not small talk.",
        topic="conversation style",
        stance=BeliefStance.SUPPORT,
        confidence=0.9,
        reason="Stated in a planning conversation.",
        evidence_refs=EVIDENCE,
        expected_revision=None,
        now=aware(),
    )
    sofia_record = service.record_sofia_conviction(
        principal=principal,
        statement="Prefer Rust for new systems work.",
        topic="rust over python",
        stance=BeliefStance.SUPPORT,
        confidence=0.8,
        reason="Documented migration outcomes.",
        evidence_refs=EVIDENCE,
        visibility=BeliefVisibility.OWNER_AUDIENCE_ONLY,
        expected_revision=None,
        now=aware(),
    )
    assert owner_record.holder is BeliefHolder.OWNER
    assert owner_record.recorded_at == aware()
    assert sofia_record.holder is BeliefHolder.SOFIA
    assert owner_record.visibility is BeliefVisibility.OWNER_AUDIENCE_ONLY
    assert sofia_record.statement != owner_record.statement
    assert store.current(
        holder=BeliefHolder.OWNER,
        topic="conversation style",
        audience_id=principal.audience_id,
    ).statement.startswith("I want technical precision")
    assert store.current(
        holder=BeliefHolder.SOFIA,
        topic="conversation style",
        audience_id=principal.audience_id,
    ) is None


def test_reconsider_requires_counterevidence(service: BeliefsService) -> None:
    principal = local_sparks_principal()
    service.record_sofia_conviction(
        principal=principal,
        statement="Prefer Rust for new systems work.",
        topic="rust over python",
        stance=BeliefStance.SUPPORT,
        confidence=0.8,
        reason="Documented migration outcomes.",
        evidence_refs=EVIDENCE,
        expected_revision=None,
        now=aware(),
    )
    with pytest.raises(ValueError):
        service.reconsider(
            principal=principal,
            statement="Maybe Python still fits.",
            topic="rust over python",
            stance=BeliefStance.UNCERTAIN,
            confidence=0.5,
            reason="Benchmark results were mixed.",
            evidence_refs=EVIDENCE,
            counterevidence_refs=(),
            expected_revision=1,
            now=aware(2026, 1, 4),
        )
    revised = service.reconsider(
        principal=principal,
        statement="Maybe Python still fits.",
        topic="rust over python",
        stance=BeliefStance.UNCERTAIN,
        confidence=0.5,
        reason="Benchmark results were mixed.",
        evidence_refs=EVIDENCE,
        counterevidence_refs=COUNTER_EVIDENCE,
        expected_revision=1,
        now=aware(2026, 1, 4),
    )
    assert revised.change_kind is BeliefChangeKind.RECONSIDER
    assert revised.revision == 2
    assert revised.counterevidence_refs == COUNTER_EVIDENCE


def test_withdraw_entry_point(service: BeliefsService) -> None:
    principal = local_sparks_principal()
    origin = service.record_sofia_conviction(
        principal=principal,
        statement="Prefer Rust for new systems work.",
        topic="rust over python",
        stance=BeliefStance.SUPPORT,
        confidence=0.8,
        reason="Documented migration outcomes.",
        evidence_refs=EVIDENCE,
        expected_revision=None,
        now=aware(),
    )
    with pytest.raises(ValueError):
        service.withdraw(
            principal=principal,
            topic="unknown topic",
            reason="Superseded.",
            evidence_refs=COUNTER_EVIDENCE,
            expected_revision=1,
            now=aware(2026, 1, 6),
        )
    withdrawn = service.withdraw(
        principal=principal,
        topic=origin.topic,
        reason="The owner asked to drop the claim.",
        evidence_refs=COUNTER_EVIDENCE,
        expected_revision=origin.revision,
        now=aware(2026, 1, 6),
    )
    assert withdrawn.change_kind is BeliefChangeKind.RETRACT
    assert withdrawn.stance is BeliefStance.WITHDRAWN
    assert withdrawn.counterevidence_refs == COUNTER_EVIDENCE


def test_evidence_verifier_gates_refs(sofia_db: Path) -> None:
    principal = local_sparks_principal()

    def verifier(ref: str) -> bool:
        return ref.startswith("memory:")

    service = BeliefsService(
        ConvictionStore(sofia_db),
        evidence_verifier=verifier,
    )
    with pytest.raises(ValueError):
        service.record_sofia_conviction(
            principal=principal,
            statement="Prefer Rust for new systems work.",
            topic="rust over python",
            stance=BeliefStance.SUPPORT,
            confidence=0.8,
            reason="Documented migration outcomes.",
            evidence_refs=("conversation:turn-15",),
            expected_revision=None,
            now=aware(),
        )
    accepted = service.record_sofia_conviction(
        principal=principal,
        statement="Prefer Rust for new systems work.",
        topic="rust over python",
        stance=BeliefStance.SUPPORT,
        confidence=0.8,
        reason="Documented migration outcomes.",
        evidence_refs=("memory:session-2026-01-02",),
        expected_revision=None,
        now=aware(),
    )
    assert accepted.evidence_refs == ("memory:session-2026-01-02",)


def test_working_context_respects_listener_audience(
    sofia_db: Path,
) -> None:
    owner = local_sparks_principal()
    service = BeliefsService(ConvictionStore(sofia_db))
    service.record_owner_position(
        principal=owner,
        statement="I want technical precision, not small talk.",
        topic="conversation style",
        stance=BeliefStance.SUPPORT,
        confidence=0.9,
        reason="Stated in a planning conversation.",
        evidence_refs=EVIDENCE,
        expected_revision=None,
        now=aware(),
    )
    owner_context = service.working_context(
        query_text="what is my conversation style",
        audience_id=owner.audience_id,
        owner_audience_id=owner.audience_id,
    )
    assert len(owner_context) == 1
    guest_context = service.working_context(
        query_text="what is my conversation style",
        audience_id="local:guest",
        owner_audience_id=None,
    )
    assert guest_context == ()


def test_schedule_reconsideration_round_trip(service: BeliefsService) -> None:
    principal = local_sparks_principal()
    origin = service.record_sofia_conviction(
        principal=principal,
        statement="Prefer Rust for new systems work.",
        topic="rust over python",
        stance=BeliefStance.SUPPORT,
        confidence=0.8,
        reason="Documented migration outcomes.",
        evidence_refs=EVIDENCE,
        expected_revision=None,
        now=aware(),
    )
    scheduled = service.schedule_reconsideration(
        principal=principal,
        topic=origin.topic,
        due_at=aware() + timedelta(days=14),
        note="Recheck after benchmark results.",
    )
    assert scheduled.revision == 1
    due = service.due_reconsiderations(
        now=aware() + timedelta(days=15),
    )
    assert len(due) == 1
    assert due[0].conviction_id == origin.conviction_id
