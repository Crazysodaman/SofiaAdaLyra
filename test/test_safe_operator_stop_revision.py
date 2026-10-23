"""One-use owner approval cannot clear a newer emergency stop.

Regression source only. Tests deliberately deferred to the owner final gate.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from test.owner_auth_fixture import record_verified_owner_approval


NOW = datetime(2026, 10, 11, 16, tzinfo=timezone.utc)


def test_new_operator_pause_invalidates_signed_but_unconsumed_old_resume(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    stop = OperatorStopStore(state)
    stop.set(
        active=True, updated_by="Sparks", reason="pause first",
        at=NOW,
    )
    previous = stop.current().updated_at.isoformat()
    payload = {
        "active": False, "reason": "resume optional work",
        "expected_updated_at": previous,
    }
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability="operator.stop.resume",
        request_fingerprint=execution_fingerprint(
            "operator.stop.resume", payload,
        ),
        approved_by="Sparks",
        approved_at=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(seconds=90),
    )
    approvals = ExecutionApprovalVerifier(state)
    record_verified_owner_approval(approvals, approval)

    # A second user emergency stop arrives while a signed browser prompt
    # is in flight. A stale resume must never lift the newer stop.
    stop.set(
        active=True, updated_by="Sparks", reason="pause again",
        at=NOW + timedelta(seconds=3),
    )
    with pytest.raises(PermissionError, match="changed since"):
        stop.set(
            active=False, updated_by="Sparks",
            reason="resume optional work",
            approval_id=approval.approval_id,
            expected_updated_at=previous,
            at=NOW + timedelta(seconds=4),
        )
    assert stop.current().active is True
    assert stop.current().reason == "pause again"
    assert approvals.matches_unconsumed(
        approval_id=approval.approval_id,
        capability="operator.stop.resume",
        parameters=payload,
        now=NOW + timedelta(seconds=5),
    )


def test_unapproved_resume_is_denied_without_weaker_actor_fallback(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    stop = OperatorStopStore(state)
    stop.set(active=True, updated_by="Sparks", reason="owner pause", at=NOW)
    with pytest.raises(PermissionError, match="FIDO2 approval"):
        stop.set(
            active=False, updated_by="Sparks", reason="resume",
            expected_updated_at=stop.current().updated_at.isoformat(),
            at=NOW + timedelta(seconds=1),
        )
    assert stop.current().active is True


def test_operator_resume_audit_failure_rolls_back_approval_consumption(tmp_path, monkeypatch):
    from test.owner_auth_fixture import record_verified_owner_approval

    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    stop = OperatorStopStore(state)
    stop.set(
        active=True, updated_by="Sparks",
        reason="stop before critical work", at=NOW,
    )
    revision = stop.current().updated_at.isoformat()
    exact = {
        "active": False, "reason": "resume after operator verification",
        "expected_updated_at": revision,
    }
    approval = ExecutionApproval(
        approval_id=str(uuid4()),
        capability="operator.stop.resume",
        request_fingerprint=execution_fingerprint(
            "operator.stop.resume", exact,
        ),
        approved_by="Sparks", approved_at=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=3),
    )
    approvals = ExecutionApprovalVerifier(state)
    record_verified_owner_approval(approvals, approval)

    def fail_audit(*args, **kwargs):
        raise OSError("synthetic stop audit failure")

    monkeypatch.setattr(stop.audit, "append_in_transaction", fail_audit)
    with pytest.raises(OSError, match="stop audit"):
        stop.set(
            active=False, updated_by="Sparks",
            reason="resume after operator verification",
            expected_updated_at=revision,
            approval_id=approval.approval_id,
            at=NOW + timedelta(seconds=2),
        )
    assert stop.current().active is True
    assert approvals.matches_unconsumed(
        approval_id=approval.approval_id,
        capability="operator.stop.resume",
        parameters=exact,
        now=NOW + timedelta(seconds=3),
    )


@pytest.mark.parametrize(
    "second_at",
    (NOW, NOW - timedelta(minutes=5)),
    ids=("same-clock-tick", "clock-moved-backwards"),
)
def test_repeated_operator_stop_cannot_reuse_signed_resume_revision(tmp_path, second_at):
    """A second STOP must fence an old resume even with identical/backwards clocks."""
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    stop = OperatorStopStore(state)
    stop.set(active=True, updated_by="Sparks", reason="first stop", at=NOW)
    first = stop.current().updated_at
    parameters = {
        "active": False,
        "reason": "stale resume",
        "expected_updated_at": first.isoformat(),
    }
    approval = ExecutionApproval(
        approval_id=str(uuid4()),
        capability="operator.stop.resume",
        request_fingerprint=execution_fingerprint(
            "operator.stop.resume", parameters
        ),
        approved_by="Sparks",
        approved_at=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
    )
    verifier = ExecutionApprovalVerifier(state)
    record_verified_owner_approval(verifier, approval)

    stop.set(
        active=True, updated_by="Sparks",
        reason="newer emergency stop", at=second_at,
    )
    second = stop.current()
    assert second.active and second.reason == "newer emergency stop"
    assert second.updated_at > first
    with pytest.raises(PermissionError, match="changed since"):
        stop.set(
            active=False, updated_by="Sparks", reason="stale resume",
            approval_id=approval.approval_id,
            expected_updated_at=first.isoformat(),
            at=NOW + timedelta(seconds=2),
        )
    assert stop.current() == second
    assert verifier.matches_unconsumed(
        approval_id=approval.approval_id,
        capability="operator.stop.resume",
        parameters=parameters,
        now=NOW + timedelta(seconds=3),
    )


def test_operator_stop_revisions_remain_unique_across_rapid_restart(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    first = OperatorStopStore(state)
    first.set(active=True, updated_by="Sparks", reason="first", at=NOW)
    rev1 = first.current().updated_at
    restarted = OperatorStopStore(state)
    restarted.set(active=True, updated_by="Sparks", reason="repeat", at=NOW)
    rev2 = restarted.current().updated_at
    assert rev2 > rev1
    assert OperatorStopStore(state).current().updated_at == rev2
