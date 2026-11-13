from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from sofia.platform.run.heartbeat import (
    ApplicationHeartbeat, ApplicationHeartbeatStore, generation_bound_heartbeat_publisher,
)
from sofia.platform.run.host import LocalServiceRuntimeBackend, RunSupervisorHost
from sofia.platform.run.lease import LeaseResult, RunLease, LocalRunLeaseStore
from sofia.platform.run.runtime_service import (
    runtime_package_identity,
    runtime_start_allowed,
)
from sofia.platform.safe.operator_stop import OperatorStopStore


NOW = datetime.now(timezone.utc)


class Maintenance:
    def __init__(self, status="running"):
        self.status = status
        self.calls = []

    def service_status(self, name):
        return self.status

    def service(self, name, action):
        self.calls.append((name, action))


def state(tmp_path: Path) -> Path:
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE preserved(value TEXT)")
    return path


def test_legacy_heartbeat_schema_migrates_without_claiming_generation(tmp_path):
    path = state(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("""
            CREATE TABLE run_application_heartbeat (
                instance_id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL,
                ready INTEGER NOT NULL, runtime_state TEXT NOT NULL,
                database_writable INTEGER NOT NULL,
                background_running INTEGER NOT NULL, detail TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE run_application_heartbeat_current (
                singleton INTEGER PRIMARY KEY, instance_id TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            )
        """)
        db.execute(
            "INSERT INTO run_application_heartbeat VALUES(?,?,?,?,?,?,?)",
            ("legacy", NOW.isoformat(), 1, "ready", 1, 1, "legacy"),
        )
        db.execute(
            "INSERT INTO run_application_heartbeat_current VALUES(1,?,?)",
            ("legacy", NOW.isoformat()),
        )

    observed = ApplicationHeartbeatStore(path).current()

    assert observed is not None
    assert observed.generation_epoch is None


def heartbeat(
    path, *, epoch, recorded_at=NOW, ready=True,
    database_writable=True, background_running=True,
):
    ApplicationHeartbeatStore(path).publish(ApplicationHeartbeat(
        instance_id=f"runtime:{epoch}", recorded_at=recorded_at,
        ready=ready, runtime_state="ready",
        database_writable=database_writable,
        background_running=background_running, detail="test heartbeat",
        generation_epoch=epoch,
    ))


def test_scm_running_without_generation_bound_heartbeat_is_not_ready(tmp_path):
    path = state(tmp_path)
    maintenance = Maintenance()
    backend = LocalServiceRuntimeBackend(
        service_name="SofiaAdaLyra", state_path=path, maintenance=maintenance,
    )
    backend.heartbeats.bind_generation(7, now=NOW)

    observation = backend.observe()

    assert observation.ready is False
    assert observation.generation_epoch == 7


@pytest.mark.parametrize("collection_age_seconds", (0, 600))
def test_only_fresh_matching_application_heartbeat_is_ready(
    tmp_path, monkeypatch, collection_age_seconds,
):
    moment = datetime.now(timezone.utc)
    # A long suite may run this test minutes after module collection.
    monkeypatch.setitem(globals(), "NOW", moment - timedelta(seconds=collection_age_seconds))
    path = state(tmp_path)
    maintenance = Maintenance()
    backend = LocalServiceRuntimeBackend(
        service_name="SofiaAdaLyra", state_path=path, maintenance=maintenance,
    )
    live_lease = LocalRunLeaseStore(path).acquire(
        owner_id="watchdog:readiness-test", now=moment, ttl_seconds=300,
    ).lease
    assert live_lease is not None
    backend.heartbeats.bind_generation(live_lease.epoch, now=moment)
    heartbeat(path, epoch=live_lease.epoch + 1, recorded_at=moment)
    assert backend.observe().ready is False

    heartbeat(path, epoch=live_lease.epoch, recorded_at=moment - timedelta(minutes=2))
    assert backend.observe().ready is False

    heartbeat(path, epoch=live_lease.epoch, recorded_at=datetime.now(timezone.utc))
    assert backend.observe().ready is True



def test_fresh_heartbeat_cannot_restore_expired_run_lease(tmp_path):
    path = state(tmp_path)
    moment = datetime.now(timezone.utc)
    backend = LocalServiceRuntimeBackend(
        service_name="SofiaAdaLyra", state_path=path, maintenance=Maintenance(),
    )
    old = moment - timedelta(minutes=10)
    lease = LocalRunLeaseStore(path).acquire(
        owner_id="watchdog:expired-readiness-test", now=old, ttl_seconds=300,
    ).lease
    assert lease is not None
    backend.heartbeats.bind_generation(lease.epoch, now=old)
    heartbeat(path, epoch=lease.epoch, recorded_at=moment)

    assert backend.observe().ready is False

def test_database_or_background_failure_withholds_service_readiness(tmp_path):
    path = state(tmp_path)
    backend = LocalServiceRuntimeBackend(
        service_name="SofiaAdaLyra", state_path=path,
        maintenance=Maintenance(),
    )
    backend.heartbeats.bind_generation(7, now=NOW)

    heartbeat(
        path, epoch=7, recorded_at=datetime.now(timezone.utc),
        database_writable=False,
    )
    assert backend.observe().ready is False

    heartbeat(
        path, epoch=7, recorded_at=datetime.now(timezone.utc),
        background_running=False,
    )
    assert backend.observe().ready is False


def test_service_start_binds_generation_before_scm_call(tmp_path):
    path = state(tmp_path)
    maintenance = Maintenance(status="stopped")
    backend = LocalServiceRuntimeBackend(
        service_name="SofiaAdaLyra", state_path=path, maintenance=maintenance,
    )

    live_lease = LocalRunLeaseStore(path).acquire(
        owner_id="watchdog:service-test", now=datetime.now(timezone.utc),
        ttl_seconds=300,
    ).lease
    assert live_lease is not None
    backend.start(epoch=live_lease.epoch)

    assert backend.heartbeats.current_generation() == live_lease.epoch
    assert maintenance.calls == [("SofiaAdaLyra", "start")]

    try:
        backend.start(epoch=live_lease.epoch + 1)
    except PermissionError:
        pass
    else:
        raise AssertionError("stale watchdog generation started the service")
    assert maintenance.calls == [("SofiaAdaLyra", "start")]


class OneLoopStop:
    def __init__(self):
        self.done = False

    def is_set(self):
        return self.done

    def wait(self, _seconds):
        self.done = True


class LeaseStore:
    def __init__(self):
        self.lease = RunLease(
            "watchdog", 1, NOW, NOW, NOW + timedelta(minutes=1),
        )

    def acquire(self, **_kwargs):
        return LeaseResult("acquired", self.lease)

    def renew(self, lease, **_kwargs):
        return LeaseResult("renewed", lease)

    def release(self, *_args, **_kwargs):
        return True


class Supervisor:
    def __init__(self):
        self.calls = []

    def reconcile(self, lease, **kwargs):
        self.calls.append((lease, kwargs))


def test_persisted_owner_stop_dominates_watchdog_recovery(tmp_path, monkeypatch):
    path = state(tmp_path)
    OperatorStopStore(path).set(
        active=True, updated_by="Sparks", reason="owner intends runtime offline",
        at=NOW,
    )
    assert runtime_start_allowed(path) is False
    leases, supervisor = LeaseStore(), Supervisor()
    monkeypatch.setattr(
        RunSupervisorHost, "_supervisor", lambda _self: (leases, supervisor),
    )
    host = RunSupervisorHost(
        state_path=path, service_name="SofiaAdaLyra", owner_id="watchdog",
    )

    host.run(stop_event=OneLoopStop())

    assert len(supervisor.calls) == 1
    assert supervisor.calls[0][1]["desired_running"] is False
    assert supervisor.calls[0][1]["stop_requested"] is True


def test_runtime_diagnostic_identity_is_bounded_and_contains_no_path():
    identity = runtime_package_identity()

    assert identity.startswith("sofia-ada-lyra/")
    assert len(identity) <= 120
    assert "/workspace/" not in identity
    assert "\\" not in identity

def test_core001_scm_heartbeat_without_live_writer_lease_is_not_ready(tmp_path):
    path = state(tmp_path)
    backend = LocalServiceRuntimeBackend(
        service_name="SofiaAdaLyra", state_path=path,
        maintenance=Maintenance(),
    )
    backend.heartbeats.bind_generation(7, now=datetime.now(timezone.utc))
    heartbeat(path, epoch=7, recorded_at=datetime.now(timezone.utc))
    assert backend.observe().ready is False
    with pytest.raises(PermissionError, match="lease"):
        backend.start(epoch=7)


def test_core001_lease_owner_revocation_removes_scm_readiness(tmp_path):
    path = state(tmp_path)
    store = LocalRunLeaseStore(path)
    now = datetime.now(timezone.utc)
    lease = store.acquire(
        owner_id="watchdog:revocation", now=now, ttl_seconds=180,
    ).lease
    assert lease is not None
    backend = LocalServiceRuntimeBackend(
        service_name="SofiaAdaLyra", state_path=path,
        maintenance=Maintenance(),
    )
    backend.heartbeats.bind_generation(lease.epoch, now=now)
    heartbeat(path, epoch=lease.epoch, recorded_at=now)
    assert backend.observe().ready is True

    store.release(lease, now=now + timedelta(seconds=1))
    assert backend.observe().ready is False


def test_core001_operator_stop_blocks_scm_ready_and_start(tmp_path):
    path = state(tmp_path)
    now = datetime.now(timezone.utc)
    lease = LocalRunLeaseStore(path).acquire(
        owner_id="watchdog:operator-stop", now=now, ttl_seconds=180,
    ).lease
    assert lease is not None
    backend = LocalServiceRuntimeBackend(
        service_name="SofiaAdaLyra", state_path=path, maintenance=Maintenance(),
    )
    backend.heartbeats.bind_generation(lease.epoch, now=now)
    heartbeat(path, epoch=lease.epoch, recorded_at=now)
    assert backend.observe().ready is True
    OperatorStopStore(path).set(
        active=True, updated_by="Sparks", reason="disposable test STOP",
    )
    assert backend.observe().ready is False
    with pytest.raises(PermissionError, match="STOP"):
        backend.start(epoch=lease.epoch)


def test_core001_generation_bound_publisher_never_adopts_newer_epoch(tmp_path):
    path = state(tmp_path)
    now = datetime.now(timezone.utc)
    heartbeats = ApplicationHeartbeatStore(path)
    heartbeats.bind_generation(3, now=now)
    publish = generation_bound_heartbeat_publisher(
        heartbeats, instance_id="disposable-original", runtime_state=lambda: "ready",
    )
    publish(now, True)
    current = heartbeats.current()
    assert current is not None and current.generation_epoch == 3
    assert current.ready

    # Only the service/supervisor may bind an epoch, but when it does,
    # a stale background publisher may not impersonate its successor.
    heartbeats.bind_generation(4, now=now + timedelta(seconds=1))
    with pytest.raises(PermissionError, match="stale application heartbeat"):
        publish(now + timedelta(seconds=2), True)
    assert heartbeats.current().generation_epoch == 3


def test_core001_generation_bound_publisher_denies_missing_initial_authority(tmp_path):
    path = state(tmp_path)
    heartbeats = ApplicationHeartbeatStore(path)
    publish = generation_bound_heartbeat_publisher(
        heartbeats, instance_id="disposable-unleased", runtime_state=lambda: "ready",
    )
    with pytest.raises(PermissionError, match="no startup generation"):
        publish(datetime.now(timezone.utc), True)
    assert heartbeats.current() is None
