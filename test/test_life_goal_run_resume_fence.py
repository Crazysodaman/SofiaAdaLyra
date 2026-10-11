"""Deferred LIFE/GOALS/RUN authorization-state regression tests.

No live RUN work or external capability is executed by these fixtures.
"""
from datetime import timedelta

import pytest

from sofia.creative import ArtifactKind
from sofia.goals import GoalStatus, SOFIA_GOAL_OWNER_ID
from sofia.life.model import ProjectStatus
from sofia.run.work import WorkStatus
from sofia.social.principals import local_sparks_principal
from test.test_life_project_forge import infrastructure, active_project


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_run]


def _goal(goals, project):
    return next(
        item for item in goals.list_visible(local_sparks_principal())
        if item.id == project.goal_id
    )


def _transition_goal(goals, goal, before, after, when, evidence):
    return goals.transition(
        goal_id=goal.id, principal_id=goal.scope_principal_id,
        audience=goal.scope_audience, expected_status=before,
        next_status=after, actor_principal_id=SOFIA_GOAL_OWNER_ID,
        now=when, evidence_refs=(evidence,),
    )


def test_blocked_canonical_goal_pauses_active_life_without_work(tmp_path):
    life, goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        original = _goal(goals, project)
        _transition_goal(
            goals, original, GoalStatus.ACTIVE, GoalStatus.BLOCKED,
            now + timedelta(seconds=3), evidence,
        )
        before_jobs = life.store.jobs(project.project_id)
        result = life.tick(now=now + timedelta(seconds=4), busy=True)
        assert result["goal_lifecycle_projects_settled"] == 1
        assert life._project(project.project_id).status is ProjectStatus.PAUSED
        assert _goal(goals, project).status is GoalStatus.BLOCKED
        assert life.store.jobs(project.project_id) == before_jobs == ()
        assert life.tick(now=now + timedelta(seconds=5), busy=True)[
            "goal_lifecycle_projects_settled"
        ] == 0
    finally:
        life.close()


@pytest.mark.parametrize("pending", (
    WorkStatus.QUEUED, WorkStatus.RUNNING,
    WorkStatus.WAITING_APPROVAL, WorkStatus.BLOCKED,
    WorkStatus.CANCELLED, WorkStatus.UNCERTAIN, WorkStatus.FAILED,
))
def test_goal_resumption_never_reactivates_pending_or_unsafe_run(
    tmp_path, pending,
):
    life, goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        job = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="Deferred original authoring",
            specification={"content": "The work remains original and not yet validated."},
            evidence_ref=evidence, now=now + timedelta(seconds=3),
        )
        goal = _goal(goals, project)
        _transition_goal(
            goals, goal, GoalStatus.ACTIVE, GoalStatus.PAUSED,
            now + timedelta(seconds=4), evidence,
        )
        first = life.tick(now=now + timedelta(seconds=5), busy=True)
        assert first["goal_lifecycle_projects_settled"] == 1
        assert life._project(project.project_id).status is ProjectStatus.PAUSED

        if pending is not WorkStatus.QUEUED:
            life.work_store.transition(
                job.job_id, expected=(WorkStatus.QUEUED,),
                status=pending, reason="test-only recorded canonical RUN status",
                now=now + timedelta(seconds=6),
            )
        _transition_goal(
            goals, goal, GoalStatus.PAUSED, GoalStatus.ACTIVE,
            now + timedelta(seconds=7), evidence,
        )
        observed = life.tick(now=now + timedelta(seconds=8), busy=True)
        assert observed["goal_lifecycle_projects_settled"] == 0
        assert observed["jobs_started"] == 0
        assert life._project(project.project_id).status is ProjectStatus.PAUSED
        assert life.work_store.get(job.job_id).status is pending
        assert life.store.jobs(project.project_id) == (job.job_id,)
        assert _goal(goals, project).status is GoalStatus.ACTIVE
    finally:
        life.close()


def test_goal_can_resume_after_goals_pause_without_unfinished_run(tmp_path):
    life, goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        goal = _goal(goals, project)
        _transition_goal(
            goals, goal, GoalStatus.ACTIVE, GoalStatus.PAUSED,
            now + timedelta(seconds=3), evidence,
        )
        assert life.tick(now=now + timedelta(seconds=4), busy=True)[
            "goal_lifecycle_projects_settled"
        ] == 1
        _transition_goal(
            goals, goal, GoalStatus.PAUSED, GoalStatus.ACTIVE,
            now + timedelta(seconds=5), evidence,
        )
        assert life.tick(now=now + timedelta(seconds=6), busy=True)[
            "goal_lifecycle_projects_settled"
        ] == 1
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
        assert life.store.jobs(project.project_id) == ()
    finally:
        life.close()



