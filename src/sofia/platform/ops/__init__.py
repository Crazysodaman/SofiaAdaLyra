"""PKG-OPS fleet telemetry, lifecycle and bounded planning.

The package facade resolves its public names lazily: importing an ops
submodule (for example the Core-free backup engine used by the Platform
state foundation) must not import the whole PKG-OPS surface, several parts
of which are Core-host services.
"""
from importlib import import_module

_EXPORTS: dict[str, str] = {
    "HostLifecycle": ".model",
    "HostTelemetry": ".model",
    "FleetHost": ".model",
    "WorkloadContract": ".model",
    "FleetRegistry": ".fleet",
    "FleetRemovalApprovalRequired": ".fleet",
    "FleetRemovalApproval": ".fleet",
    "PlacementDecision": ".placement",
    "PlacementEngine": ".placement",
    "SQLiteTelemetryHistory": ".history",
    "ManagedWorkload": ".workload",
    "StateMode": ".workload",
    "WorkloadInstance": ".workload",
    "WorkloadPhase": ".workload",
    "MigrationPlan": ".workload",
    "MigrationStage": ".workload",
    "DesiredHostState": ".desired",
    "DesiredWorkloadPlacement": ".desired",
    "Drift": ".desired",
    "detect_drift": ".desired",
    "MaintenanceOperation": ".maintenance",
    "MaintenancePolicy": ".maintenance",
    "MaintenanceRequest": ".maintenance",
    "AuthenticatedPeerEvidence": ".enrollment",
    "FleetEnrollmentApproval": ".enrollment",
    "FleetEnrollmentService": ".enrollment",
    "MachineNodeBinding": ".enrollment",
    "BackupEvidence": ".recovery",
    "RecoveryDenied": ".recovery",
    "RecoveryGuard": ".recovery",
    "RestoreVerification": ".recovery",
    "ActivityMode": ".activity",
    "HostActivityObservation": ".activity",
    "HostActivityState": ".activity",
    "HostActivityStore": ".activity",
    "detect_windows_game": ".activity",
    "AgentDiscoveryTarget": ".agent_discovery",
    "CombinedFleetDiscoverySource": ".agent_discovery",
    "MtlsAgentDiscoverySource": ".agent_discovery",
    "ScopedHostPresenceDiscoverySource": ".agent_discovery",
    "ScopedMtlsAgentDiscoverySource": ".agent_discovery",
    "FleetDiscoveryBootstrapCoordinator": ".discovery",
    "FleetDiscoveryBootstrapResult": ".discovery",
    "FleetDiscoveryCoordinator": ".discovery",
    "FleetDiscoveryEvidence": ".discovery",
    "FleetDiscoveryEnrollmentReconciler": ".discovery",
    "FleetDiscoveryEnrollmentResult": ".discovery",
    "FleetDiscoveryResult": ".discovery",
    "FleetDiscoverySource": ".discovery",
    "AgentPackage": ".bootstrap",
    "AgentInstaller": ".bootstrap",
    "BootstrapCandidate": ".bootstrap",
    "BootstrapDisposition": ".bootstrap",
    "BootstrapPlan": ".bootstrap",
    "FleetBootstrapExecutor": ".bootstrap",
    "FleetBootstrapPlanner": ".bootstrap",
    "InstallAuthority": ".bootstrap",
    "InstallReceipt": ".bootstrap",
    "DependencyEvidenceStore": ".dependencies",
    "DependencyHealth": ".dependencies",
    "DependencyObservation": ".dependencies",
    "DependencyRegistry": ".dependencies",
    "DependencyTier": ".dependencies",
    "SoftwareDependency": ".dependencies",
    "default_dependency_registry": ".dependencies",
    "InstallOperation": ".platform_install",
    "InstallOutcome": ".platform_install",
    "OfflineArtifactCache": ".platform_install",
    "PlatformArtifact": ".platform_install",
    "PlatformInstallCoordinator": ".platform_install",
    "PlatformInstallPlan": ".platform_install",
    "PlatformInstallReceipt": ".platform_install",
    "PlatformInstallStore": ".platform_install",
    "PlatformKind": ".platform_install",
    "RecoveryBundle": ".platform_install",
    "OperatorHandoffEvidence": ".state_promotion",
    "OperatorHandoffKind": ".state_promotion",
    "OperatorHandoffReview": ".state_promotion",
    "PendingHomePointer": ".state_promotion",
    "review_operator_handoff": ".state_promotion",
    "ResourceArbiter": ".resources",
    "ResourceObservation": ".resources",
    "ResourceReservation": ".resources",
    "FleetForecast": ".forecast",
    "FleetPressureSample": ".forecast",
    "ForecastAdvice": ".forecast",
    "PressureProjection": ".forecast",
    "deterministic_fleet_forecast": ".forecast",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )
    value = getattr(import_module(target, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))
