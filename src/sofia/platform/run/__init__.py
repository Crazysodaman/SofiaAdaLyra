"""PKG-RUN: local lifecycle, singleton fencing, and bounded background opportunities."""

from .lease import (
    LeaseResult,
    LocalRunLeaseStore,
    RunLease,
    RunLeaseError,
)
from .heartbeat import (
    ApplicationHeartbeat,
    ApplicationHeartbeatStore,
)
from .periodic import (
    OpportunityPolicy,
    OpportunityResult,
    PeriodicThoughtGate,
    PeriodicThoughtRunner,
)
from .supervisor import (
    LocalRuntimeSupervisor,
    ManagedRuntimeBackend,
    ProcessState,
    RuntimeObservation,
    SupervisorPolicy,
    SupervisorResult,
)
from .windows_service_spec import (
    RUNTIME_SERVICE,
    WATCHDOG_SERVICE,
    WindowsServiceSpec,
    service_specs,
)
from .work import (
    DurableWorkStore,
    TaskExecutionManager,
    WorkJob,
    WorkOverloadError,
    WorkResult,
    WorkStatus,
)
from .components import (
    ComponentAction,
    ComponentHealth,
    ComponentKind,
    ComponentRuntimeSupervisor,
    ComponentSpec,
    ComponentStatus,
    DesiredComponentState,
)
from .effects import EffectBroker, EffectReceipt, EffectRequest, EffectStatus

__all__ = [
    "ApplicationHeartbeat",
    "ApplicationHeartbeatStore",
    "LeaseResult",
    "LocalRunLeaseStore",
    "LocalRuntimeSupervisor",
    "ManagedRuntimeBackend",
    "OpportunityPolicy",
    "OpportunityResult",
    "PeriodicThoughtGate",
    "PeriodicThoughtRunner",
    "ProcessState",
    "RunLease",
    "RunLeaseError",
    "RuntimeObservation",
    "SupervisorPolicy",
    "SupervisorResult",
    "RUNTIME_SERVICE",
    "WATCHDOG_SERVICE",
    "WindowsServiceSpec",
    "service_specs",
    "DurableWorkStore",
    "TaskExecutionManager",
    "WorkJob",
    "WorkOverloadError",
    "WorkResult",
    "WorkStatus",
    "ComponentAction",
    "ComponentHealth",
    "ComponentKind",
    "ComponentRuntimeSupervisor",
    "ComponentSpec",
    "ComponentStatus",
    "DesiredComponentState",
    "EffectBroker",
    "EffectReceipt",
    "EffectRequest",
    "EffectStatus",
]
