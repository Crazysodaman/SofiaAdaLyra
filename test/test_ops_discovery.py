from datetime import datetime, timezone

import pytest

from sofia.ops import (
    FleetDiscoveryCoordinator,
    FleetDiscoveryEvidence,
    FleetRegistry,
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
