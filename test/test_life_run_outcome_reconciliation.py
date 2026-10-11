"""RUN-to-LIFE source-event reconciliation, never side-effect replay.

Authored for the owner's deferred test campaign; not executed here.
"""
from datetime import timedelta

from sofia.life.model import ProjectStatus
from sofia.run.work import WorkStatus
from test.test_life_project_forge import infrastructure, active_project


def _queued_job(life, now):
    project, evidence_ref = active_project(life, now)
    from sofia.creative import ArtifactKind
    job = life.schedule_artifact(
        project.project_id,
        artifact_kind=ArtifactKind.TEXT,
        title="A reconciled source artifact",
        specification={"content": "Some real source content"},
        evidence_ref=evidence_ref,
        now=now + timedelta(seconds=3),
    )
    return project, job


def test_run_outcomes_observed_once_from_original_event_id(tmp_path):
    life, goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        assert life.store.reconcile_run_outcomes(now=now) == ()
        blocked = life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.BLOCKED,
            reason="host SAFE permission denied",
            now=now + timedelta(seconds=4),
        )
        receipts = life.store.reconcile_run_outcomes(now=now + timedelta(seconds=4))
        assert len(receipts) == 1
        receipt = receipts[0]
        assert receipt.project_id == project.project_id
        assert receipt.job_id == job.job_id
        assert receipt.status == "blocked"
        assert receipt.reason == "host SAFE permission denied"
        assert receipt.run_event_id > 0
        assert life.store.reconcile_run_outcomes(now=now + timedelta(seconds=5)) == ()
        # Operator review is preserved. A blocked/uncertain result cannot
        # autonomously promote a personal LIFE project to success.
        assert life.store.get(
            project.project_id,
            owner_principal_id=project.owner_principal_id,
            audience_id=project.audience_id,
        ).status is ProjectStatus.ACTIVE
        assert blocked.status is WorkStatus.BLOCKED
    finally:
        life.close()


def test_observation_replays_neither_failed_job_nor_its_execution(tmp_path):
    life, goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.CANCELLED,
            reason="operator cancelled before starting",
            now=now + timedelta(seconds=4),
        )
        result = life.tick(now=now + timedelta(seconds=5), busy=True)
        assert result["run_outcomes_observed"] == 1
        assert result["jobs_started"] == 0
        assert life.store.jobs(project.project_id) == (job.job_id,)
        assert len(life.store.run_outcome_observations(project.project_id)) == 1
        assert life.store.reconcile_run_outcomes(now=now + timedelta(seconds=6)) == ()
    finally:
        life.close()


def test_all_work_result_transition_receipts_are_auditable_and_idempotent(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        transitions = (
            (WorkStatus.BLOCKED, "scope blocked"),
            (WorkStatus.WAITING_APPROVAL, "awaiting operator"),
            (WorkStatus.FAILED, "worker ran out of approved resource"),
        )
        previous = WorkStatus.QUEUED
        for offset, (status, reason) in enumerate(transitions, start=4):
            life.work_store.transition(
                job.job_id, expected=(previous,), status=status,
                reason=reason, now=now + timedelta(seconds=offset),
            )
            previous = status
        observed = life.store.reconcile_run_outcomes(
            now=now + timedelta(seconds=8),
        )
        assert [r.status for r in observed] == [
            "blocked", "waiting_approval", "failed",
        ]
        assert len({r.run_event_id for r in observed}) == 3
        assert life.store.reconcile_run_outcomes(
            now=now + timedelta(seconds=9),
        ) == ()
        assert [r.status for r in life.store.run_outcome_observations(
            project.project_id,
        )] == ["blocked", "waiting_approval", "failed"]
        assert life.store.jobs(project.project_id) == (job.job_id,)
    finally:
        life.close()


def test_source_outcomes_can_be_recorded_even_under_busy_cognition(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.UNCERTAIN, reason="executor restarted without receipt",
            now=now + timedelta(seconds=4),
        )
        report = life.tick(
            now=now + timedelta(seconds=5),
            busy=True, resource_pressure=1.0,
        )
        assert report["selection"] == "inactivity"
        assert report["run_outcomes_observed"] == 1
        assert report["jobs_started"] == 0
        assert len(life.store.run_outcome_observations(project.project_id)) == 1
        assert life.store.run_outcome_observations(
            project.project_id,
        )[0].status == "uncertain"
    finally:
        life.close()
