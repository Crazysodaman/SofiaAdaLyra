"""HNF-01 through HNF-03 typed resource and inventory regressions."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.platform.ops.capability import OpsToolService
from sofia.platform.ops.discovery import FleetDiscoveryEvidence
from sofia.platform.ops.model import FleetHost, HostLifecycle
from sofia.platform.ops.model import HostTelemetry
from sofia.platform.modules import (
    ModulePlatformTarget,
    OperationProfileKind,
    evaluate_module_compatibility,
    parse_signed_manifest,
)
from test.test_module_package_v1 import manifest
from sofia.platform.resources import (
    CapabilityFact,
    CapabilityPredicate,
    CapabilityRequirement,
    EvidenceClass,
    HardwareInventoryStore,
    HardwareTelemetryStore,
    PredicateOperator,
    RequirementAlternative,
    ResourceSupply,
    evaluate_resource_requirements,
)


NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
GIB = 1024 ** 3


def fact(key, value, *, resource="host:test", unit=None,
         evidence=EvidenceClass.OBSERVED, expires=True):
    return CapabilityFact(
        key, value, unit, "node:7f21", resource, evidence,
        f"evidence:{resource.replace(':', '-')}", NOW,
        NOW + timedelta(minutes=5) if expires else None, True,
    )


def predicate(key, operator, expected, *, unit=None, upper=None):
    return CapabilityPredicate(
        key, operator, expected, upper=upper, unit=unit,
        maximum_age_seconds=300,
    )


def requirement(identifier, *predicates, preferred=False):
    return CapabilityRequirement(
        identifier, (RequirementAlternative(tuple(predicates)),), preferred,
    )


def supply(*facts, enrolled=True, trusted=True):
    return ResourceSupply("node:7f21", enrolled, trusted, 3, tuple(facts))


def test_cpu_only_supply_matches_without_inventing_gpu() -> None:
    result = evaluate_resource_requirements(
        supply(
            fact("cpu.arch", "x86_64"),
            fact("cpu.cores.allocatable", 8, unit="count"),
            fact("memory.allocatable_bytes", 16 * GIB, unit="bytes"),
        ),
        (requirement("cpu-runtime",
            predicate("cpu.arch", PredicateOperator.IN_SET, ("x86_64", "arm64")),
            predicate("cpu.cores.allocatable", PredicateOperator.MINIMUM, 4, unit="count"),
        ),), now=NOW,
    )
    assert result.compatible is True
    assert result.matched == ("cpu-runtime",)


def test_two_gpu_vram_is_never_combined_across_devices() -> None:
    requirement_value = requirement(
        "single-gpu",
        predicate("gpu.backend", PredicateOperator.CONTAINS, "cuda"),
        predicate("gpu.vram.allocatable_bytes", PredicateOperator.MINIMUM, 10 * GIB, unit="bytes"),
    )
    result = evaluate_resource_requirements(
        supply(
            fact("gpu.backend", ("cuda",), resource="gpu:0"),
            fact("gpu.vram.allocatable_bytes", 6 * GIB, resource="gpu:0", unit="bytes"),
            fact("gpu.backend", ("cuda",), resource="gpu:1"),
            fact("gpu.vram.allocatable_bytes", 6 * GIB, resource="gpu:1", unit="bytes"),
        ), (requirement_value,), now=NOW,
    )
    assert result.compatible is False
    assert result.rejected[0][0] == "single-gpu"


def test_missing_and_stale_capacity_are_unknown_not_zero() -> None:
    required = requirement("gpu-memory",
        predicate("gpu.vram.allocatable_bytes", PredicateOperator.MINIMUM, 1, unit="bytes"))
    missing = evaluate_resource_requirements(supply(), (required,), now=NOW)
    stale_fact = replace(
        fact("gpu.vram.allocatable_bytes", 8 * GIB, resource="gpu:0", unit="bytes"),
        observed_at=NOW - timedelta(hours=1), expires_at=NOW - timedelta(minutes=30),
    )
    stale = evaluate_resource_requirements(supply(stale_fact), (required,), now=NOW)
    assert missing.unknown[0][0] == "gpu-memory"
    assert stale.unknown[0][0] == "gpu-memory"


def test_unenrolled_or_untrusted_host_cannot_be_compatible() -> None:
    result = evaluate_resource_requirements(
        supply(fact("cpu.arch", "x86_64"), enrolled=False, trusted=False),
        (), now=NOW,
    )
    assert result.compatible is False
    assert {item[0] for item in result.rejected} == {"host.enrollment", "host.trust"}


def test_requirement_alternatives_and_preference_do_not_override_hard_limits() -> None:
    alternative = CapabilityRequirement("backend", (
        RequirementAlternative((predicate("gpu.backend", PredicateOperator.CONTAINS, "cuda"),)),
        RequirementAlternative((predicate("gpu.backend", PredicateOperator.CONTAINS, "rocm"),)),
    ))
    preference = requirement("fast-network",
        predicate("network.bandwidth_bps", PredicateOperator.MINIMUM, 10_000, unit="bps"),
        preferred=True)
    result = evaluate_resource_requirements(
        supply(fact("gpu.backend", ("rocm",), resource="gpu:0")),
        (alternative, preference), now=NOW,
    )
    assert result.compatible is True
    assert result.matched == ("backend",)
    assert result.preferred_unmet == ("fast-network",)


def test_inventory_discovery_cannot_self_enroll_and_preserves_revisions(canonical_state_path) -> None:
    valid_refs = {"enrollment:7f21"}
    store = HardwareInventoryStore(
        canonical_state_path,
        enrollment_verifier=lambda host, ref, now: host == "node:7f21" and ref in valid_refs,
    )
    observed = (fact("cpu.arch", "x86_64", expires=False),)
    discovered = store.record(
        host_id="node:7f21", display_name="Any Display Name", facts=observed,
        observed_at=NOW,
    )
    assert discovered.enrolled is False
    with pytest.raises(PermissionError, match="authoritative"):
        store.record(
            host_id="node:7f21", display_name="Renamed", facts=observed,
            observed_at=NOW, enrolled=True, trusted=True,
            enrollment_ref="enrollment:forged", expected_revision=1,
        )
    enrolled = store.record(
        host_id="node:7f21", display_name="Renamed", facts=observed,
        observed_at=NOW, enrolled=True, trusted=True,
        enrollment_ref="enrollment:7f21", expected_revision=1,
    )
    changed = store.record(
        host_id="node:7f21", display_name="Renamed", facts=(
            fact("cpu.arch", "arm64", expires=False),
        ), observed_at=NOW + timedelta(minutes=1), enrolled=True, trusted=True,
        enrollment_ref="enrollment:7f21", expected_revision=2,
    )
    assert (enrolled.revision, changed.revision) == (2, 3)
    assert tuple(item.revision for item in store.history("node:7f21")) == (3, 2, 1)


def test_inventory_same_semantics_does_not_create_revision(canonical_state_path) -> None:
    store = HardwareInventoryStore(
        canonical_state_path, enrollment_verifier=lambda *_: False,
    )
    first = store.record(
        host_id="node:7f21", display_name="Worker", facts=(
            fact("cpu.arch", "x86_64", expires=False),
        ), observed_at=NOW,
    )
    refreshed = store.record(
        host_id="node:7f21", display_name="Worker", facts=(replace(
            first.facts[0], observed_at=NOW + timedelta(minutes=1),
        ),), observed_at=NOW + timedelta(minutes=1), expected_revision=1,
    )
    assert refreshed.revision == 1


def test_live_telemetry_is_bounded_and_survives_store_restart(canonical_state_path) -> None:
    store = HardwareTelemetryStore(canonical_state_path, retention_per_host=8)
    for index in range(10):
        moment = NOW + timedelta(seconds=index)
        item = replace(
            fact("cpu.utilization_percent", float(index), unit="percent"),
            observed_at=moment, expires_at=moment + timedelta(minutes=2),
        )
        store.record(
            host_id="node:7f21", facts=(item,), source_ref="agent:7f21",
            observed_at=moment,
        )
    restarted = HardwareTelemetryStore(canonical_state_path, retention_per_host=8)
    assert restarted.latest("node:7f21")[0].value == 9.0
    with restarted._connect() as db:
        count = db.execute(
            "SELECT COUNT(*) FROM platform_hardware_telemetry WHERE host_id=?",
            ("node:7f21",),
        ).fetchone()[0]
    assert count == 8


def test_capability_units_and_nonfinite_values_fail_closed() -> None:
    with pytest.raises(ValueError, match="requires unit bytes"):
        fact("memory.allocatable_bytes", 100, unit="mib")
    with pytest.raises(ValueError, match="finite"):
        fact("cpu.utilization_percent", float("nan"), unit="percent")
    with pytest.raises(ValueError, match="manufacturer source"):
        fact(
            "cpu.arch", "x86_64", evidence=EvidenceClass.MANUFACTURER,
        )


def test_production_ops_discovery_projects_untrusted_inventory(canonical_state_path) -> None:
    service = OpsToolService(canonical_state_path)
    observation = FleetDiscoveryEvidence(
        "worker:any-name", "Owner Editable Name", "linux", "x86_64", NOW,
        "configured-subnet", True,
    )
    service.registry.register_candidate(FleetHost(
        observation.host_id, observation.platform, observation.architecture,
        HostLifecycle.CANDIDATE, False,
    ))

    record = service.record_discovery_inventory(observation)
    projected = service.resource_supply(observation.host_id)

    assert record.display_name == "Owner Editable Name"
    assert record.enrolled is False
    assert projected is not None and projected.trusted is False
    assert {item.key for item in projected.facts} == {"os.family", "cpu.arch"}


def test_manifest_v2_signs_profile_resource_requirements_and_round_trips() -> None:
    from dataclasses import replace
    original = manifest((("module.py", "0" * 64),))
    required = requirement(
        "single-gpu",
        predicate("gpu.backend", PredicateOperator.CONTAINS, "cuda"),
        predicate("gpu.vram.allocatable_bytes", PredicateOperator.MINIMUM, 8 * GIB, unit="bytes"),
    )
    upgraded = replace(
        original,
        schema_version=2,
        profiles=(replace(original.profiles[0], resource_requirements=(required,)),),
    )
    document = upgraded.unsigned_document()
    document["signature_b64"] = upgraded.signature_b64

    parsed = parse_signed_manifest(document)

    assert parsed == upgraded
    assert parsed.package_identity_digest() == upgraded.package_identity_digest()
    assert "resource_requirements" not in original.unsigned_document()["profiles"][0]
    document["profiles"][0]["resource_requirements"][0]["preferred"] = "false"
    with pytest.raises(ValueError, match="invalid typed values"):
        parse_signed_manifest(document)


def test_module_compatibility_uses_typed_per_device_supply() -> None:
    from dataclasses import replace
    original = manifest((("module.py", "0" * 64),))
    required = requirement(
        "single-gpu",
        predicate("gpu.backend", PredicateOperator.CONTAINS, "cuda"),
        predicate("gpu.vram.allocatable_bytes", PredicateOperator.MINIMUM, 10 * GIB, unit="bytes"),
    )
    upgraded = replace(
        original, schema_version=2,
        profiles=(replace(original.profiles[0], resource_requirements=(required,)),),
    )
    split_vram = supply(
        fact("gpu.backend", ("cuda",), resource="gpu:0"),
        fact("gpu.vram.allocatable_bytes", 6 * GIB, resource="gpu:0", unit="bytes"),
        fact("gpu.backend", ("cuda",), resource="gpu:1"),
        fact("gpu.vram.allocatable_bytes", 6 * GIB, resource="gpu:1", unit="bytes"),
    )
    target = ModulePlatformTarget(
        "linux-x86_64", "1.5.0", (),
        (("cpu_millis", 200), ("ram_mib", 256)),
        ("subprocess-restricted",), split_vram,
    )

    report = evaluate_module_compatibility(
        upgraded, profile=OperationProfileKind.OBSERVE, target=target, now=NOW,
    )

    assert report.compatible is False
    assert any("single-gpu" in reason for reason in report.reasons)


def test_authenticated_legacy_telemetry_projects_one_gpu_without_aggregation(
    canonical_state_path,
) -> None:
    service = OpsToolService(canonical_state_path)
    host_id = "node:7f21"
    service.registry.register_candidate(FleetHost(
        host_id, "linux", "x86_64", HostLifecycle.CANDIDATE, False,
    ))
    service.registry.authenticate_candidate(host_id, uuid4())
    service.registry.transition(host_id, HostLifecycle.ENROLLED)
    observation = HostTelemetry(
        NOW, cpu_percent=10.0, ram_used_bytes=4 * GIB,
        ram_total_bytes=16 * GIB, gpu_percent=20.0,
        vram_used_bytes=2 * GIB, vram_total_bytes=12 * GIB,
        storage_free_bytes=30 * GIB, temperature_c=55.0, throttled=False,
    )

    service.record_resource_telemetry(
        host_id, observation, source_ref="fleet-agent:7f21", authenticated=True,
    )

    facts = service.resource_telemetry.latest(host_id)
    vram = [item for item in facts if item.key == "gpu.vram.allocatable_bytes"]
    assert len(vram) == 1
    assert vram[0].value == 10 * GIB
    assert vram[0].resource_id == "gpu:node:7f21:0"
    assert vram[0].verified is True
