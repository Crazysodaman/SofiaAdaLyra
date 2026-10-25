"""PKG-RUN exports loaded lazily across Core-free Platform boundaries."""
from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    **{name: ("lease", name) for name in (
        "LeaseResult", "LocalRunLeaseStore", "RunLease", "RunLeaseError",
    )},
    **{name: ("generation", name) for name in (
        "ComponentGenerationStore", "GenerationState",
    )},
    **{name: ("heartbeat", name) for name in (
        "ApplicationHeartbeat", "ApplicationHeartbeatStore",
    )},
    **{name: ("periodic", name) for name in (
        "OpportunityPolicy", "OpportunityResult", "PeriodicThoughtGate",
        "PeriodicThoughtRunner",
    )},
    **{name: ("supervisor", name) for name in (
        "LocalRuntimeSupervisor", "ManagedRuntimeBackend", "ProcessState",
        "RuntimeObservation", "SupervisorPolicy", "SupervisorResult",
    )},
    **{name: ("windows_service_spec", name) for name in (
        "RUNTIME_SERVICE", "WATCHDOG_SERVICE", "WindowsServiceSpec",
        "service_specs",
    )},
    **{name: ("work", name) for name in (
        "DurableWorkStore", "TaskExecutionManager", "WorkJob",
        "WorkOverloadError", "WorkResult", "WorkStatus",
    )},
    **{name: ("components", name) for name in (
        "ComponentAction", "ComponentHealth", "ComponentKind",
        "ComponentRuntimeSupervisor", "ComponentSpec", "ComponentStatus",
        "DesiredComponentState",
    )},
    **{name: ("effects", name) for name in (
        "EffectBroker", "EffectReceipt", "EffectRequest", "EffectStatus",
    )},
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value
