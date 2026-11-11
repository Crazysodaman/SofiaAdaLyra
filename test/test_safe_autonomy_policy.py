"""Owner-established autonomy policy regressions."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from uuid import uuid4

import pytest

from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.autonomy_policy import (
    AUTONOMY_POLICY_CAPABILITY,
    PROFILE_HIGH_AUTONOMY,
    PROFILE_OBSERVE,
    AutonomyPolicyStore,
    approval_parameters,
    new_autonomy_policy,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from test.owner_auth_fixture import record_verified_owner_approval


def _approve(store, policy, now):
    approval = ExecutionApproval(
        approval_id=str(uuid4()),
        capability=AUTONOMY_POLICY_CAPABILITY,
        request_fingerprint=execution_fingerprint(
            AUTONOMY_POLICY_CAPABILITY, policy.to_parameters(),
        ),
        approved_by="Sparks",
        approved_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(store.path), approval,
    )
    return approval.approval_id


def _state(tmp_path):
    return bootstrap_canonical_sqlite(tmp_path / "sofia.db")


def _high_autonomy(now, *, revision=1):
    return new_autonomy_policy(
        profile=PROFILE_HIGH_AUTONOMY,
        revision=revision,
        now=now,
        automatic_fleet_admission=True,
        automatic_core_migration=True,
        admission_signer_key_ids=("publisher:sparks",),
        max_initial_permission_level=2,
    )


def test_policy_is_absent_until_exact_owner_establishment(tmp_path):
    state = _state(tmp_path)
    store = AutonomyPolicyStore(state)
    assert store.resolve() is None
    now = datetime.now(timezone.utc)
    policy = _high_autonomy(now)
    store.establish(policy, approval_id=_approve(store, policy, now), now=now)
    resolved = store.resolve()
    assert resolved == policy
    assert AuditChain(state).verify() == (True, None)


def test_policy_revision_sequence_and_one_use_owner_approval(tmp_path):
    state = _state(tmp_path)
    store = AutonomyPolicyStore(state)
    now = datetime.now(timezone.utc)
    first = _high_autonomy(now)
    approval_id = _approve(store, first, now)
    store.establish(first, approval_id=approval_id, now=now)
    with pytest.raises(PermissionError):
        store.establish(first, approval_id=approval_id, now=now)
    stale = _high_autonomy(now)
    with pytest.raises(PermissionError):
        store.establish(stale, approval_id=_approve(store, stale, now), now=now)
    second = _high_autonomy(now, revision=2)
    store.establish(second, approval_id=_approve(store, second, now), now=now)
    assert store.resolve().revision == 2


def test_owner_credential_revocation_invalidates_the_policy(tmp_path):
    state = _state(tmp_path)
    store = AutonomyPolicyStore(state)
    now = datetime.now(timezone.utc)
    policy = _high_autonomy(now)
    store.establish(policy, approval_id=_approve(store, policy, now), now=now)
    with closing(sqlite3.connect(state)) as db, db:
        db.execute(
            "UPDATE safe_owner_credential SET revoked_at=?",
            (datetime.now(timezone.utc).isoformat(),),
        )
    with pytest.raises(PermissionError, match="owner proof"):
        store.resolve()


def test_policy_payload_tampering_fails_closed(tmp_path):
    state = _state(tmp_path)
    store = AutonomyPolicyStore(state)
    now = datetime.now(timezone.utc)
    policy = _high_autonomy(now)
    store.establish(policy, approval_id=_approve(store, policy, now), now=now)
    with closing(sqlite3.connect(state)) as db, db:
        payload = json.loads(
            db.execute(
                "SELECT policy_json FROM safe_autonomy_policy WHERE singleton=1"
            ).fetchone()[0]
        )
        payload["max_initial_permission_level"] = 3
        db.execute(
            "UPDATE safe_autonomy_policy SET policy_json=? WHERE singleton=1",
            (json.dumps(payload),),
        )
    with pytest.raises(PermissionError):
        store.resolve()


def test_unsafe_autonomy_combinations_are_rejected():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        new_autonomy_policy(
            profile=PROFILE_OBSERVE,
            now=now,
            automatic_fleet_admission=True,
            admission_signer_key_ids=("publisher:sparks",),
        )
    with pytest.raises(ValueError):
        new_autonomy_policy(
            profile=PROFILE_HIGH_AUTONOMY,
            now=now,
            automatic_fleet_admission=True,
            admission_signer_key_ids=(),
        )
    with pytest.raises(ValueError):
        new_autonomy_policy(
            profile=PROFILE_HIGH_AUTONOMY,
            now=now,
            automatic_fleet_admission=True,
            admission_signer_key_ids=("publisher:sparks",),
            max_initial_permission_level=4,
        )
    with pytest.raises(ValueError):
        new_autonomy_policy(
            profile=PROFILE_HIGH_AUTONOMY,
            now=now,
            automatic_core_migration=True,
            verified_backup_required_for_migration=False,
        )


def test_approval_parameters_are_exact_and_bounded():
    policy = _high_autonomy(datetime.now(timezone.utc))
    assert approval_parameters(policy) == policy.to_payload()
    assert set(policy.to_payload()) == {
        "schema", "policy_id", "revision", "profile", "established_at",
        "established_by", "automatic_fleet_admission",
        "automatic_core_migration", "mutable_identity_self_development",
        "signed_installation_provenance_required",
        "admission_signer_key_ids", "max_initial_permission_level",
        "quarantine_unverified", "verified_backup_required_for_migration",
    }
