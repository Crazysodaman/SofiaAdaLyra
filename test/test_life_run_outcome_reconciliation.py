"""RUN-to-LIFE source-event reconciliation, never side-effect replay.

Authored for the owner's deferred test campaign; not executed here.
"""
from datetime import timedelta

from sofia.core.life.model import ProjectStatus
from sofia.platform.run.work import WorkStatus
from sofia.core.social.principals import local_sparks_principal
from test.test_life_project_forge import infrastructure, active_project


def _queued_job(life, now):
    project, evidence_ref = active_project(life, now)
    from sofia.core.creative import ArtifactKind
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


def test_expired_unstarted_run_pauses_without_claiming_project_failure(tmp_path):
    """A missed admission window is distinct from failed executed work."""
    from sofia.core.goals.model import GoalStatus

    life, goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        expired_at = job.deadline + timedelta(seconds=1)
        assert life.work_store.expire_unstarted(now=expired_at) == 1
        result = life.tick(now=expired_at + timedelta(seconds=1), busy=True)
        assert result["run_outcomes_observed"] == 1
        assert result["terminal_run_projects_settled"] == 1
        assert life.work_store.get(job.job_id).status is WorkStatus.FAILED
        settled = life._project(project.project_id)
        assert settled.status is ProjectStatus.PAUSED
        goal = next(
            item for item in goals.list_visible(local_sparks_principal())
            if item.id == project.goal_id
        )
        assert goal.status is GoalStatus.PAUSED
        assert life.store.jobs(project.project_id) == (job.job_id,)
        assert life.store.artifacts(project.project_id) == ()
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


def test_exact_original_terminal_receipt_survives_unrelated_observation_volume(
    tmp_path,
):
    """Last-100 diagnostic pagination cannot hide current original RUN proof."""
    import sqlite3

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        original = life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.UNCERTAIN,
            reason="original RUN effect uncertain",
            now=now + timedelta(seconds=4),
        )
        assert original.status is WorkStatus.UNCERTAIN
        receipt = life.store.reconcile_run_outcomes(
            now=now + timedelta(seconds=5),
        )[0]
        assert life.store.exact_original_run_outcome(
            project_id=project.project_id,
            job_id=job.job_id, status="uncertain",
        ) == receipt
        # Test-only malformed derived rows have no corresponding original
        # autonomous_work_event and must never become RUN authority.
        with sqlite3.connect(life.path) as db:
            for i in range(105):
                db.execute(
                    "INSERT INTO life_run_outcome_observation VALUES(?,?,?,?,?,?,?)",
                    (
                        receipt.run_event_id + 1000 + i,
                        project.project_id, f"unlinked-test-job:{i}", "blocked",
                        "invalid imported diagnostic observation",
                        receipt.run_at.isoformat(),
                        receipt.observed_at.isoformat(),
                    ),
                )
        assert receipt not in life.store.run_outcome_observations(
            project.project_id, limit=100,
        )
        assert life.store.exact_original_run_outcome(
            project_id=project.project_id,
            job_id=job.job_id, status="uncertain",
        ) == receipt
        assert life.store.exact_original_run_outcome(
            project_id=project.project_id,
            job_id="unlinked-test-job:0", status="blocked",
        ) is None
        # Real original evidence still pauses LIFE; no re-execution occurs.
        assert life._reconcile_terminal_run_projects(
            now=now + timedelta(seconds=6),
        ) == 1
        assert life._project(project.project_id).status is ProjectStatus.PAUSED
        assert life.store.jobs(project.project_id) == (job.job_id,)
    finally:
        life.close()


def test_older_original_terminal_run_event_survives_later_queued_job(
    tmp_path,
):
    """A new queued job cannot conceal the prior source-backed RUN failure."""
    from sofia.core.creative import ArtifactKind

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, first = _queued_job(life, now)
        original = life.work_store.transition(
            first.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.UNCERTAIN,
            reason="first external work result uncertain",
            now=now + timedelta(seconds=4),
        )
        assert original.status is WorkStatus.UNCERTAIN
        evidence = life.record_observation(
            kind="reconciliation-test-original",
            source="test:source-evidence",
            assertion="A separate still-queued work item was admitted in error.",
            now=now + timedelta(seconds=5),
        )
        # Historical admission may have allowed later work before the LIFE
        # tick projected the first uncertain effect. No RUN execution here.
        # Directly insert the queued original job via its reviewed public
        # scheduling path only when the store's unsettled-work fence permits.
        later = life.manager.submit(
            kind="life-create-artifact",
            fingerprint="life-late-queued-run-source-test",
            payload={
                "project_id": project.project_id,
                "goal_id": project.goal_id,
                "project_revision": project.revision,
                "goal_revision": 1,
                "capability_name": "creative.artifact.create",
                "parameters": {"request_id": "request:test-pending-original"},
                "requested_scope": project.project_id,
                "rationale": "queued only, no execution",
            },
            priority=1, resource_cost=1, risk="isolated_change",
            completion_condition="Review original result only",
            now=now + timedelta(seconds=5),
            deadline=now + timedelta(minutes=1),
        )
        # Historical original LIFE job association, not a new scheduler.
        with life.store._connect() as db:
            with db:
                db.execute(
                    "INSERT INTO life_project_job VALUES(?,?,?)",
                    (
                        project.project_id, later.job_id,
                        (now + timedelta(seconds=5)).isoformat(),
                    ),
                )
        result = life.tick(now=now + timedelta(seconds=6), busy=True)
        assert result["terminal_run_projects_settled"] == 1
        assert life._project(project.project_id).status is ProjectStatus.PAUSED
        assert life.store.jobs(project.project_id) == (
            first.job_id, later.job_id,
        )
        assert life.work_store.get(later.job_id).status is WorkStatus.QUEUED
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()


