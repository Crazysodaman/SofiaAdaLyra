from datetime import datetime, timedelta, timezone
import time

import pytest

from sofia.run.work import (
    DurableWorkStore, TaskExecutionManager, WorkResult, WorkStatus,
)
from sofia.state.sqlite_plane import SQLiteStatePlane


pytestmark = pytest.mark.pkg_run


def test_multiple_application_coordinators_only_claim_their_reviewed_job_kinds(tmp_path):
    path = tmp_path / "sofia.db"
    SQLiteStatePlane(path)
    store = DurableWorkStore(path)
    handler = lambda _job, _cancel: WorkResult(
        WorkStatus.COMPLETED, {"receipt": "real"}, "handled",
    )
    life = TaskExecutionManager(store, {"life-job": handler}, max_workers=1)
    engineering = TaskExecutionManager(store, {"engineering-job": handler}, max_workers=1)
    now = datetime.now(timezone.utc)
    try:
        job = life.submit(
            kind="life-job", fingerprint="life-handler-isolation",
            payload={}, priority=50, resource_cost=5, risk="read_only",
            completion_condition="The reviewed handler records a result.",
            now=now, deadline=now + timedelta(minutes=1),
        )
        assert engineering.tick(now=now) == 0
        assert store.get(job.job_id).status is WorkStatus.QUEUED
        assert life.tick(now=now) == 1
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and store.get(job.job_id).status is WorkStatus.RUNNING:
            time.sleep(0.01)
        assert store.get(job.job_id).status is WorkStatus.COMPLETED
    finally:
        life.close()
        engineering.close()
