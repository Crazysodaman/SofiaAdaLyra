from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.run import (
    ComponentHealth,
    ComponentKind,
    ComponentRuntimeSupervisor,
    ComponentSpec,
    DesiredComponentState,
    LocalRunLeaseStore,
    ManagedRuntimeBackend,
    ProcessState,
    RuntimeObservation,
)


NOW = datetime(2026, 10, 22, 19, tzinfo=timezone.utc)


class Backend(ManagedRuntimeBackend):
    def __init__(self, state=ProcessState.STOPPED, *, ready=False):
        self.observation = RuntimeObservation(state, ready=ready)
        self.starts: list[int] = []
        self.stops = 0
        self.error: Exception | None = None

    def observe(self):
        return self.observation

    def start(self, *, epoch):
        self.starts.append(epoch)
        if self.error is not None:
            raise self.error
        self.observation = RuntimeObservation(ProcessState.STARTING)

    def stop(self):
        self.stops += 1
        self.observation = RuntimeObservation(ProcessState.STOPPED)


def make_supervisor(path):
    leases = LocalRunLeaseStore(path)
    supervisor = ComponentRuntimeSupervisor(state_path=path, lease_store=leases)
    lease = leases.acquire(owner_id="platform-supervisor", now=NOW, ttl_seconds=300).lease
    assert lease is not None
    return leases, supervisor, lease


def test_dependency_order_starts_optional_component_after_core(canonical_state_path):
    _, supervisor, lease = make_supervisor(canonical_state_path)
    core = Backend()
    optional = Backend()
    supervisor.register(ComponentSpec("core", ComponentKind.CORE), core, now=NOW)
    supervisor.register(
        ComponentSpec("research", ComponentKind.OPTIONAL_MODULE, dependencies=("core",)),
        optional,
        now=NOW,
    )

    first = supervisor.reconcile_startup(lease=lease, now=NOW)
    assert [result.component_id for result in first] == ["core", "research"]
    assert first[0].action == "started"
    assert first[1].action == "dependency_unhealthy"

    core.observation = RuntimeObservation(ProcessState.RUNNING, ready=True)
    second = supervisor.reconcile_startup(lease=lease, now=NOW + timedelta(seconds=1))
    assert second[0].action == "already_healthy"
    assert second[1].action == "started"
    assert optional.starts == [lease.epoch]


def test_optional_crash_loop_quarantines_without_stopping_core(canonical_state_path):
    _, supervisor, lease = make_supervisor(canonical_state_path)
    core = Backend(ProcessState.RUNNING, ready=True)
    broken = Backend()
    broken.error = RuntimeError("boom")
    supervisor.register(ComponentSpec("core", ComponentKind.CORE), core, now=NOW)
    supervisor.register(
        ComponentSpec(
            "broken", ComponentKind.OPTIONAL_MODULE,
            dependencies=("core",), failure_limit=2,
        ),
        broken,
        now=NOW,
    )

    assert supervisor.start_component("broken", lease=lease, now=NOW).action == "start_failed"
    result = supervisor.start_component(
        "broken", lease=lease, now=NOW + timedelta(seconds=1),
    )
    assert result.action == "quarantined"
    assert result.status.desired is DesiredComponentState.QUARANTINED
    assert core.stops == 0
    assert supervisor.start_component(
        "broken", lease=lease, now=NOW + timedelta(seconds=2),
    ).action == "blocked_quarantined"


def test_repeated_observed_crash_quarantines_optional_component(canonical_state_path):
    _, supervisor, lease = make_supervisor(canonical_state_path)
    core = Backend(ProcessState.RUNNING, ready=True)
    optional = Backend(ProcessState.FAILED)
    supervisor.register(ComponentSpec("core", ComponentKind.CORE), core, now=NOW)
    supervisor.register(
        ComponentSpec(
            "research", ComponentKind.OPTIONAL_MODULE,
            dependencies=("core",), failure_limit=2,
        ),
        optional,
        now=NOW,
    )
    assert supervisor.start_component("research", lease=lease, now=NOW).action == "started"
    optional.observation = RuntimeObservation(ProcessState.FAILED)
    second = supervisor.start_component(
        "research", lease=lease, now=NOW + timedelta(seconds=1),
    )
    assert second.action == "quarantined"
    assert core.stops == 0


