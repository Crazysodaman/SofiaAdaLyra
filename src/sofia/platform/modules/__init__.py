"""Platform-owned signed module packaging, lifecycle, and readiness."""

from .compatibility import (
    ModuleCompatibilityReport,
    ModulePlatformTarget,
    evaluate_module_compatibility,
)
from .lifecycle import (
    ModuleChangePlan,
    ModuleInstallPlan,
    ModuleLifecycle,
    ModuleLifecycleAuthorization,
    ModuleLifecycleHealth,
    ModuleLifecycleManager,
    ModuleLifecycleRecord,
    ModuleTransitionReceipt,
)
from .package import (
    DependencyRequirement,
    ModuleMaintenanceProfile,
    ModuleOperationProfile,
    OperationProfileKind,
    PackageManifestError,
    PlacementMode,
    SignedModuleManifest,
    VerifiedModulePackage,
    parse_signed_manifest,
    validate_dependency_graph,
    verify_module_package,
)
from .readiness import (
    ModuleReadinessReport,
    PlatformReadiness,
    ReadinessEvidence,
    ReadinessEvidenceKind,
    ReadinessEvidenceStore,
    evaluate_module_readiness,
)
from .observer import CanonicalPlatformModuleObserver
from .adapters import (
    AdapterFactoryContract,
    AdapterFactoryRegistry,
    AdapterInspection,
    ReviewedAdapterFactory,
    ReviewedModuleAdapter,
)
from .process_worker import (
    RESEARCH_CAPABILITY_ID,
    RESEARCH_COMPONENT_ID,
    RESEARCH_MODULE_ID,
    ModuleProcessError,
    ResearchModuleProcessAdapter,
    ReviewedResearchProcessFactory,
)
from .operations import (
    ModuleAttemptEvent,
    ModuleAttemptStatus,
    ModuleCancellationPolicy,
    ModuleOperationCoordinator,
    ModuleOperationRequest,
    ModuleOperationType,
)
from .control_center import platform_control_center_text

__all__ = [
    "AdapterFactoryContract", "AdapterFactoryRegistry", "AdapterInspection",
    "DependencyRequirement", "ModuleChangePlan", "ModuleCompatibilityReport",
    "ModuleInstallPlan", "ModuleLifecycle", "ModuleLifecycleAuthorization",
    "ModuleLifecycleHealth",
    "ModuleLifecycleManager", "ModuleLifecycleRecord",
    "ModuleTransitionReceipt",
    "ModuleMaintenanceProfile", "ModuleOperationProfile",
    "ModuleAttemptEvent", "ModuleAttemptStatus", "ModuleCancellationPolicy",
    "ModuleOperationCoordinator", "ModuleOperationRequest",
    "ModuleOperationType",
    "ModulePlatformTarget", "ModuleReadinessReport", "OperationProfileKind",
    "PackageManifestError", "PlacementMode", "PlatformReadiness",
    "ReadinessEvidence", "ReadinessEvidenceKind", "ReadinessEvidenceStore",
    "SignedModuleManifest", "VerifiedModulePackage",
    "CanonicalPlatformModuleObserver",
    "ReviewedAdapterFactory", "ReviewedModuleAdapter",
    "ModuleProcessError", "ResearchModuleProcessAdapter",
    "ReviewedResearchProcessFactory", "RESEARCH_CAPABILITY_ID",
    "RESEARCH_COMPONENT_ID", "RESEARCH_MODULE_ID",
    "evaluate_module_compatibility", "evaluate_module_readiness",
    "parse_signed_manifest", "validate_dependency_graph",
    "verify_module_package",
    "platform_control_center_text",
]