def test_atomic_run_admission_rejects_original_life_revision_change(
    tmp_path, monkeypatch,
):
    """A pause/resume race must not admit a stale drafted RUN artifact job."""
    life, goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        original_submit = life.manager.submit
        def competing_pause_and_resume(**kwargs):
            life.pause(
                project.project_id,
                reason="Concurrently pause optional work before RUN enqueue.",
                evidence_refs=(evidence,),
                now=now + timedelta(seconds=4),
            )
            life.resume(
                project.project_id,
                reason="Resume with a new canonical project revision.",
                evidence_refs=(evidence,),
                now=now + timedelta(seconds=5),
            )
            return original_submit(**kwargs)
        monkeypatch.setattr(
            life.manager, "submit", competing_pause_and_resume,
        )
        with pytest.raises(RuntimeError, match="revision changed"):
            life.schedule_artifact(
                project.project_id,
                artifact_kind=ArtifactKind.TEXT,
                title="Stale project authoring",
                specification={"content": "Outdated creative instructions"},
                evidence_ref=evidence,
                now=now + timedelta(seconds=6),
                expected_project_revision=project.revision,
            )
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
        assert life._project(project.project_id).revision > project.revision
        assert life.store.jobs(project.project_id) == ()
        assert life.store.artifacts(project.project_id) == ()
        assert life.work_store.open_count() == 0
    finally:
        life.close()


def test_queued_creative_job_refuses_stale_life_revision_after_resume(tmp_path):
    """Queued work from before an original LIFE pause never silently restarts."""
    from test.test_life_project_forge import wait_for_job

    life, goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        job = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="Queued draft from prior LIFE revision",
            specification={"content": "No longer authorized after a pause."},
            evidence_ref=evidence, now=now + timedelta(seconds=3),
        )
        before = dict(job.payload)
        assert before["project_revision"] == project.revision
        life.pause(
            project.project_id,
            reason="Original optional work intentionally paused.",
            evidence_refs=(evidence,), now=now + timedelta(seconds=4),
        )
        resumed = life.resume(
            project.project_id,
            reason="Later work can be newly reviewed.",
            evidence_refs=(evidence,), now=now + timedelta(seconds=5),
        )
        assert resumed.revision > before["project_revision"]
        assert _goal(goals, project).status is GoalStatus.ACTIVE
        life.manager.tick(now=now + timedelta(seconds=6))
        settled = wait_for_job(life, job.job_id)
        assert settled.status is WorkStatus.BLOCKED
        assert "original_authority_changed" in settled.reason
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()


def test_queued_creative_job_refuses_stale_goals_revision_without_life_tick(
    tmp_path,
):
    """Even fast GOALS pause/resume before LIFE polling invalidates queued work."""
    from test.test_life_project_forge import wait_for_job

    life, goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        job = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="Queued draft from prior GOALS revision",
            specification={"content": "GOALS authority has changed."},
            evidence_ref=evidence, now=now + timedelta(seconds=3),
        )
        original_goal = _goal(goals, project)
        paused = _transition_goal(
            goals, original_goal, GoalStatus.ACTIVE, GoalStatus.PAUSED,
            now + timedelta(seconds=4), evidence,
        )
        _transition_goal(
            goals, paused, GoalStatus.PAUSED, GoalStatus.ACTIVE,
            now + timedelta(seconds=5), evidence,
        )
        assert life._project(project.project_id).revision == project.revision
        assert _goal(goals, project).revision > job.payload["goal_revision"]
        life.manager.tick(now=now + timedelta(seconds=6))
        settled = wait_for_job(life, job.job_id)
        assert settled.status is WorkStatus.BLOCKED
        assert "original_authority_changed" in settled.reason
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()


def test_background_draft_handles_atomic_project_revision_race_without_crash(
    tmp_path, monkeypatch,
):
    """A lost LIFE admission CAS is deferred, never retried as a fresh effect."""
    from test.test_life_autonomous_followthrough import typed_active_project
    from sofia.cognition.model import CognitiveResponse
    import json

    life, _goals, now = infrastructure(tmp_path)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        submit = life.manager.submit

        def change_revision_at_atomic_enqueue(**kwargs):
            life.pause(
                project.project_id, reason="Source changed before RUN admit.",
                evidence_refs=(), now=now + timedelta(seconds=4),
            )
            life.resume(
                project.project_id, reason="Source changed again before RUN admit.",
                evidence_refs=(), now=now + timedelta(seconds=5),
            )
            return submit(**kwargs)

        monkeypatch.setattr(
            life.manager, "submit", change_revision_at_atomic_enqueue,
        )
        result = life.tick(
            now=now + timedelta(seconds=6),
            generate=lambda request: CognitiveResponse(
                content=json.dumps({
                    "content": "Foxfire is a verified word in this newly drafted "
                               "creative text, but source revision changed."
                }),
            ),
        )
        assert result["scheduled"] == 0
        assert result["follow_through"] == "authority_changed_during_draft"
        assert life.store.jobs(project.project_id) == ()
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()
