"""LIFE and RUN use one atomic SQLite authorization+job reservation.

This module is intentionally NOT executed during the owner's code-first wave.
The exact rollback, restart, overlap and idempotency checks are for later CI.
"""
from contextlib import closing
from datetime import timedelta
import sqlite3

import pytest

from sofia.creative import ArtifactKind
from sofia.run.work import WorkStatus
from test.test_life_project_forge import (
    infrastructure, active_project, wait_for_job,
)


@pytest.mark.pkg_run
def test_atomic_submitted_job_has_project_link_and_one_use_grant(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project, evidence_ref = active_project(life, now)
    try:
        job = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="Transactional", specification={"content": "Foxfire story"},
            evidence_ref=evidence_ref, now=now + timedelta(seconds=3),
        )
        assert life.store.jobs(project.project_id) == (job.job_id,)
        with closing(sqlite3.connect(life.path)) as db:
            receipt = db.execute(
                "SELECT status,project_id,artifact_id,request_digest "
                "FROM life_artifact_authorization WHERE request_id=?",
                (job.payload["parameters"]["request_id"],),
            ).fetchone()
        assert receipt[0] == "authorized"
        assert receipt[1] == project.project_id
        assert receipt[2] == job.payload["parameters"]["artifact_id"]
        assert len(receipt[3]) == 64
    finally:
        life.close()


@pytest.mark.pkg_run
def test_failed_life_provision_rolls_back_run_job_event_and_grant(tmp_path, monkeypatch):
    life, _goals, now = infrastructure(tmp_path)
    project, evidence_ref = active_project(life, now)
    try:
        def fail_in_transaction(db, **kwargs):
            # Simulate crashing after RUN has persisted its enqueue INSERT
            # but before the LIFE link/grant transaction completes.
            db.execute(
                "INSERT INTO life_artifact_authorization VALUES"
                "(?,?,?,?,?,?,?)",
                ("partial", project.project_id, "broken", "bad", "authorized",
                 now.isoformat(), None),
            )
            raise RuntimeError("simulated interruption before commit")

        monkeypatch.setattr(life.store, "provision_artifact_job", fail_in_transaction)
        with pytest.raises(RuntimeError, match="interruption"):
            life.schedule_artifact(
                project.project_id, artifact_kind=ArtifactKind.TEXT,
                title="Rollback", specification={"content": "test"},
                evidence_ref=evidence_ref, now=now + timedelta(seconds=3),
            )
        assert life.store.jobs(project.project_id) == ()
        assert life.work_store.list() == ()
        with closing(sqlite3.connect(life.path)) as db:
            assert db.execute(
                "SELECT count(*) FROM life_artifact_authorization"
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT count(*) FROM autonomous_work_event"
            ).fetchone()[0] == 0
    finally:
        life.close()


@pytest.mark.pkg_run
def test_two_pending_jobs_for_one_project_are_rejected_atomically(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project, evidence_ref = active_project(life, now)
    try:
        one = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="First", specification={"content": "v1"},
            evidence_ref=evidence_ref, now=now + timedelta(seconds=3),
        )
        with pytest.raises(RuntimeError, match="unsettled RUN job"):
            life.schedule_artifact(
                project.project_id, artifact_kind=ArtifactKind.TEXT,
                title="Second", specification={"content": "v2"},
                evidence_ref=evidence_ref, now=now + timedelta(seconds=4),
            )
        assert life.store.jobs(project.project_id) == (one.job_id,)
        assert len(life.work_store.list()) == 1
        with closing(sqlite3.connect(life.path)) as db:
            assert db.execute(
                "SELECT count(*) FROM life_artifact_authorization"
            ).fetchone()[0] == 1
    finally:
        life.close()


@pytest.mark.pkg_run
def test_second_revision_allowed_after_real_first_job_settles(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project, evidence_ref = active_project(life, now)
    try:
        first = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="First", specification={"content": "Foxfire edition one"},
            evidence_ref=evidence_ref, now=now + timedelta(seconds=3),
        )
        life.manager.tick(now=now + timedelta(seconds=3))
        assert wait_for_job(life, first.job_id).status is WorkStatus.COMPLETED
        second = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="Revised", specification={"content": "Foxfire edition two"},
            evidence_ref=evidence_ref, now=now + timedelta(seconds=10),
        )
        assert second.job_id != first.job_id
        assert life.store.jobs(project.project_id) == (first.job_id, second.job_id)
    finally:
        life.close()


@pytest.mark.pkg_run
def test_unknown_previous_outcome_blocks_new_artifact_attempt(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project, evidence_ref = active_project(life, now)
    try:
        uncertain = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="Uncertain", specification={"content": "Maybe written"},
            evidence_ref=evidence_ref, now=now + timedelta(seconds=3),
        )
        life.work_store.transition(
            uncertain.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.UNCERTAIN,
            reason="worker_restarted_receipt_missing",
            now=now + timedelta(seconds=4),
        )
        with pytest.raises(RuntimeError, match="unsettled RUN job"):
            life.schedule_artifact(
                project.project_id, artifact_kind=ArtifactKind.TEXT,
                title="Must not replay", specification={"content": "unsafe repeat"},
                evidence_ref=evidence_ref, now=now + timedelta(seconds=5),
            )
        assert life.store.jobs(project.project_id) == (uncertain.job_id,)
    finally:
        life.close()
