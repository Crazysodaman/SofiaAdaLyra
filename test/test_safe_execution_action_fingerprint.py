"""CA-1904: exact, bounded, one-use execution authority at common SAFE boundary.

Authored for the deferred test gate. No live approval or execution here.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from test.owner_auth_fixture import record_verified_owner_approval

from sofia.platform.safe.execution_approval import (
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
    state.touch()
    verifier = ExecutionApprovalVerifier(state)
    active = _approval({"source_host": "Venus"})
    record_verified_owner_approval(verifier, active)
    # Legacy corruption or an older build's forged row must never be
    # returned as a valid approval, even if its exact digest still matches.
    with closing(sqlite3.connect(state)) as db, db:
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
    state.touch()
    verifier = ExecutionApprovalVerifier(state)
    approved = {
        "source_host": "Venus", "target_host": "Artemis",
        "expected_effect": "stop-old-owner-and-transfer",
        "lease_epoch": 4,
    }
    approval = _approval(approved)
    record_verified_owner_approval(verifier, approval)
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


def test_missing_state_cannot_bootstrap_new_safe_approval_authority(tmp_path):
    state = tmp_path / "wrong-home" / "sofia.db"
    with pytest.raises(FileNotFoundError, match="canonical SQLite state is unavailable"):
        ExecutionApprovalVerifier(state)
    assert not state.exists()
    assert not state.parent.exists()


def test_existing_verifier_cannot_recreate_missing_canonical_state(tmp_path):
    state = tmp_path / "sofia.db"
    state.touch()
    verifier = ExecutionApprovalVerifier(state)
    approved = {"source_host": "Venus"}
    grant = _approval(approved,identifier="recovered-approval-no-new-state")
    record_verified_owner_approval(verifier, grant)
    state.unlink()
    with pytest.raises(FileNotFoundError, match="canonical SQLite state is unavailable"):
        verifier.consume(
            approval_id=grant.approval_id,capability=grant.capability,
            parameters=approved,now=NOW+timedelta(seconds=1),
        )
    assert not state.exists()


def test_level3_exact_execution_refuses_unverified_owner_label(tmp_path):
    """CA-1904: a string 'Sparks' alone must never authorize a reversible effect."""
    state = tmp_path / "sofia.db"
    state.touch()
    verifier = ExecutionApprovalVerifier(state)
    exact = {"service": "example"}
    approval = ExecutionApproval(
        approval_id="reversible-auth-required",
        capability="local.service.restart",
        request_fingerprint=execution_fingerprint("local.service.restart", exact),
        approved_by="Sparks",
        approved_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    with pytest.raises(PermissionError, match="level-3"):
        verifier.record(approval)
    assert verifier.matches_unconsumed(
        approval_id=approval.approval_id,
        capability=approval.capability,
        parameters=exact,
        now=NOW + timedelta(seconds=1),
    ) is False

    # Simulate a legacy unverified row from before the stronger SAFE gate.
    # All three read/execute paths must still reject it.
    with closing(sqlite3.connect(state)) as db, db:
        db.execute(
            "INSERT INTO safe_execution_approval "
            "(approval_id,capability,request_fingerprint,approved_by,"
            "approved_at,expires_at,consumed_at) VALUES (?,?,?,?,?,?,NULL)",
            (
                approval.approval_id, approval.capability,
                approval.request_fingerprint, approval.approved_by,
                approval.approved_at.isoformat(), approval.expires_at.isoformat(),
            ),
        )
    assert "local.service.restart" not in verifier.active_capabilities(
        now=NOW + timedelta(seconds=1)
    )
    assert not verifier.matches_unconsumed(
        approval_id=approval.approval_id,
        capability=approval.capability,
        parameters=exact,
        now=NOW + timedelta(seconds=1),
    )
    with pytest.raises(PermissionError, match="verified owner authentication"):
        verifier.consume(
            approval_id=approval.approval_id,
            capability=approval.capability,
            parameters=exact,
            now=NOW + timedelta(seconds=1),
        )


def test_level3_verified_windows_hello_can_authorize_exact_once(tmp_path):
    """L3 accepts signed user-verification; L4 still requires a security key."""
    state = tmp_path / "sofia.db"
    state.touch()
    verifier = ExecutionApprovalVerifier(state)
    exact = {"service": "example"}
    approval = ExecutionApproval(
        approval_id="reversible-with-valid-proof",
        capability="local.service.restart",
        request_fingerprint=execution_fingerprint("local.service.restart", exact),
        approved_by="Sparks",
        approved_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        verifier, approval, credential_kind="platform",
    )
    assert verifier.matches_unconsumed(
        approval_id=approval.approval_id,
        capability=approval.capability,
        parameters=exact,
        now=NOW + timedelta(seconds=1),
    )
    assert verifier.consume(
        approval_id=approval.approval_id,
        capability=approval.capability,
        parameters=exact,
        now=NOW + timedelta(seconds=1),
    ) == approval


def test_level3_execution_cli_requires_web_authentication(tmp_path, capsys):
    from sofia.platform.safe.approve_execution import main

    state = tmp_path / "sofia.db"
    state.touch()
    result = main([
        "--state-path", str(state),
        "--capability", "local.service.restart",
        "--parameters-json", '{"service":"example"}',
    ])
    assert result == 2
    assert "level-3+" in capsys.readouterr().err
