"""One-use owner approval cannot clear a newer emergency stop.

Regression source only. Tests deliberately deferred to the owner final gate.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.safe.operator_stop import OperatorStopStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite
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
