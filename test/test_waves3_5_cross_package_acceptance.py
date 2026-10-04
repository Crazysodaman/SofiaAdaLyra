from datetime import datetime,timezone
from sofia.capability.model import CapabilityRequest, CapabilityResultKind

from sofia.capability import Capability,CapabilitySystem
from sofia.ops import FleetHost,FleetRegistry,HostLifecycle,HostTelemetry,PlacementEngine,WorkloadContract

NOW=datetime.now(timezone.utc)


def test_ops_placement_uses_only_trusted_healthy_hosts():
    telemetry=HostTelemetry(NOW,cpu_percent=5,ram_used_bytes=1,ram_total_bytes=10,storage_free_bytes=100)
    trusted=FleetHost("venus","windows","x86_64",HostLifecycle.HEALTHY,True,telemetry)
    untrusted=FleetHost("candidate","windows","x86_64",HostLifecycle.HEALTHY,False,telemetry)
    work=WorkloadContract("worker","1",("windows",),("x86_64",))
    decision=PlacementEngine().choose(work,(untrusted,trusted))
    assert decision.host_id=="venus"

def test_tool_boundary_preserves_underlying_capability_authority():
    called = []
    system = CapabilitySystem(lambda request: False)
    capability = Capability("system.inspect", "Inspect system")
    system.register(capability, lambda request: called.append(request))
    result = system.execute(CapabilityRequest(capability, {}, None, "inspect system"))
    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None
    assert called == []


def test_general_tool_authority_still_cannot_decommission_machine():
    fleet = FleetRegistry()
    fleet.register_candidate(FleetHost("node", "windows", "x86_64", HostLifecycle.CANDIDATE, True))
    fleet.transition("node", HostLifecycle.ENROLLED)
    fleet.transition("node", HostLifecycle.QUARANTINED)
    fleet.transition("node", HostLifecycle.DRAINING)
    capability = Capability("ops.host.remove", "Remove Fleet host")
    system = CapabilitySystem(lambda request: True)
    system.register(capability, lambda request: fleet.transition(
        request.parameters["host_id"], HostLifecycle.DECOMMISSIONED))
    result = system.execute(CapabilityRequest(capability, {"host_id": "node"}, None, "remove node"))
    assert result.kind is CapabilityResultKind.FAILED
    assert result.error == (
        "Capability execution failed: "
        "final fleet removal requires exact Sparks approval evidence"
    )
    assert fleet.host("node").lifecycle is HostLifecycle.DRAINING