def test_unverified_older_run_failure_never_overrides_newer_work(tmp_path):
    """Absent original terminal source cannot be projected as verified."""
    import sqlite3
    from sofia.core.creative import ArtifactKind

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, first = _queued_job(life, now)
        life.work_store.transition(
            first.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.BLOCKED, reason="unverified diagnostic",
            now=now + timedelta(seconds=4),
        )
        # The original durable event, not the mutable RUN status field,
        # proves a terminal effect. Remove it for a corrupt-history fixture.
        with sqlite3.connect(life.path) as db:
            db.execute(
                "DELETE FROM autonomous_work_event "
                "WHERE job_id=? AND to_status='blocked'",
                (first.job_id,),
            )
        assert life.store.reconcile_run_outcomes(now=now + timedelta(seconds=5)) == ()
        report = life.tick(now=now + timedelta(seconds=6), busy=True)
        assert report["terminal_run_projects_settled"] == 0
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
    finally:
        life.close()


def test_terminal_run_proof_refuses_mismatched_original_reason(tmp_path):
    """An actual RUN status cannot launder a false derived failure reason."""
    import sqlite3

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.BLOCKED, reason="original SAFE denied this job",
            now=now + timedelta(seconds=4),
        )
        receipt = life.store.reconcile_run_outcomes(
            now=now + timedelta(seconds=5),
        )[0]
        assert receipt.reason == "original SAFE denied this job"
        with sqlite3.connect(life.path) as db:
            db.execute(
                "UPDATE life_run_outcome_observation SET run_reason=? "
                "WHERE run_event_id=?",
                ("false operator approval occurred", receipt.run_event_id),
            )
        assert life.store.exact_original_run_outcome(
            project_id=project.project_id, job_id=job.job_id, status="blocked",
        ) is None
        assert life._reconcile_terminal_run_projects(
            now=now + timedelta(seconds=6),
        ) == 0
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()


def test_terminal_run_proof_refuses_observation_predating_original_event(
    tmp_path,
):
    """A derived observation cannot truthfully precede its source event."""
    import sqlite3

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.UNCERTAIN, reason="original effect unknown",
            now=now + timedelta(seconds=4),
        )
        receipt = life.store.reconcile_run_outcomes(
            now=now + timedelta(seconds=5),
        )[0]
        with sqlite3.connect(life.path) as db:
            db.execute(
                "UPDATE life_run_outcome_observation SET observed_at=? "
                "WHERE run_event_id=?",
                ((now + timedelta(seconds=3)).isoformat(),
                 receipt.run_event_id),
            )
        assert life.store.exact_original_run_outcome(
            project_id=project.project_id, job_id=job.job_id, status="uncertain",
        ) is None
        assert life._reconcile_terminal_run_projects(
            now=now + timedelta(seconds=6),
        ) == 0
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
    finally:
        life.close()


def test_original_run_source_rejects_malformed_observation_timestamp(tmp_path):
    """A corrupted timestamp is unknown evidence, not an exception or a grant."""
    import sqlite3

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.BLOCKED, reason="safe policy blocked execution",
            now=now + timedelta(seconds=4),
        )
        receipt = life.store.reconcile_run_outcomes(
            now=now + timedelta(seconds=5),
        )[0]
        with sqlite3.connect(life.path) as db:
            db.execute(
                "UPDATE life_run_outcome_observation SET observed_at=? "
                "WHERE run_event_id=?",
                ("not-an-ISO-timestamp", receipt.run_event_id),
            )
        assert life.store.exact_original_run_outcome(
            project_id=project.project_id, job_id=job.job_id, status="blocked",
        ) is None
        assert life._reconcile_terminal_run_projects(
            now=now + timedelta(seconds=6),
        ) == 0
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
    finally:
        life.close()



