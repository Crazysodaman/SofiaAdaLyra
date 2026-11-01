from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from sofia.platform.run.heartbeat import ApplicationHeartbeat, ApplicationHeartbeatStore
from sofia.platform.run.host import LocalServiceRuntimeBackend, RunSupervisorHost
from sofia.platform.run.lease import LeaseResult, RunLease
from sofia.platform.run.runtime_service import runtime_start_allowed
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


def heartbeat(path, *, epoch, recorded_at=NOW, ready=True):
    ApplicationHeartbeatStore(path).publish(ApplicationHeartbeat(
        instance_id=f"runtime:{epoch}", recorded_at=recorded_at,
        ready=ready, runtime_state="ready", database_writable=True,
        background_running=True, detail="test heartbeat",
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


def test_only_fresh_matching_application_heartbeat_is_ready(tmp_path, monkeypatch):
    path = state(tmp_path)
    maintenance = Maintenance()
    backend = LocalServiceRuntimeBackend(
        service_name="SofiaAdaLyra", state_path=path, maintenance=maintenance,
    )
    backend.heartbeats.bind_generation(7, now=NOW)
    heartbeat(path, epoch=6)
    assert backend.observe().ready is False

    heartbeat(path, epoch=7, recorded_at=NOW - timedelta(minutes=2))
    assert backend.observe().ready is False

    heartbeat(path, epoch=7, recorded_at=datetime.now(timezone.utc))
    assert backend.observe().ready is True


def test_service_start_binds_generation_before_scm_call(tmp_path):
    path = state(tmp_path)
    maintenance = Maintenance(status="stopped")
    backend = LocalServiceRuntimeBackend(
        service_name="SofiaAdaLyra", state_path=path, maintenance=maintenance,
    )

    backend.start(epoch=9)

    assert backend.heartbeats.current_generation() == 9
    assert maintenance.calls == [("SofiaAdaLyra", "start")]

    try:
        backend.start(epoch=8)
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
