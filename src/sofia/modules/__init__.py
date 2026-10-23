"""Sofía's module manifest layer: typed validation, trust, health.

Manifest documents found on disk are untrusted candidates. Only the
owner-session registry turns them into verified entries, after checking
the implementation is actually present in authorized codebase inspection
evidence. Discovery, validation, and health projection never execute
candidate code and never grant authority.
"""
from sofia.modules.manifest import (
    ManifestCandidate,
    ModuleManifest,
    ModuleManifestError,
    discover_candidates,
    parse_manifest,
)
from sofia.modules.platform import (
    FakeCapabilitySpec,
    FakePlatformModuleObserver,
    ModuleDescribeObservation,
    ModuleHealthObservation,
    ModuleObservationKind,
    OutcomeObservation,
    OutcomeStatus,
    PlacementMode,
    PlacementObservation,
    PlatformModuleObserver,
)
from sofia.modules.self_model import (
    CapabilityPermissionAspect,
    CapabilitySelfModel,
    Grounding,
    ModuleAwarenessRow,
)
from sofia.modules.proposals import (
    ModuleNeed,
    ModuleProposalRecord,
    ModuleProposalService,
    ModuleProposalStore,
    NeedEvaluation,
    NeedOrigin,
    ProposalAction,
    ProposalStatus,
    ProposalError,
)
from sofia.modules.workshop import (
    WorkshopDevelopmentRequest,
    WorkshopRequestError,
    WorkshopRequestService,
    WorkshopRequestStatus,
    WorkshopRequestStore,
)
from sofia.modules.capability import (
    MODULE_AWARENESS_CAPABILITY,
    ModuleAwarenessCapability,
)
from sofia.modules.registry import (
    ModuleHealth,
    ModuleHealthReport,
    ModuleRegistryError,
    ModuleRegistryService,
    ModuleRegistryStore,
    ModuleRegistration,
    TrustState,
)

__all__ = [
    "ManifestCandidate",
    "ModuleManifest",
    "ModuleManifestError",
    "discover_candidates",
    "parse_manifest",
    "FakeCapabilitySpec",
    "FakePlatformModuleObserver",
    "ModuleDescribeObservation",
    "ModuleHealthObservation",
    "ModuleObservationKind",
    "OutcomeObservation",
    "OutcomeStatus",
    "PlacementMode",
    "PlacementObservation",
    "PlatformModuleObserver",
    "CapabilityPermissionAspect",
    "CapabilitySelfModel",
    "Grounding",
    "ModuleAwarenessRow",
    "ModuleNeed",
    "ProposalError",
    "ModuleProposalRecord",
    "ModuleProposalService",
    "ModuleProposalStore",
    "NeedEvaluation",
    "NeedOrigin",
    "ProposalAction",
    "ProposalStatus",
    "WorkshopDevelopmentRequest",
    "WorkshopRequestError",
    "WorkshopRequestService",
    "WorkshopRequestStatus",
    "WorkshopRequestStore",
    "MODULE_AWARENESS_CAPABILITY",
    "ModuleAwarenessCapability",
    "ModuleHealth",
    "ModuleHealthReport",
    "ModuleRegistryError",
    "ModuleRegistryService",
    "ModuleRegistryStore",
    "ModuleRegistration",
    "TrustState",
]
