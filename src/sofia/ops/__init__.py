"""PKG-OPS fleet telemetry, lifecycle, orchestration and failover primitives."""
from .model import HostLifecycle,HostTelemetry,FleetHost,WorkloadContract,WorkloadState
from .fleet import FleetRegistry,FleetRemovalApprovalRequired
from .placement import PlacementDecision,PlacementEngine
from .approval import FleetRemovalApproval
from .history import TelemetryHistory
from .lease import AuthorityLease,LeaseTable,SplitBrainRisk
from .durable_lease import JsonLeaseTable
from .workload import ManagedWorkload,StateMode,WorkloadInstance,WorkloadPhase
from .migration import MigrationCoordinator,MigrationPlan,MigrationStage
from .failover import FailureDomain,PromotionDenied,PromotionEvidence,PromotionGuard
from .desired import DesiredHostState,DesiredWorkloadPlacement,Drift,detect_drift
from .maintenance import MaintenanceOperation,MaintenancePolicy,MaintenanceRequest
from .enrollment import AuthenticatedPeerEvidence,FleetEnrollmentService,MachineNodeBinding
from .recovery import BackupEvidence,HostUpdateAssignment,RecoveryDenied,RecoveryGuard,RestoreVerification,UpdatePlanner,UpdateRing
__all__=["HostLifecycle","HostTelemetry","FleetHost","WorkloadContract","WorkloadState","FleetRegistry","FleetRemovalApprovalRequired","PlacementDecision","PlacementEngine","FleetRemovalApproval","TelemetryHistory","AuthorityLease","LeaseTable","SplitBrainRisk","ManagedWorkload","StateMode","WorkloadInstance","WorkloadPhase","MigrationCoordinator","MigrationPlan","MigrationStage","FailureDomain","PromotionDenied","PromotionEvidence","PromotionGuard","DesiredHostState","DesiredWorkloadPlacement","Drift","detect_drift","MaintenanceOperation","MaintenancePolicy","MaintenanceRequest","AuthenticatedPeerEvidence","FleetEnrollmentService","MachineNodeBinding","BackupEvidence","HostUpdateAssignment","RecoveryDenied","RecoveryGuard","RestoreVerification","UpdatePlanner","UpdateRing","JsonLeaseTable"]
