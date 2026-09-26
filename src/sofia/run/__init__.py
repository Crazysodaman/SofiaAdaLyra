"""PKG-RUN: local lifecycle, singleton fencing, and bounded background opportunities."""

from .act_schedule import (
    ActSchedulePolicy,
    ActScheduleTick,
    ScheduledActRunner,
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
    "RunLifecycleSnapshot",
    "RunLifecycleState",
    "RunLifecycleStore",
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
]
