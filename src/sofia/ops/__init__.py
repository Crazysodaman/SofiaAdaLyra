"""PKG-OPS fleet telemetry, lifecycle and bounded planning."""
from .model import HostLifecycle,HostTelemetry,FleetHost,WorkloadContract
from .fleet import FleetRegistry,FleetRemovalApprovalRequired
from .placement import PlacementDecision,PlacementEngine
from sofia.ops.fleet import FleetRemovalApproval
from .history import SQLiteTelemetryHistory
from .workload import ManagedWorkload,StateMode,WorkloadInstance,WorkloadPhase
from sofia.ops.workload import MigrationPlan, MigrationStage
from .desired import DesiredHostState,DesiredWorkloadPlacement,Drift,detect_drift
from .maintenance import MaintenanceOperation,MaintenancePolicy,MaintenanceRequest
from .enrollment import AuthenticatedPeerEvidence,FleetEnrollmentApproval,FleetEnrollmentService,MachineNodeBinding
from .recovery import BackupEvidence,RecoveryDenied,RecoveryGuard,RestoreVerification
from .activity import ActivityMode,HostActivityObservation,HostActivityState,HostActivityStore,detect_windows_game
from .agent_discovery import (
    AgentDiscoveryTarget,
    CombinedFleetDiscoverySource,
    MtlsAgentDiscoverySource,
    ScopedHostPresenceDiscoverySource,
    ScopedMtlsAgentDiscoverySource,
)
from .discovery import (
    FleetDiscoveryBootstrapCoordinator,
    FleetDiscoveryBootstrapResult,
    FleetDiscoveryCoordinator,
    FleetDiscoveryEvidence,
    FleetDiscoveryEnrollmentReconciler,
    FleetDiscoveryEnrollmentResult,
    FleetDiscoveryResult,
    FleetDiscoverySource,
)
from .bootstrap import (
    AgentPackage,AgentInstaller,BootstrapCandidate,BootstrapDisposition,BootstrapPlan,
    FleetBootstrapExecutor,FleetBootstrapPlanner,InstallAuthority,InstallReceipt,
)

__all__ = [
    'HostLifecycle',
    'HostTelemetry',
    'FleetHost',
    'WorkloadContract',
    'FleetRegistry',
    'FleetRemovalApprovalRequired',
    'PlacementDecision',
    'PlacementEngine',
    'FleetRemovalApproval',
    'SQLiteTelemetryHistory',
    'ManagedWorkload',
    'StateMode',
    'WorkloadInstance',
    'WorkloadPhase',
    'MigrationPlan',
    'MigrationStage',
    'DesiredHostState',
    'DesiredWorkloadPlacement',
    'Drift',
    'detect_drift',
    'MaintenanceOperation',
    'MaintenancePolicy',
    'MaintenanceRequest',
    'AuthenticatedPeerEvidence',
    'FleetEnrollmentApproval',
    'FleetEnrollmentService',
    'MachineNodeBinding',
    'BackupEvidence',
    'RecoveryDenied',
    'RecoveryGuard',
    'RestoreVerification',
    'ActivityMode',
    'HostActivityObservation',
    'HostActivityState',
    'HostActivityStore',
    'detect_windows_game',
    'AgentPackage',
    'AgentInstaller',
    'BootstrapCandidate',
    'BootstrapDisposition',
    'BootstrapPlan',
    'FleetBootstrapExecutor',
    'FleetBootstrapPlanner',
    'InstallAuthority',
    'InstallReceipt',
    'AgentDiscoveryTarget',
    'CombinedFleetDiscoverySource',
    'MtlsAgentDiscoverySource',
    'ScopedHostPresenceDiscoverySource',
    'ScopedMtlsAgentDiscoverySource',
    'FleetDiscoveryBootstrapCoordinator',
    'FleetDiscoveryBootstrapResult',
    'FleetDiscoveryCoordinator',
    'FleetDiscoveryEvidence',
    'FleetDiscoveryEnrollmentReconciler',
    'FleetDiscoveryEnrollmentResult',
    'FleetDiscoveryResult',
    'FleetDiscoverySource',
]
