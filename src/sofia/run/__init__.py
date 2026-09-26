"""PKG-RUN: local lifecycle, singleton fencing, and bounded background opportunities."""

from .act_schedule import (
    ActSchedulePolicy,
    ActScheduleTick,
    ScheduledActRunner,
)
from .health import (
    RunHealthObservation,
    RunHealthState,
    RunHeartbeatSnapshot,
    RunHeartbeatStore,
)
from .lifecycle import (
    RunLifecycleSnapshot,
    RunLifecycleState,
    RunLifecycleStore,
)
from .lease import (
    LeaseResult,
    LocalRunLeaseStore,
    RunLease,
    RunLeaseError,
)
from .periodic import (
    OpportunityPolicy,
    OpportunityResult,
    PeriodicThoughtGate,
    PeriodicThoughtRunner,
)
from .watchdog import (
    HostServiceController,
    HostServiceObservation,
    HostServiceState,
    IndependentRunWatchdog,
    WatchdogPolicy,
    WatchdogResult,
)
from .supervisor import (
    LocalRuntimeSupervisor,
    ManagedRuntimeBackend,
    ProcessState,
    RuntimeObservation,
    SupervisorPolicy,
    SupervisorResult,
)

__all__ = [
    "ActSchedulePolicy",
    "ActScheduleTick",
    "ScheduledActRunner",
    "RunHealthObservation",
    "RunHealthState",
    "RunHeartbeatSnapshot",
    "RunHeartbeatStore",
    "RunLifecycleSnapshot",
    "RunLifecycleState",
    "RunLifecycleStore",
    "LeaseResult",
    "LocalRunLeaseStore",
    "LocalRuntimeSupervisor",
    "HostServiceController",
    "HostServiceObservation",
    "HostServiceState",
    "IndependentRunWatchdog",
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
    "WatchdogPolicy",
    "WatchdogResult",
]
