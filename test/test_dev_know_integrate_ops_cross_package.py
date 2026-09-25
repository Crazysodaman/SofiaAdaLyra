from datetime import datetime, timezone
import pytest

from sofia.dev import ChangeProposal, ReviewState, inspect
from sofia.integrate import AdapterManifest, AdapterRegistry, SideEffectClass, ToolInvocation
from sofia.knowledge import KnowledgeDocument, KnowledgeFact, KnowledgeStore, SourceKind
from sofia.ops import FleetHost, FleetRegistry, HostLifecycle, HostTelemetry, PlacementEngine, WorkloadContract


class PlacementAdapter:
    manifest = AdapterManifest(
        "ops.placement.choose", "1", "PKG-OPS", SideEffectClass.READ_ONLY,
        ("fleet.inspect",), {}, {}
    )

    def __init__(self, hosts):
        self._hosts = hosts

    def invoke(self, arguments):
        workload = WorkloadContract(
            arguments["workload_id"], "1",
            tuple(arguments["supported_platforms"]),
            tuple(arguments["supported_architectures"]),
        )
        decision = PlacementEngine().choose(workload, self._hosts)
        return {"workload_id": decision.workload_id, "host_id": decision.host_id}


def _healthy_host(host_id="venus", cpu=10):
    now = datetime.now(timezone.utc)
    return FleetHost(
        host_id, "windows", "x86_64", HostLifecycle.HEALTHY, True,
        HostTelemetry(now, cpu_percent=cpu, ram_used_bytes=4, ram_total_bytes=16, storage_free_bytes=100),
    )


def test_knowledge_provenance_can_anchor_dev_proposal():
    now = datetime.now(timezone.utc)
    store = KnowledgeStore()
    document = KnowledgeDocument("doc-1", SourceKind.REPOSITORY, "repo://src/sofia/x.py", "abc123", now, "hash")
    store.register_document(document)
    fact = KnowledgeFact("fact-1", "doc-1", "implementation requires bounded adapter", "L10-L20", now)
    store.record_fact(fact)

    proposal = ChangeProposal(
        "proposal-1", "a" * 40, ("src/sofia/integrate/example.py",),
        (fact.fact_id,), "add bounded adapter", "run focused tests", "revert commit",
    )
    findings = inspect(proposal)
    assert store.fact(proposal.source_evidence_ids[0]) == fact
    assert findings[0].state is ReviewState.REQUIRES_REVIEW


def test_ops_is_exposed_through_typed_integrate_adapter():
    registry = AdapterRegistry()
    registry.register(PlacementAdapter((_healthy_host(),)))
    receipt = registry.invoke(ToolInvocation(
        "invoke-1", "ops.placement.choose",
        {"workload_id": "worker", "supported_platforms": ["windows"], "supported_architectures": ["x86_64"]},
        True,
    ))
    assert receipt.succeeded
    assert receipt.output == {"workload_id": "worker", "host_id": "venus"}


def test_integrate_still_blocks_unauthorized_ops_tool():
    registry = AdapterRegistry()
    registry.register(PlacementAdapter((_healthy_host(),)))
    with pytest.raises(PermissionError):
        registry.invoke(ToolInvocation(
            "invoke-2", "ops.placement.choose",
            {"workload_id": "worker", "supported_platforms": ["windows"], "supported_architectures": ["x86_64"]},
            False,
        ))


def test_ops_trust_boundary_survives_tool_layer():
    untrusted = FleetHost("candidate", "windows", "x86_64", HostLifecycle.ENROLLED, False, _healthy_host().telemetry)
    registry = AdapterRegistry()
    registry.register(PlacementAdapter((untrusted,)))
    receipt = registry.invoke(ToolInvocation(
        "invoke-3", "ops.placement.choose",
        {"workload_id": "worker", "supported_platforms": ["windows"], "supported_architectures": ["x86_64"]},
        True,
    ))
    assert receipt.succeeded
    assert receipt.output["host_id"] is None


def test_machine_removal_cannot_be_smuggled_through_general_tool_authority():
    fleet = FleetRegistry()
    fleet.register_candidate(FleetHost("node", "windows", "x86_64", HostLifecycle.CANDIDATE, True))
    fleet.transition("node", HostLifecycle.ENROLLED)
    fleet.transition("node", HostLifecycle.QUARANTINED)
    fleet.transition("node", HostLifecycle.DRAINING)

    class RemovalAdapter:
        manifest = AdapterManifest("ops.host.remove", "1", "PKG-OPS", SideEffectClass.DESTRUCTIVE, ("fleet.remove",), {}, {})
        def invoke(self, arguments):
            return fleet.transition(arguments["host_id"], HostLifecycle.DECOMMISSIONED)

    registry = AdapterRegistry()
    registry.register(RemovalAdapter())
    receipt = registry.invoke(ToolInvocation("invoke-4", "ops.host.remove", {"host_id": "node"}, True))
    assert not receipt.succeeded
    assert "FleetRemovalApprovalRequired" in receipt.error
    assert fleet.host("node").lifecycle is HostLifecycle.DRAINING
