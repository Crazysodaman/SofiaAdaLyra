"""Shared hardware supply and module demand contracts."""

from .contract import (
    CapabilityFact,
    CapabilityPredicate,
    CapabilityRequirement,
    CompatibilityAssessment,
    EvidenceClass,
    MatchState,
    PredicateOperator,
    RequirementAlternative,
    ResourceSupply,
    evaluate_resource_requirements,
    requirement_from_document,
    requirement_to_document,
)
from .inventory import (
    HardwareInventoryStore,
    HardwareTelemetryStore,
    InventoryRecord,
)
from .benchmark import (
    BenchmarkCoordinator, BenchmarkExecution, BenchmarkKind,
    BenchmarkMeasurement, IdleAdmission, VerifiedIdleObserver,
    resolve_source_revision,
)

__all__ = [
    "BenchmarkCoordinator", "BenchmarkExecution", "BenchmarkKind",
    "BenchmarkMeasurement", "CapabilityFact", "CapabilityPredicate", "CapabilityRequirement",
    "CompatibilityAssessment", "EvidenceClass", "HardwareInventoryStore",
    "HardwareTelemetryStore", "IdleAdmission", "InventoryRecord", "MatchState", "PredicateOperator",
    "RequirementAlternative", "ResourceSupply",
    "evaluate_resource_requirements", "requirement_from_document",
    "requirement_to_document", "resolve_source_revision", "VerifiedIdleObserver",
]
