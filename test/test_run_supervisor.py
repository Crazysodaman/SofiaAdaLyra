from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.run import (
    LocalRunLeaseStore,
    LocalRuntimeSupervisor,
    ManagedRuntimeBackend,
    ProcessState,
    RuntimeObservation,
    SupervisorPolicy,
)

START = datetime(2026, 9, 25, 19, tzinfo=timezone.utc)


class FakeBackend(ManagedRuntimeBackend):
    def __init__(self, observation=None):
        self.observation = observation or RuntimeObservation(ProcessState.STOPPED)
        self.starts = []
        self.stops = 0
        self.start_error = None
        self.stop_error = None

    def observe(self):
        return self.observation

    def start(self, *, epoch):
        self.starts.append(epoch)
        if self.start_error is not None:
            raise self.start_error
        self.observation = RuntimeObservation(ProcessState.STARTING)

    def stop(self):
        self.stops += 1
        if self.stop_error is not None:
            raise self.stop_error
        self.observation = RuntimeObservation(ProcessState.STOPPED)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE preserved (value TEXT)")
        db.execute("INSERT INTO preserved VALUES ('yes')")
    return path


def make_supervisor(state, backend=None, policy=None):
    store = LocalRunLeaseStore(state)
    backend = backend or FakeBackend()
    supervisor = LocalRuntimeSupervisor(
        state_path=state,
        lease_store=store,
        backend=backend,
        policy=policy or SupervisorPolicy(),
    )
    return store, backend, supervisor


def test_valid_lease_starts_stopped_runtime_with_epoch(state):
    store, backend, supervisor = make_supervisor(state)
    lease = store.acquire(owner_id="local-supervisor", now=START).lease
    result = supervisor.reconcile(lease, now=START)
    assert result.action == "started"
    assert backend.starts == [lease.epoch]
    assert backend.observation.state is ProcessState.STARTING


def test_running_ready_runtime_is_healthy_and_not_restarted(state):
    backend = FakeBackend(
        RuntimeObservation(ProcessState.RUNNING, ready=True)
    )
    store, backend, supervisor = make_supervisor(state, backend)
    lease = store.acquire(owner_id="local-supervisor", now=START).lease
    result = supervisor.reconcile(lease, now=START)
    assert result.action == "healthy"
    assert backend.starts == []
    assert backend.stops == 0


def test_no_lease_means_no_start_authority(state):
    store, backend, supervisor = make_supervisor(state)
    fake_lease = store.acquire(owner_id="other", now=START).lease
    store.release(fake_lease, now=START + timedelta(seconds=1))
    result = supervisor.reconcile(
        fake_lease,
        now=START + timedelta(seconds=2),
    )
    assert result.action == "no_authority"
    assert backend.starts == []


def test_lost_lease_fences_still_running_old_process(state):
    backend = FakeBackend(
        RuntimeObservation(ProcessState.RUNNING, ready=True)
    )
    store, backend, supervisor = make_supervisor(state, backend)
    old = store.acquire(
        owner_id="old-supervisor",
        now=START,
        ttl_seconds=5,
    ).lease
    new = store.acquire(
        owner_id="new-supervisor",
        now=START + timedelta(seconds=5),
        ttl_seconds=30,
    ).lease
    assert new.epoch > old.epoch

    result = supervisor.reconcile(
        old,
        now=START + timedelta(seconds=6),
    )
    assert result.action == "fenced_stopped"
    assert backend.stops == 1
    assert backend.observation.state is ProcessState.STOPPED


def test_stop_request_stops_runtime_but_does_not_release_lease(state):
    backend = FakeBackend(
        RuntimeObservation(ProcessState.RUNNING, ready=True)
    )
    store, backend, supervisor = make_supervisor(state, backend)
    lease = store.acquire(owner_id="local-supervisor", now=START).lease
    result = supervisor.reconcile(
        lease,
        now=START,
        stop_requested=True,
    )
    assert result.action == "stopped"
    assert backend.stops == 1
    assert store.holds(lease, now=START)


