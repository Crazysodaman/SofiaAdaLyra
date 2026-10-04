from datetime import datetime, timezone
from sofia.capability import Capability, CapabilitySystem
from sofia.capability.model import CapabilityRequest, CapabilityResultKind

from sofia.dev import ChangeProposal, ReviewState, inspect
from sofia.knowledge import KnowledgeDocument, KnowledgeFact, KnowledgeStore, SourceKind
from sofia.ops import FleetHost, FleetRegistry, HostLifecycle, HostTelemetry, PlacementEngine, WorkloadContract




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










def test_relocated_embodiment_baseline_remains_protected_from_dev_changes():
    proposal = ChangeProposal(
        "baseline-move", "a" * 40,
        ("src/sofia/embodiment/avatar.json", "src/sofia/embodiment/model.py"),
        ("reviewed-source",), "inspect baseline and model", "run package gate", "revert checkpoint",
    )
    findings = inspect(proposal)
    assert findings[0].state is ReviewState.BLOCKED_PROTECTED
    assert findings[1].state is ReviewState.REQUIRES_REVIEW

def _placement_system(hosts, *, authorized=True):
    system = CapabilitySystem(lambda request: authorized)
    capability = Capability("ops.placement.choose", "Choose a trusted healthy host")
    def place(request):
        arguments = request.parameters
        workload = WorkloadContract(arguments["workload_id"], "1",
                                    tuple(arguments["supported_platforms"]),
                                    tuple(arguments["supported_architectures"]))
        decision = PlacementEngine().choose(workload, hosts)
        return {"workload_id": decision.workload_id, "host_id": decision.host_id}
    system.register(capability, place)
    return system, CapabilityRequest(capability,
        {"workload_id": "worker", "supported_platforms": ["windows"],
         "supported_architectures": ["x86_64"]}, None, "inspect placement")


def test_ops_placement_uses_canonical_capability_boundary():
    system, request = _placement_system((_healthy_host(),))
    result = system.execute(request)
    assert result.kind is CapabilityResultKind.SUCCESS
    assert result.evidence == {"workload_id": "worker", "host_id": "venus"}


def test_capability_still_blocks_unauthorized_ops_tool():
    system, request = _placement_system((_healthy_host(),), authorized=False)
    result = system.execute(request)
    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert result.evidence is None


def test_ops_trust_boundary_survives_tool_layer():
    untrusted = FleetHost("candidate", "windows", "x86_64", HostLifecycle.ENROLLED,
                         False, _healthy_host().telemetry)
    system, request = _placement_system((untrusted,))
    result = system.execute(request)
    assert result.kind is CapabilityResultKind.SUCCESS
    assert result.evidence["host_id"] is None


def test_machine_removal_cannot_be_smuggled_through_general_tool_authority():
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
