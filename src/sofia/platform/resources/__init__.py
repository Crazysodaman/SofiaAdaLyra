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

__all__ = [
    "CapabilityFact", "CapabilityPredicate", "CapabilityRequirement",
    "CompatibilityAssessment", "EvidenceClass", "HardwareInventoryStore",
    "HardwareTelemetryStore", "InventoryRecord", "MatchState", "PredicateOperator",
    "RequirementAlternative", "ResourceSupply",
    "evaluate_resource_requirements", "requirement_from_document",
    "requirement_to_document",
]
