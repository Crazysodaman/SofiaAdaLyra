"""CA-3005 deterministic RUN shutdown before Windows SQLite home teardown.

Authored for the deferred Windows test campaign; NOT executed here.
"""
from datetime import datetime, timedelta, timezone
from threading import Event, Thread

import pytest

from sofia.run.work import (
    DurableWorkStore, TaskExecutionManager, WorkResult, WorkStatus,
)
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


NOW = datetime(2026, 10, 11, 9, tzinfo=timezone.utc)


def _manager(tmp_path, handler):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = DurableWorkStore(state)
    manager = TaskExecutionManager(store, {"slow-read": handler})
    job = manager.submit(
        kind="slow-read", fingerprint="one-shutdown-owner-job",
        payload={"request": "bounded"},
        priority=20,resource_cost=5,risk="read_only",
        completion_condition="durable result",
        now=NOW,deadline=NOW+timedelta(minutes=30),
    )
    return state,store,manager,job


def test_shutdown_waits_for_running_job_and_db_transition(tmp_path):
    running,release = Event(),Event()
    def handler(job, cancel):
        running.set()
        release.wait(timeout=10)
        return WorkResult(WorkStatus.COMPLETED, {}, "already_finished")
    path,store,manager,job = _manager(tmp_path,handler)
    assert manager.tick(now=NOW+timedelta(seconds=1)) == 1
    assert running.wait(timeout=5)
    shut = Event()
    errors = []
    def close():
        try:
            manager.close(wait=True,timeout_seconds=5)
        except BaseException as exc:
            errors.append(exc)
        finally:
            shut.set()
    worker = Thread(target=close)
    worker.start()
    try:
        assert not shut.wait(timeout=0.05)
        release.set()
        assert shut.wait(timeout=5)
        assert errors == []
        assert store.get(job.job_id).status in (
            WorkStatus.COMPLETED,WorkStatus.UNCERTAIN,
        )
        with pytest.raises(RuntimeError, match="shutting down"):
            manager.tick(now=NOW+timedelta(minutes=1))
        # Once callback fully drains there must be no active SQLite writer
        # retained merely because ThreadPoolExecutor.close returned early.
        path.rename(tmp_path / "retired-sofia.db")
    finally:
        release.set()
        worker.join(timeout=5)


def test_uncooperative_worker_reports_unfinished_shutdown_instead_of_success(tmp_path):
    entered,release = Event(),Event()
    def handler(job, cancel):
        entered.set()
        release.wait(timeout=5)
        return WorkResult(WorkStatus.UNCERTAIN, {}, "test_end")
    path,store,manager,job = _manager(tmp_path,handler)
    assert manager.tick(now=NOW+timedelta(seconds=1)) == 1
    assert entered.wait(timeout=5)
    try:
        with pytest.raises(RuntimeError, match="still active"):
            manager.close(wait=True,timeout_seconds=0.01)
    finally:
        release.set()


def test_all_application_owned_executor_closes_require_bounded_drain():
    import inspect
    from sofia.application.autonomous_work import AutonomousWorkCoordinator
    from sofia.life.coordinator import SelfDirectedLifeCoordinator
    for owner in (AutonomousWorkCoordinator,SelfDirectedLifeCoordinator):
        source = inspect.getsource(owner.close)
        assert "wait=True" in source and "timeout_seconds" in source
