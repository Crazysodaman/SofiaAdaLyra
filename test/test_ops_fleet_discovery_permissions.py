from datetime import datetime, timezone

from sofia.capability.model import CapabilityRequest
from sofia.ops.capability import OpsCapabilitySet, OpsToolService
from sofia.ops.discovery import FleetDiscoveryEvidence
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
        discovery_source=source,
    )

    result = service.discover_network()

    assert result["configured"] is True
    assert result["observed"][0]["host_id"] == "printer"
    assert service.host("printer") is None


def test_network_discovery_is_level_one_read_only():
    policy = capability_permission_policy("network.discover")
    assert policy.level is PermissionLevel.OBSERVE_READ
    assert policy.standing_grant_allowed is False
