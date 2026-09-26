from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from sofia.evolve.revision import RevisionAdapter, RevisionApprovalVerifier
from sofia.ops.capability import OpsToolService
from sofia.run.supervisor import ManagedRuntimeBackend, ProcessState, RuntimeObservation
from sofia.runtime.control_plane import RuntimeControlPlane


NOW = datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc)


def _state(tmp_path: Path) -> Path:
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path) as db:
        db.execute(
            """
            CREATE TABLE conversation_messages (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL
            )
            """
        )
    return path


class FakeBackend(ManagedRuntimeBackend):
    def __init__(self) -> None:
        self.starts: list[int] = []
        self.stops = 0

    def observe(self) -> RuntimeObservation:
        return RuntimeObservation(ProcessState.STOPPED)

    def start(self, *, epoch: int) -> None:
        self.starts.append(epoch)

    def stop(self) -> None:
        self.stops += 1


class MemoryAdapter(RevisionAdapter):
    def read_digest(self, scope, key):
        return "0" * 64

    def validate(self, scope, key, proposed_content):
        return None

    def apply(self, scope, key, *, expected_digest, proposed_content):
        return "rollback-token"

    def rollback(self, scope, key, *, expected_current_digest, rollback_token):
        return None


class ExactVerifier(RevisionApprovalVerifier):
    def verify(self, proposal, approval, *, now):
        return True


def test_open_wires_shared_ops_run_act_state_without_enabling_activity(tmp_path: Path):
    state = _state(tmp_path)
    ops = OpsToolService(state)
    control = RuntimeControlPlane(state_path=state, ops_service=ops)

    control.open()

    assert control.opened is True
    assert control.ops_service is ops
    assert control.run_lease_store.path.resolve() == state.resolve()
    assert control.run_lifecycle_store.path.resolve() == state.resolve()
    assert control.act_outbox.path.resolve() == state.resolve()
    assert control.run_periodic_gate.policy.enabled is False


def test_default_periodic_runner_is_inert(tmp_path: Path):
    state = _state(tmp_path)
    control = RuntimeControlPlane(state_path=state)
    control.open()
    reflected: list[str] = []

    runner = control.create_periodic_runner(
        lambda: reflected.append("event-1") or "event-1"
    )
    result = runner.tick(
        now=NOW,
        source_refs=("event-1",),
    )

    assert result.status == "disabled"
    assert reflected == []


def test_delivery_and_supervisor_factories_do_not_execute_on_construction(tmp_path: Path):
    state = _state(tmp_path)
    control = RuntimeControlPlane(state_path=state)
    control.open()
    sends = []
    backend = FakeBackend()

    delivery = control.create_delivery_runner(
        lambda payload: sends.append(payload)
    )
    supervisor = control.create_supervisor(backend)

    assert delivery.outbox is control.act_outbox
    assert supervisor.lease_store is control.run_lease_store
    assert sends == []
    assert backend.starts == []
    assert backend.stops == 0


def test_evolve_factory_requires_explicit_adapter_and_verifier(tmp_path: Path):
    state = _state(tmp_path)
    control = RuntimeControlPlane(state_path=state)
    control.open()

    executor = control.create_reviewed_revision_executor(
        adapter=MemoryAdapter(),
        verifier=ExactVerifier(),
    )

    assert executor.state_path.resolve() == state.resolve()


def test_close_revokes_runtime_control_plane_access(tmp_path: Path):
    state = _state(tmp_path)
    control = RuntimeControlPlane(state_path=state)
    control.open()

    control.close()

    assert control.opened is False
    with pytest.raises(RuntimeError):
        _ = control.act_outbox
    with pytest.raises(RuntimeError):
        _ = control.run_lease_store
    with pytest.raises(RuntimeError):
        _ = control.run_lifecycle_store



def test_control_plane_builds_disabled_run_act_scheduler(tmp_path: Path):
    state = _state(tmp_path)
    control = RuntimeControlPlane(state_path=state)
    control.open()
    sent = []

    runner = control.create_scheduled_delivery_runner(
        lambda payload: sent.append(payload),
        policy_for=lambda bound: None,
        attempt_id_for=lambda bound: "attempt-1",
    )
    result = runner.tick(now=NOW)

    assert result.status == "disabled"
    assert sent == []



def test_open_quarantines_interrupted_act_claims(tmp_path: Path):
    state = _state(tmp_path)
    with sqlite3.connect(state) as db:
        db.execute(
            "INSERT INTO conversation_messages (id, role) VALUES (?, ?)",
            ("source-recovery", "user"),
        )
    control = RuntimeControlPlane(state_path=state)
    control.open()
    journal = control.goal_journal
    journal.create_goal(
        goal_id="goal-recovery",
        source_id="source-recovery",
        title="Recovery",
        kind="question",
        priority=1,
        at=NOW,
    )
    journal.transition(
        goal_id="goal-recovery",
        transition_id="transition-recovery",
        source_id="source-recovery",
        expected_status="proposed",
        next_status="active",
        at=NOW,
    )
    queued = journal.queue_message(
        message_id="message-recovery",
        goal_id="goal-recovery",
        evidence_id="source-recovery",
        content="recovery message",
        at=NOW,
        opted_in=True,
        presence="away",
        mode="queue_only",
    )
    assert queued is not None
    control.act_outbox.bind(
        message_id="message-recovery",
        recipient_id="sparks",
        channel="test",
        destination="private",
        expires_at=NOW.replace(hour=23),
        at=NOW,
    )
    from sofia.act import DeliveryLimits, Policy
    claim = control.act_outbox.claim(
        message_id="message-recovery",
        attempt_id="attempt-recovery",
        policy=Policy(recipient_id="sparks", enabled=True, quiet_start_utc=23, quiet_end_utc=7),
        limits=DeliveryLimits(),
        now=NOW,
    )
    assert claim.status == "claimed"
    control.close()

    reopened = RuntimeControlPlane(state_path=state)
    reopened.open()

    assert reopened.recovered_act_delivery_claims == 1
    with pytest.raises(ValueError):
        reopened.act_outbox.payload(claim.claim)
