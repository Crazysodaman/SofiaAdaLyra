from datetime import datetime, timezone
from uuid import UUID

import pytest

from sofia.distributed.endpoint_policy import ApprovedEndpoint
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import DistributedNode, NodeEndpoint, NodeTransport
from sofia.ops.state_registry import StatePlaneFleetRegistry
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.ops import (
    FleetDiscoveryCoordinator,
    FleetDiscoveryEvidence,
    FleetDiscoveryEnrollmentReconciler,
    FleetRegistry,
    FleetEnrollmentService,
    FleetHost,
    HostLifecycle,
)


NOW = datetime(2026, 9, 29, 22, 30, tzinfo=timezone.utc)


def evidence(host_id="terra", **overrides):
    values = {
        "host_id": host_id,
        "hostname": host_id,
        "platform": "linux",
        "architecture": "x86_64",
        "observed_at": NOW,
        "source": "approved-lan",
        "inside_approved_scope": True,
        "trusted_bootstrap_available": True,
    }
    values.update(overrides)
    return FleetDiscoveryEvidence(**values)


def test_discovery_creates_untrusted_candidate_only():
    registry = FleetRegistry()
    result = FleetDiscoveryCoordinator(registry).ingest((evidence(),))

    host = registry.host("terra")
    assert host is not None
    assert host.lifecycle is HostLifecycle.CANDIDATE
    assert host.trusted is False
    assert host.node_id is None
    assert result.created_host_ids == ("terra",)


def test_discovery_does_not_enroll_existing_candidate():
    registry = FleetRegistry()
    coordinator = FleetDiscoveryCoordinator(registry)
    coordinator.ingest((evidence(),))
    second = coordinator.ingest((evidence(),))

    host = registry.host("terra")
    assert host.lifecycle is HostLifecycle.CANDIDATE
    assert host.trusted is False
    assert second.existing_host_ids == ("terra",)


def test_out_of_scope_discovery_is_rejected_without_registration():
    registry = FleetRegistry()
    result = FleetDiscoveryCoordinator(registry).ingest(
        (evidence(inside_approved_scope=False),)
    )

    assert registry.host("terra") is None
    assert result.rejected_host_ids == ("terra",)


def test_conflicting_same_run_evidence_is_rejected():
    registry = FleetRegistry()
    coordinator = FleetDiscoveryCoordinator(registry)

    with pytest.raises(ValueError, match="conflicting discovery evidence"):
        coordinator.ingest(
            (
                evidence(host_id="terra", hostname="terra"),
                evidence(host_id="terra", hostname="different"),
            )
        )

    assert registry.host("terra") is None


def test_discovery_cannot_mutate_durable_platform_identity():
    registry = FleetRegistry()
    coordinator = FleetDiscoveryCoordinator(registry)
    coordinator.ingest((evidence(),))

    with pytest.raises(ValueError, match="durable Fleet identity"):
        coordinator.ingest(
            (
                evidence(
                    platform="windows",
                    architecture="amd64",
                ),
            )
        )

    host = registry.host("terra")
    assert host.platform == "linux"
    assert host.architecture == "x86_64"
    assert host.trusted is False


def test_discovery_evidence_converts_to_existing_bootstrap_contract():
    candidate = evidence(
        installed_agent_version="1.2.3",
        installed_agent_sha256="a" * 64,
        installed_protocol_version="1.0",
        installed_signer_key_id="release-key",
        installed_signature_verified=True,
    ).bootstrap_candidate()

    assert candidate.host_id == "terra"
    assert candidate.discovery_source == "approved-lan"
    assert candidate.trusted_bootstrap_available is True
    assert candidate.installed_agent_version == "1.2.3"
    assert candidate.installed_agent_sha256 == "a" * 64
    assert candidate.installed_protocol_version == "1.0"


def test_preapproved_discovered_identity_auto_enrolls(tmp_path):
    registry = FleetRegistry()
    coordinator = FleetDiscoveryCoordinator(registry)
    node_id = UUID("11111111-2222-3333-4444-555555555555")
    key = "b" * 64
    observation = evidence(
        host_id="Artemis",
        hostname="artemis.local",
        platform="windows",
        architecture="amd64",
        observed_node_id=node_id,
        observed_public_key_sha256=key,
        observed_endpoint_hostname="artemis.local",
        observed_endpoint_port=7443,
    )
    discovery = coordinator.ingest((observation,))

    identities = DurableNodeIdentityRegistry(tmp_path / "identities.db")
    endpoints = DurableEndpointPolicy(tmp_path / "endpoints.db")
    identities.enroll(
        NodeEnrollment(
            DistributedNode(node_id, "Artemis"),
            key,
            NOW,
            "Sparks",
        )
    )
    endpoint = NodeEndpoint(
        "artemis.local",
        7443,
        NodeTransport.HTTPS,
    )
    endpoints.approve(
        ApprovedEndpoint(
            node_id,
            endpoint,
            "Sparks",
        )
    )
    reconciled = FleetDiscoveryEnrollmentReconciler(
        enrollment_service=FleetEnrollmentService(registry),
        identity_registry=identities,
        endpoint_policy=endpoints,
    ).reconcile(discovery)

    host = registry.host("Artemis")
    assert host is not None
    assert host.lifecycle is HostLifecycle.ENROLLED
    assert host.trusted is True
    assert host.node_id == node_id
    assert reconciled.enrolled_host_ids == ("Artemis",)

    identities.close()
    endpoints.close()


def test_unapproved_discovered_identity_stays_candidate(tmp_path):
    registry = FleetRegistry()
    coordinator = FleetDiscoveryCoordinator(registry)
    node_id = UUID("11111111-2222-3333-4444-555555555555")
    observation = evidence(
        host_id="Artemis",
        hostname="artemis.local",
        platform="windows",
        architecture="amd64",
        observed_node_id=node_id,
        observed_public_key_sha256="c" * 64,
        observed_endpoint_hostname="artemis.local",
        observed_endpoint_port=7443,
    )
    discovery = coordinator.ingest((observation,))

    identities = DurableNodeIdentityRegistry(tmp_path / "identities.db")
    endpoints = DurableEndpointPolicy(tmp_path / "endpoints.db")
    reconciled = FleetDiscoveryEnrollmentReconciler(
        enrollment_service=FleetEnrollmentService(registry),
        identity_registry=identities,
        endpoint_policy=endpoints,
    ).reconcile(discovery)

    host = registry.host("Artemis")
    assert host is not None
    assert host.lifecycle is HostLifecycle.CANDIDATE
    assert host.trusted is False
    assert host.node_id is None
    assert reconciled.pending_host_ids == ("Artemis",)

    identities.close()
    endpoints.close()


def test_state_plane_registry_persists_authenticated_candidate(tmp_path):
    plane = SQLiteStatePlane(tmp_path / "state.db")
    registry = StatePlaneFleetRegistry(plane)
    registry.register_candidate(
        FleetHost(
            host_id="Artemis",
            platform="windows",
            architecture="amd64",
            lifecycle=HostLifecycle.CANDIDATE,
            trusted=False,
        )
    )
    node_id = UUID("11111111-2222-3333-4444-555555555555")

    promoted = registry.authenticate_candidate("Artemis", node_id)

    assert promoted.trusted is True
    assert promoted.node_id == node_id

    reloaded = StatePlaneFleetRegistry(plane)
    durable = reloaded.host("Artemis")
    assert durable is not None
    assert durable.trusted is True
    assert durable.node_id == node_id
    assert durable.lifecycle is HostLifecycle.CANDIDATE
