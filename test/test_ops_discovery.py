from datetime import datetime, timezone
from uuid import UUID

import pytest

from sofia.distributed.model import ApprovedEndpoint
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.model import NodeEnrollment
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import DistributedNode, NodeEndpoint, NodeTransport
from sofia.ops.state_registry import StatePlaneFleetRegistry
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.ops import (
    FleetDiscoveryBootstrapCoordinator,
    FleetDiscoveryCoordinator,
    FleetDiscoveryEvidence,
    FleetDiscoveryEnrollmentReconciler,
    FleetRegistry,
    AuthenticatedPeerEvidence,
    FleetEnrollmentApproval,
    FleetEnrollmentService,
    MachineNodeBinding,
    AgentPackage,
    BootstrapDisposition,
    InstallAuthority,
    InstallReceipt,
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


def test_preapproved_discovered_identity_stays_pending_without_sparks_approval(tmp_path):
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
        capabilities_verified=True,
        capability_names=("system.inspect", "ops.telemetry"),
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
    assert host.lifecycle is HostLifecycle.CANDIDATE
    assert host.trusted is False
    assert host.node_id is None
    assert reconciled.enrolled_host_ids == ()
    assert reconciled.pending_host_ids == ("Artemis",)

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


def test_candidate_notifier_runs_once_for_new_host_only():
    notices = []
    registry = FleetRegistry()
    coordinator = FleetDiscoveryCoordinator(
        registry,
        candidate_notifier=lambda host, observation: notices.append(
            (host.host_id, observation.source)
        ),
    )

    coordinator.ingest((evidence(),))
    coordinator.ingest((evidence(),))

    assert notices == [("terra", "approved-lan")]


def test_bootstrap_coordinator_surfaces_operator_when_installer_missing():
    discovery = FleetDiscoveryCoordinator(FleetRegistry()).ingest(
        (evidence(trusted_bootstrap_available=True),)
    )
    notices = []
    coordinator = FleetDiscoveryBootstrapCoordinator(
        package=AgentPackage(
            "sofia-fleet-agent",
            "1.2.3",
            "a" * 64,
            "approved-wheel",
        ),
        authority=InstallAuthority.STANDING_POLICY,
        installer_factory=None,
        operator_notifier=lambda plan: notices.append(plan),
    )

    result = coordinator.reconcile(discovery)

    assert result.operator_host_ids == ("terra",)
    assert result.installed_host_ids == ()
    assert notices
    assert notices[0].disposition is BootstrapDisposition.ASK_OPERATOR


def test_bootstrap_coordinator_executes_typed_installer_when_configured():
    discovery = FleetDiscoveryCoordinator(FleetRegistry()).ingest(
        (evidence(trusted_bootstrap_available=True),)
    )
    package = AgentPackage(
        "sofia-fleet-agent",
        "1.2.3",
        "a" * 64,
        "approved-wheel",
    )

    class Installer:
        def install(self, candidate, approved_package):
            return InstallReceipt(
                candidate.host_id,
                approved_package.package_id,
                approved_package.version,
                approved_package.sha256,
                True,
                approved_package.protocol_version,
            )

    coordinator = FleetDiscoveryBootstrapCoordinator(
        package=package,
        authority=InstallAuthority.STANDING_POLICY,
        installer_factory=lambda observation: Installer(),
    )

    result = coordinator.reconcile(discovery)

    assert result.installed_host_ids == ("terra",)
    assert len(result.receipts) == 1
    assert result.receipts[0].verified is True


def test_bootstrap_coordinator_marks_matching_installed_agent_ready():
    discovery = FleetDiscoveryCoordinator(FleetRegistry()).ingest(
        (
            evidence(
                installed_agent_version="1.2.3",
                installed_agent_sha256="a" * 64,
                installed_protocol_version="1.0",
            ),
        )
    )
    coordinator = FleetDiscoveryBootstrapCoordinator(
        package=AgentPackage(
            "sofia-fleet-agent",
            "1.2.3",
            "a" * 64,
            "approved-wheel",
        ),
        authority=InstallAuthority.NONE,
    )

    result = coordinator.reconcile(discovery)

    assert result.ready_host_ids == ("terra",)
    assert result.operator_host_ids == ()


def test_unknown_candidate_refines_from_stronger_agent_evidence():
    registry = FleetRegistry()
    coordinator = FleetDiscoveryCoordinator(registry)
    coordinator.ingest(
        (
            evidence(
                host_id="newhost.local",
                hostname="newhost.local",
                platform="unknown",
                architecture="unknown",
                source="approved-scope-host-presence",
                trusted_bootstrap_available=False,
            ),
        )
    )

    coordinator.ingest(
        (
            evidence(
                host_id="newhost.local",
                hostname="newhost.local",
                platform="windows",
                architecture="amd64",
                source="mtls-agent-discovery",
                trusted_bootstrap_available=False,
                observed_node_id=UUID(
                    "11111111-2222-3333-4444-555555555555"
                ),
                observed_public_key_sha256="d" * 64,
                observed_endpoint_hostname="newhost.local",
                observed_endpoint_port=7443,
                installed_protocol_version="1.0",
            ),
        )
    )

    host = registry.host("newhost.local")
    assert host is not None
    assert host.platform == "windows"
    assert host.architecture == "amd64"
    assert host.lifecycle is HostLifecycle.CANDIDATE
    assert host.trusted is False
    assert any(tag.startswith("observed-node:") for tag in host.tags)


def test_known_candidate_identity_cannot_be_rewritten_by_discovery():
    registry = FleetRegistry()
    coordinator = FleetDiscoveryCoordinator(registry)
    coordinator.ingest((evidence(platform="linux", architecture="x86_64"),))

    with pytest.raises(ValueError, match="durable Fleet identity"):
        coordinator.ingest(
            (
                evidence(
                    platform="windows",
                    architecture="amd64",
                ),
            )
        )


def test_preapproved_identity_without_verified_capabilities_stays_pending(
    tmp_path,
):
    registry = FleetRegistry()
    node_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    key = "e" * 64
    observation = evidence(
        host_id="Artemis",
        hostname="artemis.local",
        platform="windows",
        architecture="amd64",
        observed_node_id=node_id,
        observed_public_key_sha256=key,
        observed_endpoint_hostname="artemis.local",
        observed_endpoint_port=7443,
        capabilities_verified=False,
    )
    discovery = FleetDiscoveryCoordinator(registry).ingest((observation,))

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
    endpoints.approve(
        ApprovedEndpoint(
            node_id,
            NodeEndpoint(
                "artemis.local",
                7443,
                NodeTransport.HTTPS,
            ),
            "Sparks",
        )
    )
    try:
        result = FleetDiscoveryEnrollmentReconciler(
            enrollment_service=FleetEnrollmentService(registry),
            identity_registry=identities,
            endpoint_policy=endpoints,
        ).reconcile(discovery)
    finally:
        identities.close()
        endpoints.close()

    host = registry.host("Artemis")
    assert host is not None
    assert host.lifecycle is HostLifecycle.CANDIDATE
    assert host.trusted is False
    assert result.pending_host_ids == ("Artemis",)


def test_mtls_evidence_marks_bootstrap_candidate_agent_present():
    candidate = evidence(
        observed_node_id=UUID(
            "11111111-2222-3333-4444-555555555555"
        ),
        observed_public_key_sha256="f" * 64,
        installed_protocol_version="1.0",
        capabilities_verified=True,
        capability_names=("system.inspect", "ops.telemetry"),
    ).bootstrap_candidate()

    assert candidate.agent_present is True


def test_fleet_enrollment_service_requires_exact_sparks_approval():
    registry = FleetRegistry()
    node_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    key = "c" * 64
    candidate = FleetHost(
        host_id="Terra",
        platform="linux",
        architecture="x86_64",
        lifecycle=HostLifecycle.CANDIDATE,
        trusted=False,
        telemetry=None,
        tags=("discovered",),
        node_id=None,
    )
    registry.register_candidate(candidate)
    enrollment = NodeEnrollment(
        DistributedNode(node_id, "Terra"),
        key,
        NOW,
        "Sparks",
    )
    binding = MachineNodeBinding(
        host_id="Terra",
        node_id=node_id,
        verified_at=NOW,
        source="mtls-agent-discovery",
    )
    peer = AuthenticatedPeerEvidence(
        node_id=node_id,
        public_key_sha256=key,
        observed_at=NOW,
        verifier="mtls-agent-discovery",
    )
    service = FleetEnrollmentService(registry)

    with pytest.raises(PermissionError, match="exact Sparks approval"):
        service.enroll(
            candidate,
            binding=binding,
            enrollment=enrollment,
            peer=peer,
            approval=None,
        )

    wrong = FleetEnrollmentApproval(
        approval_id="fleet-enroll-wrong",
        host_id="Other",
        node_id=node_id,
        public_key_sha256=key,
        approved_by="Sparks",
        approved_at=NOW,
    )
    with pytest.raises(PermissionError, match="does not match"):
        service.enroll(
            candidate,
            binding=binding,
            enrollment=enrollment,
            peer=peer,
            approval=wrong,
        )

    approval = FleetEnrollmentApproval(
        approval_id="fleet-enroll-terra",
        host_id="Terra",
        node_id=node_id,
        public_key_sha256=key,
        approved_by="Sparks",
        approved_at=NOW,
    )
    enrolled = service.enroll(
        candidate,
        binding=binding,
        enrollment=enrollment,
        peer=peer,
        approval=approval,
    )

    assert enrolled.lifecycle is HostLifecycle.ENROLLED
    assert enrolled.trusted is True
    assert enrolled.node_id == node_id