def test_pause_and_resume_are_restart_safe(canonical_state_path):
    leases, supervisor, lease = make_supervisor(canonical_state_path)
    backend = Backend(ProcessState.RUNNING, ready=True)
    spec = ComponentSpec("avatar", ComponentKind.OPTIONAL_MODULE)
    supervisor.register(spec, backend, now=NOW)

    paused = supervisor.pause("avatar", lease=lease, now=NOW, reason="owner pause")
    assert paused.status.desired is DesiredComponentState.PAUSED
    assert backend.stops == 1

    restarted = ComponentRuntimeSupervisor(
        state_path=canonical_state_path, lease_store=leases,
    )
    restarted.register(spec, backend, now=NOW + timedelta(seconds=1))
    assert restarted.read_health(
        "avatar", now=NOW + timedelta(seconds=1),
    ).desired is DesiredComponentState.PAUSED
    assert restarted.reconcile_startup(
        lease=lease, now=NOW + timedelta(seconds=1),
    )[0].action == "blocked_paused"

    resumed = restarted.resume(
        "avatar", lease=lease, now=NOW + timedelta(seconds=2), reason="owner resume",
    )
    assert resumed.action == "started"


def test_missing_dependency_is_rejected(canonical_state_path):
    _, supervisor, _ = make_supervisor(canonical_state_path)
    with pytest.raises(RuntimeError, match="unregistered dependencies"):
        supervisor.register(
            ComponentSpec(
                "research", ComponentKind.OPTIONAL_MODULE,
                dependencies=("missing",),
            ),
            Backend(),
            now=NOW,
        )


def test_stale_heartbeat_is_degraded_not_healthy(canonical_state_path):
    _, supervisor, lease = make_supervisor(canonical_state_path)
    backend = Backend(ProcessState.RUNNING, ready=True)
    supervisor.register(
        ComponentSpec(
            "voice", ComponentKind.OPTIONAL_MODULE,
            heartbeat_timeout=timedelta(seconds=5),
        ),
        backend,
        now=NOW,
    )
    supervisor.heartbeat("voice", lease=lease, now=NOW)
    status = supervisor.read_health("voice", now=NOW + timedelta(seconds=6))
    assert status.health is ComponentHealth.DEGRADED


def test_lost_runtime_lease_denies_component_effect(canonical_state_path):
    leases, supervisor, lease = make_supervisor(canonical_state_path)
    backend = Backend()
    supervisor.register(
        ComponentSpec("research", ComponentKind.OPTIONAL_MODULE), backend, now=NOW,
    )
    leases.release(lease, now=NOW + timedelta(seconds=1))
    with pytest.raises(PermissionError, match="lease"):
        supervisor.start_component(
            "research", lease=lease, now=NOW + timedelta(seconds=2),
        )
    assert backend.starts == []


def test_component_spec_change_requires_reviewed_migration(canonical_state_path):
    _, supervisor, _ = make_supervisor(canonical_state_path)
    backend = Backend()
    supervisor.register(
        ComponentSpec("research", ComponentKind.OPTIONAL_MODULE), backend, now=NOW,
    )
    with pytest.raises(RuntimeError, match="reviewed migration"):
        supervisor.register(
            ComponentSpec(
                "research", ComponentKind.OPTIONAL_MODULE, failure_limit=8,
            ),
            backend,
            now=NOW + timedelta(seconds=1),
        )


def test_failed_backend_stop_does_not_resurrect_component_after_restart(
    canonical_state_path,
):
    leases, supervisor, lease = make_supervisor(canonical_state_path)
    backend = Backend(ProcessState.RUNNING, ready=True)
    supervisor.register(
        ComponentSpec("research", ComponentKind.OPTIONAL_MODULE), backend, now=NOW,
    )
    def fail_stop():
        raise RuntimeError("transport lost during stop")
    backend.stop = fail_stop
    with pytest.raises(RuntimeError, match="transport lost"):
        supervisor.pause(
            "research", lease=lease, now=NOW, reason="owner pause",
        )

    restarted = ComponentRuntimeSupervisor(
        state_path=canonical_state_path, lease_store=leases,
    )
    restarted.register(
        ComponentSpec("research", ComponentKind.OPTIONAL_MODULE), backend, now=NOW,
    )
    status = restarted.read_health("research", now=NOW)
    assert status.desired is DesiredComponentState.PAUSED
    assert restarted.reconcile_startup(lease=lease, now=NOW)[0].action == "blocked_paused"
