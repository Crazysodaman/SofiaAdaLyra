"""Final Fleet removal requires exact authenticated owner authority."""
from test.fleet_state_fixture import register_fixture_candidate
from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest

from sofia.platform.ops.fleet import FleetRemovalApproval
from sofia.platform.ops.model import FleetHost, HostLifecycle
from sofia.platform.ops.state_registry import StatePlaneFleetRegistry
from sofia.platform.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.platform.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.platform.distributed.durable import DurableRemoteAuthorization
from sofia.platform.distributed.authorization import RemoteGrant
from sofia.platform.distributed.model import (
    ApprovedEndpoint, DistributedNode, NodeEndpoint, NodeEnrollment, NodeTransport,
)
from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint
from sofia.platform.safe.permissions import PermissionLevel, capability_permission_policy
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from test.owner_auth_fixture import record_verified_owner_approval


def _draining_registry(path, node_id=None):
    registry = StatePlaneFleetRegistry(SQLiteStatePlane(path))
    register_fixture_candidate(registry, FleetHost(
        "worker", "linux", "x86_64", HostLifecycle.CANDIDATE, True,
        node_id=node_id,
    ))
    for state in (HostLifecycle.ENROLLED, HostLifecycle.HEALTHY, HostLifecycle.DRAINING):
        registry.transition("worker", state)
    return registry


def test_owner_display_name_cannot_authorize_durable_removal(canonical_state_path):
    registry = _draining_registry(canonical_state_path)
    forged = FleetRemovalApproval(
        "display-name-only", "worker", "proposal:one", "Sparks", datetime.now(timezone.utc),
    )
    with pytest.raises(PermissionError):
        registry.decommission("worker", proposal_revision="proposal:one", approval=forged)
    assert registry.host("worker").lifecycle is HostLifecycle.DRAINING
    assert StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path)).host("worker").trusted


@pytest.fixture
def removal(canonical_state_path):
    node_id, grant_id = uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    registry = _draining_registry(canonical_state_path, node_id)
    identities = DurableNodeIdentityRegistry(canonical_state_path)
    endpoints = DurableEndpointPolicy(canonical_state_path)
    grants = DurableRemoteAuthorization(canonical_state_path)
    try:
        identities.enroll(NodeEnrollment(DistributedNode(node_id, "worker"), "a"*64, now, "Sparks"))
        endpoints.approve(ApprovedEndpoint(node_id, NodeEndpoint("worker.lan", 7443, NodeTransport.HTTPS), "Sparks"))
        grants.add_approved_grant(RemoteGrant(grant_id, node_id, "system.inspect", "system", "Sparks", now+timedelta(hours=1)))
    finally:
        identities.close(); endpoints.close(); grants.close()
    parameters = registry.removal_parameters("worker", proposal_revision="proposal:one")
    approval = ExecutionApproval(
        "remove-worker", "fleet.decommission", execution_fingerprint("fleet.decommission", parameters),
        "Sparks", now, now+timedelta(minutes=5),
    )
    record_verified_owner_approval(ExecutionApprovalVerifier(canonical_state_path), approval)
    reference = FleetRemovalApproval(approval.approval_id, "worker", "proposal:one", "display label only", now)
    return canonical_state_path, registry, parameters, reference, node_id, grant_id


def _net_active(path, node_id, grant_id):
    identities = DurableNodeIdentityRegistry(path)
    endpoints = DurableEndpointPolicy(path)
    grants = DurableRemoteAuthorization(path)
    try:
        return (
            identities.get(node_id) is not None,
            endpoints.get(node_id) is not None,
            grants.permits(grant_id, node_id=node_id, capability="system.inspect", operation="system", now=datetime.now(timezone.utc)),
        )
    finally:
        identities.close(); endpoints.close(); grants.close()


def test_verified_removal_revokes_known_net_trust_and_persists_tombstone(removal):
    path, registry, _, reference, node_id, grant_id = removal
    removed = registry.decommission("worker", proposal_revision="proposal:one", approval=reference)
    assert removed.lifecycle is HostLifecycle.DECOMMISSIONED
    assert removed.trusted is False and removed.node_id == node_id
    assert _net_active(path, node_id, grant_id) == (False, False, False)
    reopened = StatePlaneFleetRegistry(SQLiteStatePlane(path))
    assert reopened.host("worker") == removed
    with pytest.raises((PermissionError, ValueError)):
        reopened.decommission("worker", proposal_revision="proposal:one", approval=reference)
    assert AuditChain(path).verify() == (True, None)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT actor_id FROM safe_audit_event WHERE event_type='fleet.decommissioned'").fetchone()[0] == "person:sparks"


