"""Owner approval, NET trust and Fleet admission have one commit boundary."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.platform.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.platform.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.platform.distributed.model import (
    ApprovedEndpoint, DistributedNode, NodeEndpoint, NodeEnrollment, NodeTransport,
)
from sofia.platform.ops.capability import OpsToolService
from sofia.platform.ops.enrollment import (
    AuthenticatedPeerEvidence, FleetEnrollmentApproval, MachineNodeBinding,
)
from sofia.platform.ops.model import HostLifecycle
from sofia.platform.ops.state_registry import StatePlaneFleetRegistry
from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_ops_fleet_discovery_permissions import _ready_fleet_candidate


@pytest.fixture
def admission(canonical_state_path):
    service = OpsToolService(canonical_state_path)
    now, node_id, key = _ready_fleet_candidate(service)
    parameters = {
        "host_id": "worker", "node_id": str(node_id),
        "public_key_sha256": key,
        "endpoint_hostname": "worker.lan", "endpoint_port": 7443,
    }
    approval = ExecutionApproval(
        "atomic-enrollment", "fleet.enroll",
        execution_fingerprint("fleet.enroll", parameters),
        "Sparks", now, now + timedelta(minutes=15),
    )
    record_verified_owner_approval(ExecutionApprovalVerifier(canonical_state_path), approval)
    return canonical_state_path, service, parameters, approval, node_id


def _trust_counts(path):
    with closing(sqlite3.connect(path)) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return tuple(
            db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if table in tables else 0
            for table in ("distributed_node_identity", "approved_remote_endpoint")
        )


@pytest.mark.parametrize("failure", ["identity", "endpoint", "fleet", "audit", "enrollment-audit"])
def test_failure_rolls_back_every_owner_and_preserves_approval(admission, monkeypatch, failure):
    path, service, parameters, approval, _ = admission
    if failure == "identity":
        owner, name = DurableNodeIdentityRegistry, "_enroll_in_transaction"
    elif failure == "endpoint":
        owner, name = DurableEndpointPolicy, "_approve_in_transaction"
    elif failure == "fleet":
        owner, name = SQLiteStatePlane, "_write_one"
    else:
        owner, name = AuditChain, "append_in_transaction"
    original = getattr(owner, name)

    def fail_after_write(*args, **kwargs):
        result = original(*args, **kwargs)
        if failure != "enrollment-audit" or kwargs.get("event_type") == "fleet.enrolled":
            raise RuntimeError("injected admission write failure")
        return result

    with monkeypatch.context() as scoped:
        scoped.setattr(owner, name, staticmethod(fail_after_write) if failure == "fleet" else fail_after_write)
        with pytest.raises(RuntimeError, match="injected admission"):
            service.enroll_candidate({**parameters, "approval_id": approval.approval_id})
    assert _trust_counts(path) == (0, 0)
    reopened = StatePlaneFleetRegistry(SQLiteStatePlane(path))
    assert reopened.host("worker").trusted is False
    assert reopened.host("worker").lifecycle is HostLifecycle.CANDIDATE
    assert service.host("worker")["trusted"] is False
    verifier = ExecutionApprovalVerifier(path)
    assert verifier.matches_unconsumed(
        approval_id=approval.approval_id, capability="fleet.enroll",
        parameters=parameters, now=datetime.now(timezone.utc),
    )
    assert AuditChain(path).verify() == (True, None)
    assert service.enroll_candidate({**parameters, "approval_id": approval.approval_id})["trusted"] is True
    assert _trust_counts(path) == (1, 1)


def test_reopened_admission_is_single_use_and_notifier_observes_committed_state(admission):
    path, service, parameters, approval, _ = admission
    observations = []

    def notified(host, *evidence):
        durable = StatePlaneFleetRegistry(SQLiteStatePlane(path)).host(host.host_id)
        observations.append((durable.lifecycle, _trust_counts(path)))

    service.enrollment.set_enrolled_notifier(notified)
    service.enroll_candidate({**parameters, "approval_id": approval.approval_id})
    assert observations == [(HostLifecycle.ENROLLED, (1, 1))]
    reopened = OpsToolService(path)
    with pytest.raises(PermissionError):
        reopened.enroll_candidate({**parameters, "approval_id": approval.approval_id})
    assert _trust_counts(path) == (1, 1)
    assert AuditChain(path).verify() == (True, None)
    with closing(sqlite3.connect(path)) as db:
        actor, event = db.execute(
            "SELECT actor_id,event_type FROM safe_audit_event ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    assert (actor, event) == ("person:sparks", "fleet.enrolled")


def test_revoked_owner_proof_cannot_create_any_trust(admission):
    path, service, parameters, approval, _ = admission
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE safe_owner_credential SET revoked_at=?", (datetime.now(timezone.utc).isoformat(),))
    with pytest.raises(PermissionError, match="authentication"):
        service.enroll_candidate({**parameters, "approval_id": approval.approval_id})
    assert _trust_counts(path) == (0, 0)
    assert service.host("worker")["trusted"] is False


def test_candidate_changed_by_another_registry_preserves_approval(admission):
    path, service, parameters, approval, _ = admission
    other = StatePlaneFleetRegistry(SQLiteStatePlane(path))
    before = other.host("worker")
    other.refine_candidate_identity(
        "worker", platform=before.platform, architecture=before.architecture,
        tags=(*before.tags, "fresh-observation"),
    )
    with pytest.raises(PermissionError, match="changed since discovery"):
        service.enroll_candidate({**parameters, "approval_id": approval.approval_id})
    assert _trust_counts(path) == (0, 0)
    assert ExecutionApprovalVerifier(path).matches_unconsumed(
        approval_id=approval.approval_id, capability="fleet.enroll",
        parameters=parameters, now=datetime.now(timezone.utc),
    )


@pytest.mark.parametrize("actor", ["Sparks", "person:sparks", "person:forged-owner"])
def test_direct_service_dto_cannot_replace_authenticated_approval(admission, actor):
    path, service, parameters, approval, node_id = admission
    candidate = service.registry.host("worker")
    observed = datetime.fromisoformat(service.enrollment_evidence("worker")["observed_at"])
    with pytest.raises(PermissionError, match="approval does not exist"):
        service.enrollment.enroll(
            candidate,
            binding=MachineNodeBinding("worker", node_id, observed, "verified-mtls"),
            enrollment=NodeEnrollment(DistributedNode(node_id, "worker"), parameters["public_key_sha256"], observed, actor),
            peer=AuthenticatedPeerEvidence(node_id, parameters["public_key_sha256"], observed, "verified-mtls"),
            endpoint=NodeEndpoint("worker.lan", 7443, NodeTransport.HTTPS),
            approval=FleetEnrollmentApproval("forged-reference", "worker", node_id, parameters["public_key_sha256"], actor, approval.approved_at),
        )
    assert _trust_counts(path) == (0, 0)
    assert service.host("worker")["trusted"] is False


def test_approval_from_another_machine_database_is_not_reusable(admission, tmp_path):
    path, service, parameters, approval, _ = admission
    foreign_path = bootstrap_canonical_sqlite(tmp_path / "other-machine.db")
    foreign = OpsToolService(foreign_path)
    foreign.registry.register_candidate(service.registry.host("worker"))
    with pytest.raises(PermissionError, match="approval does not exist"):
        foreign.enroll_candidate({**parameters, "approval_id": approval.approval_id})
    assert _trust_counts(foreign_path) == (0, 0)
    assert ExecutionApprovalVerifier(path).matches_unconsumed(
        approval_id=approval.approval_id, capability="fleet.enroll",
        parameters=parameters, now=datetime.now(timezone.utc),
    )


@pytest.mark.parametrize("owner", [DurableNodeIdentityRegistry, DurableEndpointPolicy])
def test_internal_transaction_must_belong_to_the_store_database(admission, tmp_path, owner):
    path, _, _, _, node_id = admission
    store = owner(path)
    try:
        with closing(sqlite3.connect(tmp_path / "foreign.db")) as db:
            db.execute("BEGIN IMMEDIATE")
            with pytest.raises(RuntimeError, match="own database transaction"):
                store._get_in_transaction(db, node_id)
    finally:
        store.close()


def test_expired_exact_approval_does_not_create_trust(admission):
    path, service, parameters, _, _ = admission
    now = datetime.now(timezone.utc)
    expired = ExecutionApproval(
        "expired-admission", "fleet.enroll",
        execution_fingerprint("fleet.enroll", parameters),
        "Sparks", now - timedelta(minutes=2), now - timedelta(minutes=1),
    )
    record_verified_owner_approval(ExecutionApprovalVerifier(path), expired)
    with pytest.raises(PermissionError, match="expired"):
        service.enroll_candidate({**parameters, "approval_id": expired.approval_id})
    assert _trust_counts(path) == (0, 0)
    assert service.host("worker")["trusted"] is False


@pytest.mark.parametrize("revoked", ["identity", "endpoint"])
def test_revoked_net_trust_is_not_reenrolled_or_allowed_to_burn_approval(admission, revoked):
    path, service, parameters, approval, node_id = admission
    if revoked == "identity":
        owner = DurableNodeIdentityRegistry(path)
        owner.enroll(NodeEnrollment(
            DistributedNode(node_id, "worker"), parameters["public_key_sha256"],
            approval.approved_at, "Sparks",
        ))
        owner.retire(node_id)
    else:
        owner = DurableEndpointPolicy(path)
        owner.approve(ApprovedEndpoint(
            node_id, NodeEndpoint("worker.lan", 7443, NodeTransport.HTTPS), "Sparks",
        ))
        owner.revoke(node_id)
    owner.close()
    before = _trust_counts(path)
    with pytest.raises(PermissionError, match="retired|revoked"):
        service.enroll_candidate({**parameters, "approval_id": approval.approval_id})
    assert _trust_counts(path) == before
    assert service.host("worker")["trusted"] is False
    assert ExecutionApprovalVerifier(path).matches_unconsumed(
        approval_id=approval.approval_id, capability="fleet.enroll",
        parameters=parameters, now=datetime.now(timezone.utc),
    )
