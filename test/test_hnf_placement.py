"""HNF-07 hardware-neutral typed placement regressions."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sofia.platform.ops import (
    ActivityMode, FleetHost, HostActivityObservation, HostActivityState,
    HostLifecycle, PlacementEngine,
)
from sofia.platform.ops.capability import OpsToolService
from sofia.platform.resources import (
    CapabilityFact, CapabilityPredicate, CapabilityRequirement, EvidenceClass,
    PredicateOperator, RequirementAlternative, ResourceSupply,
    requirement_to_document,
)


NOW = datetime.now(timezone.utc)
GIB = 1024 ** 3


def fact(host, key, value, *, resource=None, unit=None, observed_at=None):
    moment = observed_at or NOW
    return CapabilityFact(
        key, value, unit, host, resource or f"host:{host}",
        EvidenceClass.OBSERVED, f"agent:{host}", moment,
        moment + timedelta(minutes=2), True,
    )


def supply(host, *facts, parent=None):
    return ResourceSupply(host, True, True, 1, tuple(facts), parent)


def requirement(identifier, *predicates):
    return CapabilityRequirement(
        identifier, (RequirementAlternative(tuple(predicates)),),
    )


def minimum(key, value, unit=None):
    return CapabilityPredicate(
        key, PredicateOperator.MINIMUM, value, unit=unit,
        maximum_age_seconds=120,
    )


def equals(key, value):
    return CapabilityPredicate(
        key, PredicateOperator.EQUALS, value, maximum_age_seconds=120,
    )


def idle(host):
    return HostActivityState(
        host, ActivityMode.AUTO, ActivityMode.IDLE, NOW, "agent:activity",
    )


def test_host_display_names_never_control_typed_selection() -> None:
    requirements = (requirement(
        "cpu", equals("cpu.arch", "x86_64"),
        minimum("memory.allocatable_bytes", 4 * GIB, "bytes"),
    ),)
    smaller = supply(
        "node:92f1", fact("node:92f1", "cpu.arch", "x86_64"),
        fact("node:92f1", "memory.allocatable_bytes", 8 * GIB, unit="bytes"),
    )
    larger = supply(
        "node:11ab", fact("node:11ab", "cpu.arch", "x86_64"),
        fact("node:11ab", "memory.allocatable_bytes", 16 * GIB, unit="bytes"),
    )
    decision = PlacementEngine().choose_resources(
        workload_id="render", supplies=(smaller, larger), requirements=requirements,
        activities={item.host_id: idle(item.host_id) for item in (smaller, larger)},
        benchmark_scores={"node:92f1": 1.0, "node:11ab": 2.0}, now=NOW,
    )
    assert decision.host_id == "node:11ab"
    assert "venus" not in repr(decision).casefold()
    assert "artemis" not in repr(decision).casefold()


def test_benchmark_never_overrides_hard_resource_constraint() -> None:
    requirements = (requirement(
        "memory", minimum("memory.allocatable_bytes", 8 * GIB, "bytes"),
    ),)
    insufficient = supply(
        "node:fast", fact("node:fast", "memory.allocatable_bytes", 4 * GIB, unit="bytes"),
    )
    eligible = supply(
        "node:eligible", fact("node:eligible", "memory.allocatable_bytes", 8 * GIB, unit="bytes"),
    )
    decision = PlacementEngine().choose_resources(
        workload_id="compile", supplies=(insufficient, eligible), requirements=requirements,
        activities={"node:fast": idle("node:fast"), "node:eligible": idle("node:eligible")},
        benchmark_scores={"node:fast": 1_000_000.0, "node:eligible": 1.0}, now=NOW,
    )
    assert decision.host_id == "node:eligible"
    assert dict(decision.rejected)["node:fast"]


def test_unknown_or_busy_worker_fails_closed() -> None:
    required = (requirement(
        "memory", minimum("memory.allocatable_bytes", 1, "bytes"),
    ),)
    unknown = supply("node:unknown")
    busy = supply(
        "node:busy", fact("node:busy", "memory.allocatable_bytes", GIB, unit="bytes"),
    )
    activities = {
        "node:unknown": idle("node:unknown"),
        "node:busy": HostActivityState(
            "node:busy", ActivityMode.AUTO, ActivityMode.GAMING, NOW, "agent:activity",
        ),
    }
    decision = PlacementEngine().choose_resources(
        workload_id="background", supplies=(unknown, busy), requirements=required,
        activities=activities, now=NOW,
    )
    assert decision.host_id is None
    assert set(dict(decision.rejected)) == {"node:unknown", "node:busy"}


def test_vm_and_parent_resources_are_evaluated_independently() -> None:
    required = (requirement(
        "memory", minimum("memory.allocatable_bytes", 10 * GIB, "bytes"),
    ),)
    parent = supply(
        "node:physical", fact("node:physical", "memory.allocatable_bytes", 6 * GIB, unit="bytes"),
    )
    guest = supply(
        "node:guest", fact("node:guest", "memory.allocatable_bytes", 6 * GIB, unit="bytes"),
        parent="node:physical",
    )
    decision = PlacementEngine().choose_resources(
        workload_id="large", supplies=(parent, guest), requirements=required,
        activities={"node:physical": idle("node:physical"), "node:guest": idle("node:guest")},
        now=NOW,
    )
    assert decision.host_id is None


def test_production_ops_uses_typed_inventory_and_not_host_names(
    canonical_state_path,
) -> None:
    observed_at = datetime.now(timezone.utc)
    service = OpsToolService(canonical_state_path)
    node_id = uuid4()
    service.registry.register_candidate(FleetHost(
        "node:portable", "unknown", "unknown", HostLifecycle.CANDIDATE, False,
    ))
    service.registry.refine_candidate_identity(
        "node:portable", platform="linux", architecture="x86_64",
    )
    service.registry.authenticate_candidate("node:portable", node_id)
    service.registry.transition("node:portable", HostLifecycle.ENROLLED)
    service.registry.transition("node:portable", HostLifecycle.HEALTHY)
    service.hardware_inventory.record(
        host_id="node:portable", display_name="Owner Can Rename This", facts=(
            fact("node:portable", "os.family", "linux", observed_at=observed_at),
            fact("node:portable", "cpu.arch", "x86_64", observed_at=observed_at),
            fact(
                "node:portable", "memory.allocatable_bytes", 12 * GIB,
                unit="bytes", observed_at=observed_at,
            ),
        ), observed_at=observed_at, enrolled=True, trusted=True,
        enrollment_ref=f"fleet-node:{node_id}",
    )
    service.activity.record(HostActivityObservation(
        "node:portable", ActivityMode.IDLE, observed_at, "authenticated-agent",
    ))
    requirements = (
        requirement("os", equals("os.family", "linux")),
        requirement("memory", minimum("memory.allocatable_bytes", 8 * GIB, "bytes")),
    )
    decision = service.choose_placement({
        "workload_id": "portable-work", "version": "1",
        "supported_platforms": ["linux"],
        "supported_architectures": ["x86_64"],
        "resource_requirements": [
            requirement_to_document(item) for item in requirements
        ],
    })
    assert decision["host_id"] == "node:portable"
    assert decision["eligible_hosts"] == ("node:portable",)