def test_start_failure_uses_exponential_backoff(state):
    backend = FakeBackend()
    backend.start_error = RuntimeError("cannot launch")
    policy = SupervisorPolicy(
        initial_backoff=timedelta(seconds=5),
        max_backoff=timedelta(seconds=30),
    )
    store, backend, supervisor = make_supervisor(state, backend, policy)
    lease = store.acquire(owner_id="local-supervisor", now=START).lease

    first = supervisor.reconcile(lease, now=START)
    assert first.action == "start_failed"
    assert first.backoff_until == START + timedelta(seconds=5)

    blocked = supervisor.reconcile(
        lease,
        now=START + timedelta(seconds=4),
    )
    assert blocked.action == "backoff"
    assert len(backend.starts) == 1

    second = supervisor.reconcile(
        lease,
        now=START + timedelta(seconds=5),
    )
    assert second.action == "start_failed"
    assert second.backoff_until == START + timedelta(seconds=15)
    assert len(backend.starts) == 2


def test_restart_window_limit_stops_launch_storm(state):
    backend = FakeBackend()
    backend.start_error = RuntimeError("still dead")
    policy = SupervisorPolicy(
        max_restarts_in_window=2,
        restart_window=timedelta(minutes=10),
        initial_backoff=timedelta(seconds=1),
        max_backoff=timedelta(seconds=1),
    )
    store, backend, supervisor = make_supervisor(state, backend, policy)
    lease = store.acquire(owner_id="local-supervisor", now=START).lease

    assert supervisor.reconcile(lease, now=START).action == "start_failed"
    assert supervisor.reconcile(
        lease, now=START + timedelta(seconds=1)
    ).action == "start_failed"
    third = supervisor.reconcile(
        lease,
        now=START + timedelta(seconds=2),
    )
    assert third.action == "restart_limit"
    assert len(backend.starts) == 2


def test_readiness_timeout_stops_process_and_enters_backoff(state):
    policy = SupervisorPolicy(
        readiness_grace=timedelta(seconds=30),
        initial_backoff=timedelta(seconds=5),
        max_backoff=timedelta(seconds=30),
    )
    store, backend, supervisor = make_supervisor(
        state,
        FakeBackend(),
        policy,
    )
    lease = store.acquire(owner_id="local-supervisor", now=START).lease
    assert supervisor.reconcile(lease, now=START).action == "started"

    waiting = supervisor.reconcile(
        lease,
        now=START + timedelta(seconds=29),
    )
    assert waiting.action == "waiting_readiness"

    timed_out = supervisor.reconcile(
        lease,
        now=START + timedelta(seconds=30),
    )
    assert timed_out.action == "readiness_timeout"
    assert backend.stops == 1
    assert timed_out.backoff_until == START + timedelta(seconds=35)


def test_unknown_process_state_fails_closed_without_start(state):
    backend = FakeBackend(
        RuntimeObservation(ProcessState.UNKNOWN, detail="status API unavailable")
    )
    store, backend, supervisor = make_supervisor(state, backend)
    lease = store.acquire(owner_id="local-supervisor", now=START).lease
    result = supervisor.reconcile(lease, now=START)
    assert result.action == "unknown_state"
    assert backend.starts == []


def test_observe_contract_rejects_ready_nonrunning_state():
    with pytest.raises(ValueError):
        RuntimeObservation(ProcessState.STOPPED, ready=True)


def test_supervisor_preserves_unrelated_state(state):
    store, backend, supervisor = make_supervisor(state)
    lease = store.acquire(owner_id="local-supervisor", now=START).lease
    supervisor.reconcile(lease, now=START)
    with sqlite3.connect(state) as db:
        assert db.execute("SELECT value FROM preserved").fetchone() == ("yes",)


def test_supervisor_and_lease_must_share_database(tmp_path):
    first = tmp_path / "one.db"
    second = tmp_path / "two.db"
    for path in (first, second):
        with sqlite3.connect(path):
            pass
    lease_store = LocalRunLeaseStore(first)
    with pytest.raises(ValueError, match="same state"):
        LocalRuntimeSupervisor(
            state_path=second,
            lease_store=lease_store,
            backend=FakeBackend(),
        )
