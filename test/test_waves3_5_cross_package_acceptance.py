from datetime import datetime,timezone
from pathlib import Path
import pytest

from sofia.capability import Capability,CapabilitySystem
from sofia.integrate import (
    AdapterManifest,CapabilitySystemAdapter,GovernedAdapterRegistry,InvocationContext,
    JsonlReceiptLedger,SideEffectClass,ToolInvocation,
)
from sofia.ops import FleetHost,FleetRegistry,HostLifecycle,HostTelemetry,PlacementEngine,WorkloadContract

NOW=datetime.now(timezone.utc)

def test_governed_integrate_cannot_override_underlying_capability_authority(tmp_path:Path):
    system=CapabilitySystem(lambda request: False)
    system.register(Capability("system.inspect","inspect system"),lambda request: {"hostname":"venus"})
    adapter=CapabilitySystemAdapter(system,tool_id="system.inspect.adapter",capability_name="system.inspect")
    governed=GovernedAdapterRegistry(JsonlReceiptLedger(tmp_path/"receipts.jsonl"))
    governed.register(adapter,enabled=True)
    receipt=governed.invoke(
        ToolInvocation("cap-1","system.inspect.adapter",{},True),
        InvocationContext("Sparks",frozenset({"system.inspect"}),frozenset({SideEffectClass.READ_ONLY})),
    )
    assert receipt.succeeded
    assert receipt.output["kind"]=="unauthorized"
    assert receipt.output["evidence"] is None

def test_ops_placement_uses_only_trusted_healthy_hosts():
    telemetry=HostTelemetry(NOW,cpu_percent=5,ram_used_bytes=1,ram_total_bytes=10,storage_free_bytes=100)
    trusted=FleetHost("venus","windows","x86_64",HostLifecycle.HEALTHY,True,telemetry)
    untrusted=FleetHost("candidate","windows","x86_64",HostLifecycle.HEALTHY,False,telemetry)
    work=WorkloadContract("worker","1",("windows",),("x86_64",))
    decision=PlacementEngine().choose(work,(untrusted,trusted))
    assert decision.host_id=="venus"

def test_general_tool_authority_still_cannot_decommission_machine(tmp_path:Path):
    fleet=FleetRegistry()
    fleet.register_candidate(FleetHost("node","windows","x86_64",HostLifecycle.CANDIDATE,True))
    fleet.transition("node",HostLifecycle.ENROLLED)
    fleet.transition("node",HostLifecycle.QUARANTINED)
    fleet.transition("node",HostLifecycle.DRAINING)

    class RemovalAdapter:
        manifest=AdapterManifest(
            "ops.host.remove","1","PKG-OPS",SideEffectClass.DESTRUCTIVE,
            ("fleet.remove",),{"type":"object","required":["host_id"]},{"type":"object"},
        )
        def invoke(self,arguments):
            fleet.transition(arguments["host_id"],HostLifecycle.DECOMMISSIONED)
            return {"removed":True}

    reg=GovernedAdapterRegistry(JsonlReceiptLedger(tmp_path/"receipts.jsonl"))
    reg.register(RemovalAdapter(),enabled=True)
    receipt=reg.invoke(
        ToolInvocation("remove-1","ops.host.remove",{"host_id":"node"},True),
        InvocationContext("Sparks",frozenset({"fleet.remove"}),frozenset({SideEffectClass.DESTRUCTIVE})),
    )
    assert not receipt.succeeded
    assert "FleetRemovalApprovalRequired" in receipt.error
    assert fleet.host("node").lifecycle is HostLifecycle.DRAINING

def test_failed_destructive_attempt_is_durably_receipted(tmp_path:Path):
    class Fail:
        manifest=AdapterManifest("fail","1","tests",SideEffectClass.DESTRUCTIVE,("x",),{"type":"object"},{"type":"object"})
        def invoke(self,arguments): raise RuntimeError("boom")
    path=tmp_path/"receipts.jsonl"; reg=GovernedAdapterRegistry(JsonlReceiptLedger(path)); reg.register(Fail(),enabled=True)
    receipt=reg.invoke(ToolInvocation("fail-1","fail",{},True),
        InvocationContext("Sparks",frozenset({"x"}),frozenset({SideEffectClass.DESTRUCTIVE})))
    assert not receipt.succeeded
    record=JsonlReceiptLedger(path).get("fail-1")
    assert record is not None and not record.succeeded
