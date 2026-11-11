"""Policy-governed automatic Fleet admission regressions."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.distributed.model import (
    DistributedNode,
    NodeEnrollment,
    NodeEndpoint,
    NodeTransport,
)
from sofia.platform.ops.automatic_admission import (
    InstallationAttestation,
    InstallationAttestationVerifier,
)
from sofia.platform.ops.capability import OpsToolService
from sofia.platform.ops.enrollment import (
    AuthenticatedPeerEvidence,
    MachineNodeBinding,
)
from sofia.platform.ops.model import HostLifecycle
from sofia.platform.safe.autonomy_policy import (
    PROFILE_HIGH_AUTONOMY,
    AutonomyPolicyStore,
    new_autonomy_policy,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)
from sofia.platform.safe.autonomy_policy import AUTONOMY_POLICY_CAPABILITY
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_ops_fleet_discovery_permissions import _ready_fleet_candidate


@pytest.fixture(autouse=True)
def _disposable_fleet_state(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")


def _policy(now, *, automatic=True, signer="publisher:sparks"):
    return new_autonomy_policy(
        profile=PROFILE_HIGH_AUTONOMY,
        now=now,
        automatic_fleet_admission=automatic,
        admission_signer_key_ids=(signer,),
        max_initial_permission_level=2,
    )


def _establish(store, policy, now):
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
    store.establish(policy, approval_id=approval.approval_id, now=now)


def _publisher():
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    return key, public


def _attestation(*, key, node_id, public_key_sha256, now, signer="publisher:sparks"):
    unsigned = InstallationAttestation(
        installation_identity_id="installation:worker",
        node_id=node_id,
        public_key_sha256=public_key_sha256,
        release_manifest_digest="b" * 64,
        signer_key_id=signer,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        signature=b"\x00",
    )
    return InstallationAttestation(
        installation_identity_id=unsigned.installation_identity_id,
        node_id=unsigned.node_id,
        public_key_sha256=unsigned.public_key_sha256,
        release_manifest_digest=unsigned.release_manifest_digest,
        signer_key_id=unsigned.signer_key_id,
        issued_at=unsigned.issued_at,
        expires_at=unsigned.expires_at,
        signature=key.sign(unsigned.message()),
    )


def _enrollment_inputs(service, now, node_id, key):
    candidate = service.registry.host("worker")
    binding = MachineNodeBinding("worker", node_id, now, "verified-mtls-test")
    enrollment = NodeEnrollment(
        DistributedNode(node_id, "worker"), key, now, "provisioner:test",
    )
    peer = AuthenticatedPeerEvidence(node_id, key, now, "independent-verifier")
    endpoint = NodeEndpoint("worker.lan", 7443, NodeTransport.HTTPS)
    return candidate, binding, enrollment, peer, endpoint


def test_automatic_admission_is_denied_without_an_owner_policy(tmp_path):
    state = tmp_path / "sofia.db"
    service = OpsToolService(state)
    now = datetime.now(timezone.utc)
    _, node_id, key = _ready_fleet_candidate(service, observed_at=now)
    candidate, binding, enrollment, peer, endpoint = _enrollment_inputs(
        service, now, node_id, key,
    )
    publisher, public = _publisher()
    attestation = _attestation(
        key=publisher, node_id=node_id, public_key_sha256=key, now=now,
    )
    with pytest.raises(PermissionError, match="active autonomy policy"):
        service.enrollment.enroll_under_policy(
            candidate, binding=binding, enrollment=enrollment, peer=peer,
            attestation=attestation, endpoint=endpoint,
            policy_store=AutonomyPolicyStore(state),
            attestation_verifier=InstallationAttestationVerifier({"publisher:sparks": public}),
        )
    assert service.host("worker")["trusted"] is False


def test_signed_installation_under_active_policy_enrolls_exactly_once(tmp_path):
    state = tmp_path / "sofia.db"
    service = OpsToolService(state)
    now = datetime.now(timezone.utc)
    _, node_id, key = _ready_fleet_candidate(service, observed_at=now)
    store = AutonomyPolicyStore(state)
    policy = _policy(now)
    _establish(store, policy, now)
    publisher, public = _publisher()
    attestation = _attestation(
        key=publisher, node_id=node_id, public_key_sha256=key, now=now,
    )
    candidate, binding, enrollment, peer, endpoint = _enrollment_inputs(
        service, now, node_id, key,
    )
    enrolled = service.enrollment.enroll_under_policy(
        candidate, binding=binding, enrollment=enrollment, peer=peer,
        attestation=attestation, endpoint=endpoint,
        policy_store=store,
        attestation_verifier=InstallationAttestationVerifier({"publisher:sparks": public}),
    )
    assert enrolled.trusted is True
    assert enrolled.lifecycle is HostLifecycle.ENROLLED
    assert enrolled.node_id == node_id
    with closing(sqlite3.connect(state)) as db:
        actor, event, payload = db.execute(
            "SELECT actor_id,event_type,payload_json FROM safe_audit_event "
            "ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    assert (actor, event) == (f"policy:{policy.policy_id}", "fleet.enrolled")
    assert policy.policy_id in payload
    assert "initial_permission_level" in payload
    with pytest.raises(PermissionError):
        service.enrollment.enroll_under_policy(
            service.registry.host("worker"), binding=binding, enrollment=enrollment,
            peer=peer, attestation=attestation, endpoint=endpoint,
            policy_store=store,
            attestation_verifier=InstallationAttestationVerifier({"publisher:sparks": public}),
        )


@pytest.mark.parametrize("failure", ["signer", "key", "disabled"])
def test_untrusted_provenance_never_creates_fleet_trust(tmp_path, failure):
    state = tmp_path / "sofia.db"
    service = OpsToolService(state)
    now = datetime.now(timezone.utc)
    _, node_id, key = _ready_fleet_candidate(service, observed_at=now)
    store = AutonomyPolicyStore(state)
    signer = "publisher:unknown" if failure == "signer" else "publisher:sparks"
    policy = _policy(now, automatic=failure != "disabled", signer="publisher:sparks")
    _establish(store, policy, now)
    publisher, public = _publisher()
    attestation = _attestation(
        key=publisher, node_id=node_id,
        public_key_sha256="c" * 64 if failure == "key" else key,
        now=now, signer=signer,
    )
    candidate, binding, enrollment, peer, endpoint = _enrollment_inputs(
        service, now, node_id, key,
    )
    with pytest.raises(PermissionError):
        service.enrollment.enroll_under_policy(
            candidate, binding=binding, enrollment=enrollment, peer=peer,
            attestation=attestation, endpoint=endpoint,
            policy_store=store,
            attestation_verifier=InstallationAttestationVerifier({
                "publisher:sparks": public, "publisher:other": public,
            }),
        )
    assert service.host("worker")["trusted"] is False
    assert service.host("worker")["lifecycle"] == "candidate"


def test_attestation_signature_tampering_is_denied(tmp_path):
    state = tmp_path / "sofia.db"
    service = OpsToolService(state)
    now = datetime.now(timezone.utc)
    _, node_id, key = _ready_fleet_candidate(service, observed_at=now)
    store = AutonomyPolicyStore(state)
    _establish(store, _policy(now), now)
    publisher, public = _publisher()
    attestation = _attestation(
        key=publisher, node_id=node_id, public_key_sha256=key, now=now,
    )
    tampered = InstallationAttestation(
        installation_identity_id=attestation.installation_identity_id,
        node_id=attestation.node_id,
        public_key_sha256=attestation.public_key_sha256,
        release_manifest_digest="d" * 64,
        signer_key_id=attestation.signer_key_id,
        issued_at=attestation.issued_at,
        expires_at=attestation.expires_at,
        signature=attestation.signature,
    )
    candidate, binding, enrollment, peer, endpoint = _enrollment_inputs(
        service, now, node_id, key,
    )
    with pytest.raises(PermissionError, match="signature"):
        service.enrollment.enroll_under_policy(
            candidate, binding=binding, enrollment=enrollment, peer=peer,
            attestation=tampered, endpoint=endpoint,
            policy_store=store,
            attestation_verifier=InstallationAttestationVerifier({"publisher:sparks": public}),
        )
    assert service.host("worker")["trusted"] is False
