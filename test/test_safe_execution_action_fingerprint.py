"""CA-1904: exact, bounded, one-use execution authority at common SAFE boundary.

Authored for the deferred test gate. No live approval or execution here.
"""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)


NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


def _approval(parameters, *, actor="Sparks", identifier="action-specific-1"):
    return ExecutionApproval(
        approval_id=identifier, capability="ops.migration.execute",
        request_fingerprint=execution_fingerprint(
            "ops.migration.execute", parameters,
        ),
        approved_by=actor, approved_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
    )


def test_nonowner_approval_denied_before_record_or_capability_consumption(tmp_path):
    with pytest.raises(PermissionError, match="owner"):
        _approval({"source_host": "Venus"}, actor="model:self")
    state = tmp_path / "sofia.db"
    verifier = ExecutionApprovalVerifier(state)
    active = _approval({"source_host": "Venus"})
    verifier.record(active)
    # Legacy corruption or an older build's forged row must never be
    # returned as a valid approval, even if its exact digest still matches.
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_execution_approval SET approved_by='model:self' "
            "WHERE approval_id=?", (active.approval_id,),
        )
    with pytest.raises(PermissionError, match="owner"):
        verifier.consume(
            approval_id=active.approval_id,
            capability=active.capability,
            parameters={"source_host": "Venus"},
            now=NOW + timedelta(seconds=1),
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_unsafe_non_json_finite_approval_values_are_rejected(bad):
    with pytest.raises(ValueError):
        execution_fingerprint("ops.migration.execute", {"resource": bad})


def test_large_or_unbounded_execution_request_is_never_fingerprinted():
    with pytest.raises(ValueError, match="64-KiB"):
        execution_fingerprint(
            "ops.migration.execute", {"payload": "s" * 65_000},
        )


def test_exact_target_and_effect_bound_approval_only_consumes_once(tmp_path):
    state = tmp_path / "sofia.db"
    verifier = ExecutionApprovalVerifier(state)
    approved = {
        "source_host": "Venus", "target_host": "Artemis",
        "expected_effect": "stop-old-owner-and-transfer",
        "lease_epoch": 4,
    }
    approval = _approval(approved)
    verifier.record(approval)
    with pytest.raises(PermissionError, match="parameters"):
        verifier.consume(
            approval_id=approval.approval_id, capability=approval.capability,
            parameters={**approved, "target_host": "Terra"},
            now=NOW + timedelta(seconds=2),
        )
    assert verifier.consume(
        approval_id=approval.approval_id, capability=approval.capability,
        parameters=approved, now=NOW + timedelta(seconds=3),
    ) == approval
    with pytest.raises(PermissionError, match="already consumed"):
        verifier.consume(
            approval_id=approval.approval_id, capability=approval.capability,
            parameters=approved, now=NOW + timedelta(seconds=4),
        )