def test_run_outcome_waits_for_real_original_event_time(tmp_path):
    """Do not permanently ingest future RUN chronology before it becomes real."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        future = now + timedelta(hours=2)
        life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.UNCERTAIN,
            reason="original worker outcome must await its timestamp",
            now=future,
        )
        assert life.store.reconcile_run_outcomes(
            now=now + timedelta(hours=1),
        ) == ()
        assert life.store.exact_original_run_outcome(
            project_id=project.project_id, job_id=job.job_id,
            status="uncertain",
        ) is None
        receipts = life.store.reconcile_run_outcomes(
            now=future + timedelta(seconds=1),
        )
        assert len(receipts) == 1
        assert receipts[0].run_at == future
        assert receipts[0].observed_at > receipts[0].run_at
        assert life.store.exact_original_run_outcome(
            project_id=project.project_id, job_id=job.job_id,
            status="uncertain",
        ) == receipts[0]
        assert life.store.reconcile_run_outcomes(
            now=future + timedelta(seconds=2),
        ) == ()
    finally:
        life.close()


def test_malformed_original_run_timestamp_is_not_ingested(tmp_path):
    """Bad original event time is unknown, not a durable false observation."""
    import sqlite3

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, job = _queued_job(life, now)
        life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.BLOCKED,
            reason="original SAFE decision blocked the work",
            now=now + timedelta(seconds=4),
        )
        with sqlite3.connect(life.path) as db:
            event_id = db.execute(
                "SELECT event_id FROM autonomous_work_event "
                "WHERE job_id=? AND to_status='blocked'",
                (job.job_id,),
            ).fetchone()[0]
            db.execute(
                "UPDATE autonomous_work_event SET occurred_at=? "
                "WHERE event_id=?",
                ("invalid-source-event-time", event_id),
            )
        assert life.store.reconcile_run_outcomes(
            now=now + timedelta(seconds=6),
        ) == ()
        assert life.store.exact_original_run_outcome(
            project_id=project.project_id, job_id=job.job_id,
            status="blocked",
        ) is None
        with sqlite3.connect(life.path) as db:
            db.execute(
                "UPDATE autonomous_work_event SET occurred_at=? "
                "WHERE event_id=?",
                ((now + timedelta(seconds=4)).isoformat(), event_id),
            )
        receipts = life.store.reconcile_run_outcomes(
            now=now + timedelta(seconds=7),
        )
        assert len(receipts) == 1
        assert receipts[0].run_event_id == event_id
        assert receipts[0].run_at <= receipts[0].observed_at
    finally:
        life.close()



def test_old_uncertain_run_blocks_motivation_and_dependency_review(tmp_path):
    """New queued work cannot hide an earlier uncertain original RUN event."""
    import sqlite3

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, first = _queued_job(life, now)
        life.work_store.transition(
            first.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.UNCERTAIN,
            reason="older original result is unconfirmed",
            now=now + timedelta(seconds=4),
        )
        later = life.manager.submit(
            kind="life-create-artifact",
            fingerprint="life-newest-queued-hides-old-uncertain-test",
            payload={
                "project_id": project.project_id,
                "goal_id": project.goal_id,
                "project_revision": project.revision,
                "goal_revision": 1,
                "capability_name": "creative.artifact.create",
                "parameters": {"request_id": "request:second-unexecuted"},
                "requested_scope": project.project_id,
                "rationale": "source fixture only, no execution",
            },
            priority=1, resource_cost=1, risk="isolated_change",
            completion_condition="Must not execute during source audit",
            now=now + timedelta(seconds=5),
            deadline=now + timedelta(minutes=1),
        )
        with sqlite3.connect(life.path) as db:
            db.execute(
                "INSERT INTO life_project_job VALUES(?,?,?)",
                (
                    project.project_id, later.job_id,
                    (now + timedelta(seconds=5)).isoformat(),
                ),
            )
        signal = next(
            signal for signal in life.motivation_signals(
                now=now + timedelta(seconds=6),
                busy=False, resource_pressure=0,
            ) if signal.project_id == project.project_id
        )
        assert signal.eligible is False
        assert "prior_run_needs_settlement" in signal.reason
        assert signal.uncertainty == 1.0
        view = next(
            row for row in life.goal_dependency_view(
                now=now + timedelta(seconds=6),
            ) if row["project_id"] == project.project_id
        )
        assert view["latest_run_job_id"] == later.job_id
        assert view["next_action_source_job_id"] == first.job_id
        assert view["next_action_candidate"] == "ask"
        assert "run_effect_uncertain" in view["blockers"]
        assert set(view["unsettled_job_ids"]) == {first.job_id, later.job_id}
        assert view["eligible_for_new_work"] is False
        assert life.work_store.get(later.job_id).status is WorkStatus.QUEUED
    finally:
        life.close()
