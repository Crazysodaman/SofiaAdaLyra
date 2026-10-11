"""CA-2205 expired unstarted RUN tasks, authored not executed."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3

from sofia.run.work import (
    DurableWorkStore, TaskExecutionManager, WorkStatus, WorkResult,
)


NOW = datetime(2026, 10, 10, 18, tzinfo=timezone.utc)


def _queued(store, fingerprint, *, seconds=10):
    return store.enqueue(
        kind="read-test", fingerprint=fingerprint, payload={"bounded": True},
        priority=20, resource_cost=5, risk="read_only",
        completion_condition="trusted receipt or explicit failure",
        now=NOW, deadline=NOW + timedelta(seconds=seconds),
    )


def test_expired_queued_jobs_settle_even_when_background_execution_paused(tmp_path):
    state = tmp_path / "sofia.db"
    state.touch()
    store = DurableWorkStore(state)
    handled = []
    manager = TaskExecutionManager(
        store, {"read-test": lambda job, cancel: (
            handled.append(job.job_id) or WorkResult(WorkStatus.COMPLETED, {}, "done")
        )},
        max_workers=1,
    )
    try:
        job = _queued(store, "deadline-idempotent-work-1")
        assert manager.tick(
            now=NOW + timedelta(minutes=1),
            busy=True, resource_pressure=1.0,
        ) == 0
        assert store.get(job.job_id).status is WorkStatus.FAILED
        assert store.get(job.job_id).reason == "deadline_expired_before_start"
        assert handled == []
        with closing(sqlite3.connect(state)) as db:
            events = db.execute(
                "SELECT to_status FROM autonomous_work_event WHERE job_id=? "
                "ORDER BY event_id",
                (job.job_id,),
            ).fetchall()
        assert events == [("queued",), ("failed",)]
        assert manager.tick(
            now=NOW + timedelta(minutes=2), busy=True,
        ) == 0
        with closing(sqlite3.connect(state)) as db:
            assert db.execute(
                "SELECT COUNT(*) FROM autonomous_work_event WHERE job_id=?",
                (job.job_id,),
            ).fetchone()[0] == 2
    finally:
        manager.close(wait=True)


def test_expiration_never_labels_approval_or_inflight_job_clean_failure(tmp_path):
    state = tmp_path / "sofia.db"
    state.touch()
    store = DurableWorkStore(state)
    pending = _queued(store, "deadline-approval-2")
    running = _queued(store, "deadline-running-3")
    store.transition(
        pending.job_id, expected=(WorkStatus.QUEUED,),
        status=WorkStatus.WAITING_APPROVAL, reason="host grant required",
        now=NOW + timedelta(seconds=1),
    )
    store.transition(
        running.job_id, expected=(WorkStatus.QUEUED,),
        status=WorkStatus.RUNNING, reason="worker already started",
        now=NOW + timedelta(seconds=1),
    )
    assert store.expire_unstarted(now=NOW + timedelta(minutes=1)) == 0
    assert store.get(pending.job_id).status is WorkStatus.WAITING_APPROVAL
    assert store.get(running.job_id).status is WorkStatus.RUNNING
