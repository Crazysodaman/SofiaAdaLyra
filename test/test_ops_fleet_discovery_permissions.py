from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.capability.model import CapabilityRequest
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import DistributedNode, NodeEnrollment
from sofia.ops.capability import OpsCapabilitySet, OpsToolService
from sofia.ops.discovery import FleetDiscoveryEvidence
from sofia.safe.audit import AuditChain
from sofia.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)
from sofia.safe.permissions import PermissionLevel, capability_permission_policy


class _DiscoverySource:
    def __init__(self, observations):
        self.observations = tuple(observations)
        self.calls = 0

    def discover(self):
        self.calls += 1
        return self.observations


def test_fleet_discovery_is_safe_autonomous_level_two():
    policy = capability_permission_policy("ops.fleet.discover")
    assert policy.level is PermissionLevel.SAFE_AUTONOMOUS
    assert policy.standing_grant_allowed is False


def test_on_demand_discovery_creates_only_untrusted_candidate(tmp_path):
    now = datetime(2026, 10, 4, 20, 0, tzinfo=timezone.utc)
    source = _DiscoverySource((
        FleetDiscoveryEvidence(
            host_id="newbox",
            hostname="newbox",
            platform="unknown",
            architecture="unknown",
            observed_at=now,
            source="test-approved-network-scan",
            inside_approved_scope=True,
        ),
    ))
    service = OpsToolService(
        tmp_path / "sofia.db",
        discovery_source=source,
    )

    result = service.discover_candidates()

    assert result["configured"] is True
    assert result["created_host_ids"] == ("newbox",)
    assert source.calls == 1

    candidate = service.host("newbox")
    assert candidate is not None
    assert candidate["lifecycle"] == "candidate"
    assert candidate["trusted"] is False
    assert candidate["node_id"] is None


def test_unconfigured_fleet_discovery_is_safe_readback_not_error(tmp_path):
    service = OpsToolService(tmp_path / "sofia.db")

    result = service.discover_candidates()

    assert result == {
        "configured": False,
        "observed": (),
        "created_host_ids": (),
        "existing_host_ids": (),
        "rejected_host_ids": (),
    }


def test_fleet_discovery_tool_has_no_approval_parameter(tmp_path):
    service = OpsToolService(tmp_path / "sofia.db")
    capabilities = OpsCapabilitySet(service)
    capability = next(
        item
        for item in capabilities.capabilities()
        if item.name == "ops.fleet.discover"
    )
    assert capability.name == "ops.fleet.discover"

    # The cognitive binding is parameter-free and therefore cannot smuggle an
    # enrollment/trust approval through the discovery path.
    from sofia.ops.capability import create_ops_tool_bindings
    binding = next(
        item
        for item in create_ops_tool_bindings()
        if item.capability_name == "ops.fleet.discover"
    )
    schema = binding.definition.parameters
    assert schema["required"] == []
    assert "approval_id" not in schema["properties"]

    result = capabilities.execute(
        CapabilityRequest(
            capability=capability,
            parameters={},
            requested_scope=None,
            rationale="bounded autonomous discovery",
        )
    )
    assert result["configured"] is False


def test_network_discovery_does_not_persist_fleet_candidate(tmp_path):
    now = datetime(2026, 10, 4, 20, 5, tzinfo=timezone.utc)
    source = _DiscoverySource((
        FleetDiscoveryEvidence(
            host_id="printer",
            hostname="printer",
            platform="unknown",
            architecture="unknown",
            observed_at=now,
            source="test-network-observation",
            inside_approved_scope=True,
        ),
    ))
    service = OpsToolService(
        tmp_path / "sofia.db",
        network_discovery_source=source,
    )

    result = service.discover_network()

    assert result["configured"] is True
    assert result["observed"][0]["host_id"] == "printer"
    assert service.host("printer") is None


def test_network_discovery_is_level_one_read_only():
    policy = capability_permission_policy("network.discover")
    assert policy.level is PermissionLevel.OBSERVE_READ
    assert policy.standing_grant_allowed is False