@pytest.mark.parametrize("failure", ["identity", "endpoint", "grants", "fleet", "audit"])
def test_removal_failure_rolls_back_revocation_and_owner_approval(removal, monkeypatch, failure):
    path, registry, parameters, reference, node_id, grant_id = removal
    owner, method = {
        "identity": (DurableNodeIdentityRegistry, "_retire_in_transaction"),
        "endpoint": (DurableEndpointPolicy, "_revoke_in_transaction"),
        "grants": (DurableRemoteAuthorization, "_revoke_node_in_transaction"),
        "fleet": (SQLiteStatePlane, "_write_one"),
        "audit": (AuditChain, "append_in_transaction"),
    }[failure]
    original = getattr(owner, method)

    def fail_after_mutation(*args, **kwargs):
        result = original(*args, **kwargs)
        if failure != "audit" or kwargs.get("event_type") == "fleet.decommissioned":
            raise RuntimeError("injected removal failure")
        return result

    with monkeypatch.context() as scoped:
        scoped.setattr(owner, method, staticmethod(fail_after_mutation) if failure == "fleet" else fail_after_mutation)
        with pytest.raises(RuntimeError, match="injected removal"):
            registry.decommission("worker", proposal_revision="proposal:one", approval=reference)
    assert _net_active(path, node_id, grant_id) == (True, True, True)
    assert registry.host("worker").lifecycle is HostLifecycle.DRAINING
    assert StatePlaneFleetRegistry(SQLiteStatePlane(path)).host("worker").lifecycle is HostLifecycle.DRAINING
    assert ExecutionApprovalVerifier(path).matches_unconsumed(
        approval_id=reference.approval_id, capability="fleet.decommission",
        parameters=parameters, now=datetime.now(timezone.utc),
    )
    assert AuditChain(path).verify() == (True, None)
    assert registry.decommission("worker", proposal_revision="proposal:one", approval=reference).trusted is False


def test_stale_registry_revision_requires_a_fresh_removal_approval(removal):
    path, registry, _, reference, node_id, grant_id = removal
    other = StatePlaneFleetRegistry(SQLiteStatePlane(path))
    other.transition("worker", HostLifecycle.QUARANTINED)
    with pytest.raises(PermissionError, match="parameters do not match"):
        registry.decommission("worker", proposal_revision="proposal:one", approval=reference)
    assert _net_active(path, node_id, grant_id) == (True, True, True)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?", (reference.approval_id,)).fetchone()[0] is None


def test_revoked_owner_proof_cannot_remove_or_revoke_remote_grants(removal):
    path, registry, _, reference, node_id, grant_id = removal
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE safe_owner_credential SET revoked_at=?", (datetime.now(timezone.utc).isoformat(),))
    with pytest.raises(PermissionError, match="authentication"):
        registry.decommission("worker", proposal_revision="proposal:one", approval=reference)
    assert _net_active(path, node_id, grant_id) == (True, True, True)


def test_final_removal_is_never_self_authorized_or_standing():
    policy = capability_permission_policy("fleet.decommission")
    assert policy.level is PermissionLevel.NEVER_SELF_AUTHORIZED
    assert policy.standing_grant_allowed is False


def test_wrong_proposal_cannot_retarget_an_exact_removal_approval(removal):
    path, registry, parameters, reference, node_id, grant_id = removal
    wrong = FleetRemovalApproval(
        reference.approval_id, "worker", "proposal:other", "Sparks", reference.approved_at,
    )
    with pytest.raises(PermissionError, match="parameters do not match"):
        registry.decommission("worker", proposal_revision="proposal:other", approval=wrong)
    assert _net_active(path, node_id, grant_id) == (True, True, True)
    assert ExecutionApprovalVerifier(path).matches_unconsumed(
        approval_id=reference.approval_id, capability="fleet.decommission",
        parameters=parameters, now=datetime.now(timezone.utc),
    )


def test_owner_secret_can_authorize_removal_without_enrolled_fido2(canonical_state_path, monkeypatch):
    from sofia.platform.safe import owner_secret
    monkeypatch.setattr(
        owner_secret, "require_venus_interactive_windows",
        lambda *, require_terminal=False: "S-1-5-21-SYNTHETIC-OWNER",
    )
    registry = _draining_registry(canonical_state_path)
    parameters = registry.removal_parameters("worker", proposal_revision="proposal:secret")
    secret_store = owner_secret.OwnerSecretStore(canonical_state_path)
    synthetic_secret = "ca" * 32
    secret_store.enroll(synthetic_secret)
    fingerprint = execution_fingerprint("fleet.decommission", parameters)
    authentication = secret_store.authenticate(synthetic_secret, action_fingerprint=fingerprint)
    now = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        "software-removal", "fleet.decommission", fingerprint,
        "person:sparks", now, now+timedelta(seconds=90),
    )
    ExecutionApprovalVerifier(canonical_state_path).record(approval, authentication_event_id=authentication)
    with closing(sqlite3.connect(canonical_state_path)) as db:
        assert db.execute("SELECT COUNT(*) FROM safe_owner_credential").fetchone()[0] == 0
    reference = FleetRemovalApproval(approval.approval_id, "worker", "proposal:secret", "owner display", now)
    assert registry.decommission("worker", proposal_revision="proposal:secret", approval=reference).trusted is False


def test_legacy_tombstone_cleanup_needs_its_own_fresh_approval(removal):
    path, registry, _, reference, node_id, grant_id = removal
    registry.decommission("worker", proposal_revision="proposal:one", approval=reference)
    parameters = registry.removal_parameters("worker", proposal_revision="proposal:cleanup")
    now = datetime.now(timezone.utc)
    approved = ExecutionApproval(
        "cleanup-removal", "fleet.decommission", execution_fingerprint("fleet.decommission", parameters),
        "Sparks", now, now+timedelta(minutes=5),
    )
    record_verified_owner_approval(ExecutionApprovalVerifier(path), approved)
    fresh = FleetRemovalApproval(approved.approval_id, "worker", "proposal:cleanup", "Sparks", now)
    assert registry.decommission("worker", proposal_revision="proposal:cleanup", approval=fresh).trusted is False
    assert _net_active(path, node_id, grant_id) == (False, False, False)
