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
from .operations import (
    ModuleAttemptEvent,
    ModuleAttemptStatus,
    ModuleCancellationPolicy,
    ModuleOperationCoordinator,
    ModuleOperationRequest,
    ModuleOperationType,
)

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
    "evaluate_module_compatibility", "evaluate_module_readiness",
    "parse_signed_manifest", "validate_dependency_graph",
    "verify_module_package",
]