def test_network_discovery_and_fleet_candidate_discovery_are_independent(tmp_path):
    now = datetime(2026, 10, 4, 20, 10, tzinfo=timezone.utc)
    network_source = _DiscoverySource((
        FleetDiscoveryEvidence(
            host_id="nas",
            hostname="nas",
            platform="unknown",
            architecture="unknown",
            observed_at=now,
            source="network-only",
            inside_approved_scope=True,
        ),
    ))
    fleet_source = _DiscoverySource((
        FleetDiscoveryEvidence(
            host_id="worker",
            hostname="worker",
            platform="linux",
            architecture="x86_64",
            observed_at=now,
            source="fleet-candidate",
            inside_approved_scope=True,
        ),
    ))
    service = OpsToolService(
        tmp_path / "sofia.db",
        discovery_source=fleet_source,
        network_discovery_source=network_source,
    )

    network = service.discover_network()
    assert network["observed"][0]["host_id"] == "nas"
    assert service.host("nas") is None

    fleet = service.discover_candidates()
    assert fleet["created_host_ids"] == ("worker",)
    assert service.host("worker")["trusted"] is False


def _ready_fleet_candidate(service, host_id="worker"):
    now = datetime.now(timezone.utc)
    node_id = uuid4()
    key = "a" * 64
    observation = FleetDiscoveryEvidence(
        host_id=host_id,
        hostname=host_id,
        platform="linux",
        architecture="x86_64",
        observed_at=now,
        source="verified-mtls-test",
        inside_approved_scope=True,
        observed_node_id=node_id,
        observed_public_key_sha256=key,
        observed_endpoint_hostname=f"{host_id}.lan",
        observed_endpoint_port=7443,
        capabilities_verified=True,
        capability_names=("system.inspect","ops.telemetry"),
    )
    service.discovery_source = _DiscoverySource((observation,))
    service.discover_candidates()
    return now, node_id, key


def test_fleet_enrollment_requires_exact_one_time_sparks_approval(tmp_path):
    state = tmp_path / "sofia.db"
    service = OpsToolService(state)
    now, node_id, key = _ready_fleet_candidate(service)
    parameters = {
        "host_id": "worker",
        "node_id": str(node_id),
        "public_key_sha256": key,
        "endpoint_hostname": "worker.lan",
        "endpoint_port": 7443,
    }

    with pytest.raises(PermissionError, match="approval_id"):
        service.enroll_candidate({**parameters, "approval_id": ""})

    approval = ExecutionApproval(
        approval_id="fleet-enroll-worker",
        capability="fleet.enroll",
        request_fingerprint=execution_fingerprint(
            "fleet.enroll",
            parameters,
        ),
        approved_by="Sparks",
        approved_at=now,
        expires_at=now + timedelta(minutes=15),
    )
    audit = AuditChain(state)
    audit.append(
        actor_id="system:test",
        event_type="test.preexisting",
        payload={"before": "fleet.enroll"},
        occurred_at=now - timedelta(seconds=1),
        event_id="fleet-enroll-preexisting-audit",
    )
    verifier = ExecutionApprovalVerifier(state)
    verifier.record(approval)
    assert "fleet.enroll" in verifier.active_capabilities(now=now)

    enrolled = service.enroll_candidate(
        {**parameters, "approval_id": approval.approval_id}
    )
    assert enrolled["trusted"] is True
    assert enrolled["lifecycle"] == "enrolled"
    assert enrolled["node_id"] == str(node_id)
    assert "fleet.enroll" not in verifier.active_capabilities(
        now=now + timedelta(seconds=1)
    )

    with pytest.raises(PermissionError):
        service.enroll_candidate(
            {**parameters, "approval_id": approval.approval_id}
        )
    assert audit.verify() == (True, None)


def test_fleet_enrollment_approval_cannot_be_replayed_for_changed_identity(tmp_path):
    state = tmp_path / "sofia.db"
    service = OpsToolService(state)
    now, node_id, key = _ready_fleet_candidate(service)
    approved = {
        "host_id": "worker",
        "node_id": str(node_id),
        "public_key_sha256": key,
        "endpoint_hostname": "worker.lan",
        "endpoint_port": 7443,
    }
    approval = ExecutionApproval(
        approval_id="fleet-enroll-exact",
        capability="fleet.enroll",
        request_fingerprint=execution_fingerprint(
            "fleet.enroll",
            approved,
        ),
        approved_by="Sparks",
        approved_at=now,
        expires_at=now + timedelta(minutes=15),
    )
    ExecutionApprovalVerifier(state).record(approval)

    with pytest.raises(PermissionError):
        service.enroll_candidate({
            **approved,
            "public_key_sha256": "b" * 64,
            "approval_id": approval.approval_id,
        })


def test_fleet_enrollment_is_level_four_and_never_standing():
    policy = capability_permission_policy("fleet.enroll")
    assert policy.level is PermissionLevel.PROTECTED
    assert policy.standing_grant_allowed is False


def test_rediscovery_refreshes_existing_candidate_evidence(tmp_path):
    state = tmp_path / "sofia.db"
    node_id = uuid4()
    key = "c" * 64
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    fresh = datetime.now(timezone.utc)
    source = _DiscoverySource((
        FleetDiscoveryEvidence(
            host_id="worker",
            hostname="worker",
            platform="linux",
            architecture="x86_64",
            observed_at=old,
            source="verified-mtls-test",
            inside_approved_scope=True,
            observed_node_id=node_id,
            observed_public_key_sha256=key,
            observed_endpoint_hostname="worker.lan",
            observed_endpoint_port=7443,
            capabilities_verified=True,
            capability_names=("system.inspect","ops.telemetry"),
        ),
    ))
    service = OpsToolService(state, discovery_source=source)
    service.discover_candidates()
    first = service.enrollment_evidence("worker")
    assert first["observed_at"] == old.isoformat()

    source.observations = (
        FleetDiscoveryEvidence(
            host_id="worker",
            hostname="worker",
            platform="linux",
            architecture="x86_64",
            observed_at=fresh,
            source="verified-mtls-test",
            inside_approved_scope=True,
            observed_node_id=node_id,
            observed_public_key_sha256=key,
            observed_endpoint_hostname="worker.lan",
            observed_endpoint_port=7443,
            capabilities_verified=True,
            capability_names=("system.inspect","ops.telemetry"),
        ),
    )
    result = service.discover_candidates()
    second = service.enrollment_evidence("worker")

    assert result["existing_host_ids"] == ("worker",)
    assert second["observed_at"] == fresh.isoformat()
    assert second["ready"] is True


def test_fleet_conflict_rejects_before_one_time_approval_is_consumed(tmp_path):
    state = tmp_path / "sofia.db"
    service = OpsToolService(state)
    now, node_id, key = _ready_fleet_candidate(service)
    parameters = {
        "host_id": "worker",
        "node_id": str(node_id),
        "public_key_sha256": key,
        "endpoint_hostname": "worker.lan",
        "endpoint_port": 7443,
    }
    approval = ExecutionApproval(
        approval_id="fleet-enroll-conflict",
        capability="fleet.enroll",
        request_fingerprint=execution_fingerprint(
            "fleet.enroll",
            parameters,
        ),
        approved_by="Sparks",
        approved_at=now,
        expires_at=now + timedelta(minutes=15),
    )
    verifier = ExecutionApprovalVerifier(state)
    verifier.record(approval)

    identities = DurableNodeIdentityRegistry(state)
    try:
        identities.enroll(
            NodeEnrollment(
                DistributedNode(node_id, "different-worker"),
                "d" * 64,
                now,
                "Sparks",
            )
        )
    finally:
        identities.close()

    with pytest.raises(PermissionError, match="identity differs"):
        service.enroll_candidate(
            {**parameters, "approval_id": approval.approval_id}
        )

    # Preflight rejection must leave the exact one-time approval unused.
    consumed = verifier.consume(
        approval_id=approval.approval_id,
        capability="fleet.enroll",
        parameters=parameters,
        now=now + timedelta(seconds=1),
    )
    assert consumed.approval_id == approval.approval_id
