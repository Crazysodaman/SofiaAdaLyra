"""CA-2216 canonical LIFE diagnostic projection. Authored, not run."""
from datetime import timedelta

from sofia.life.model import ProjectStatus
from sofia.run.work import WorkStatus
from test.test_life_project_forge import infrastructure, active_project


def test_empty_life_reports_idleness_without_fabricated_interest(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        result = life.operator_diagnostics(now=now)
        assert result["condition"] == "idle_no_project"
        assert result["source"] == "life_project"
        assert result["projects"] == ()
    finally:
        life.close()


def test_active_project_diagnostic_reads_project_and_run_sources(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _evidence = active_project(life, now)
        ready = life.operator_diagnostics(now=now + timedelta(seconds=3))
        assert ready["condition"] == "ready"
        assert ready["projects"][0]["project_id"] == project.project_id
        assert ready["projects"][0]["source"] == "life_project.status"
        assert ready["projects"][0]["has_verified_completion"] is False

        from sofia.creative import ArtifactKind
        evidence = life.record_observation(
            kind="operator-diagnostic", source="test:known",
            assertion="Trace one persistent RUN outcome", now=now,
        )
        job = life.schedule_artifact(
            project.project_id,
            artifact_kind=ArtifactKind.TEXT, title=project.name,
            specification={"content": "Operator diagnostic source."},
            evidence_ref=evidence, now=now + timedelta(seconds=4),
        )
        life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.UNCERTAIN,
            reason="Original RUN outcome cannot be proven",
            now=now + timedelta(seconds=5),
        )
        life.store.reconcile_run_outcomes(now=now + timedelta(seconds=5))
        result = life.operator_diagnostics(now=now + timedelta(seconds=6))
        assert result["condition"] == "uncertain"
        info = result["projects"][0]
        assert info["condition"] == "uncertain"
        assert info["source_job_id"] == job.job_id
        assert info["last_run_status"] == "uncertain"
        assert info["last_run_event_id"] is not None
        assert info["has_verified_completion"] is False
        assert life.store.get(
            project.project_id,
            owner_principal_id=project.owner_principal_id,
            audience_id=project.audience_id,
        ).status is ProjectStatus.ACTIVE
    finally:
        life.close()


def test_quiet_diagnostics_are_read_only_and_override_selection(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _ = active_project(life, now)
        life.store.choose_quiet(
            until_at=now + timedelta(hours=1),
            reason="Sofía chose an hour of quiet time", now=now,
        )
        before = life.store.events(
            project.project_id, owner_principal_id=project.owner_principal_id,
            audience_id=project.audience_id,
        )
        result = life.operator_diagnostics(now=now + timedelta(minutes=5))
        assert result["condition"] == "idle_by_choice"
        assert result["source"] == "life_quiet_choice"
        assert result["quiet_until"]
        assert result["projects"][0]["condition"] == "eligible"
        assert life.store.events(
            project.project_id, owner_principal_id=project.owner_principal_id,
            audience_id=project.audience_id,
        ) == before
    finally:
        life.close()


def test_life_goal_dependency_view_shows_original_prerequisites(tmp_path):
    """Only original scoped LIFE/GOALS/milestone records define the work plan."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _evidence = active_project(life, now)
        before = life.store.events(
            project.project_id,
            owner_principal_id=project.owner_principal_id,
            audience_id=project.audience_id,
        )
        first = life.goal_dependency_view(now=now + timedelta(seconds=3))
        assert len(first) == 1
        row = first[0]
        assert row["project_id"] == project.project_id
        assert row["goal_id"] == project.goal_id
        assert row["goal_status"] == "active"
        assert row["goal_revision"] is not None
        assert row["project_revision"] == project.revision
        assert row["priority"] == project.priority
        assert row["needed_objective_evidence"] == project.brief.objectives
        assert row["review_decision_key"].startswith("life-review:")
        assert row["review_due_at"] == project.updated_at.isoformat()
        assert row["awaiting_verification"] is False
        assert row["next_milestone_id"] is not None
        assert row["next_milestone_actionable_since"] is not None
        assert row["unsettled_job_ids"] == ()
        assert row["blockers"] == ()
        assert row["eligible_for_new_work"] is True
        assert row["next_action_candidate"] == "explore"
        assert row["next_action_source_job_id"] is None
        assert life.operator_diagnostics(now=now + timedelta(seconds=3))[
            "goal_dependencies"
        ] == first
        assert life.goal_dependency_view(now=now + timedelta(seconds=3)) == first
        assert life.store.events(
            project.project_id,
            owner_principal_id=project.owner_principal_id,
            audience_id=project.audience_id,
        ) == before
    finally:
        life.close()


def test_life_goal_dependency_view_preserves_uncertain_run_and_approval(tmp_path):
    """Outstanding effects and approvals are blockers, not made-up milestones."""
    from sofia.creative import ArtifactKind

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        job = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="Scoped dependency",
            specification={"content": "Existing queued creative work."},
            evidence_ref=evidence, now=now + timedelta(seconds=3),
        )
        life.work_store.transition(
            job.job_id, expected=(WorkStatus.QUEUED,),
            status=WorkStatus.WAITING_APPROVAL,
            reason="Original SAFE approval required",
            now=now + timedelta(seconds=4),
        )
        pending = life.goal_dependency_view(now=now + timedelta(seconds=5))[0]
        assert pending["unsettled_job_ids"] == (job.job_id,)
        assert pending["latest_run_status"] == "waiting_approval"
        assert "operator_approval_pending" in pending["blockers"]
        assert pending["eligible_for_new_work"] is False
        assert pending["next_action_candidate"] == "ask"
        assert pending["next_action_source_job_id"] == job.job_id
        life.work_store.transition(
            job.job_id, expected=(WorkStatus.WAITING_APPROVAL,),
            status=WorkStatus.UNCERTAIN,
            reason="Effect outcome unknown; never auto-retry",
            now=now + timedelta(seconds=6),
        )
        unknown = life.goal_dependency_view(now=now + timedelta(seconds=7))[0]
        assert unknown["unsettled_job_ids"] == (job.job_id,)
        assert unknown["latest_run_status"] == "uncertain"
        assert "run_effect_uncertain" in unknown["blockers"]
        assert unknown["eligible_for_new_work"] is False
        assert unknown["next_action_candidate"] == "ask"
        assert "no automatic retry" in unknown["next_action_reason"]
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()


def test_goal_dependency_view_reports_budget_exhaustion_without_running_work(
    tmp_path,
):
    """Actual recorded daily usage, not guessed hardware capacity, blocks work."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _ = active_project(life, now)
        budget = project.brief.resource_budget
        life.store.add_usage(
            project_id=project.project_id,
            usage_day=now.date(),
            cpu_seconds=0, gpu_seconds=0,
            wall_seconds=budget.daily_seconds,
            storage_bytes=budget.storage_bytes,
        )
        row = life.goal_dependency_view(now=now)[0]
        assert "daily_time_budget_exhausted" in row["blockers"]
        assert "daily_storage_budget_exhausted" in row["blockers"]
        assert row["eligible_for_new_work"] is False
        assert row["next_action_candidate"] == "rest"
        assert row["unsettled_job_ids"] == ()
        assert life.store.jobs(project.project_id) == ()
    finally:
        life.close()


def test_life_goal_dependency_completed_run_requires_independent_review(tmp_path):
    """A completed RUN job never becomes an automatic objective-success oracle."""
    from sofia.creative import ArtifactKind

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        job = life.schedule_artifact(
            project.project_id,
            artifact_kind=ArtifactKind.TEXT,
            title="Review-required original artifact",
            specification={"content": "Foxfire writing with an explicit criterion."},
            evidence_ref=evidence, now=now + timedelta(seconds=3),
        )
        life.work_store.transition(
            job.job_id,
            expected=(WorkStatus.QUEUED,),
            status=WorkStatus.COMPLETED,
            reason="RUN completion by itself is not objective proof",
            now=now + timedelta(seconds=4),
            result={"artifact_id": "artifact:unverified", "revision": 1},
        )
        row = life.goal_dependency_view(now=now + timedelta(seconds=5))[0]
        assert row["latest_run_status"] == "completed"
        assert row["next_action_candidate"] == "verify"
        assert row["awaiting_verification"] is True
        assert row["review_due_at"] == (
            now + timedelta(seconds=4)
        ).isoformat()
        assert row["review_decision_key"].startswith("life-review:")
        assert row["eligible_for_new_work"] is False
        assert row["next_action_source_job_id"] == job.job_id
        assert row["unresolved_milestones"]
        assert "Completed RUN receipt" in row["next_action_reason"]
        assert life.store.evaluations(project.project_id) == ()
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()


def test_completed_life_diagnostic_revokes_current_proof_after_byte_change(tmp_path):
    """Historical COMPLETED is not proof that the artifact still passes."""
    from sofia.life import PersonalJudgment, TechnicalOutcome
    from test.test_life_project_forge import (
        authored_foxfire_text, wait_for_job,
    )

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        life.tick(
            now=now + timedelta(seconds=3), generate=authored_foxfire_text,
        )
        job = wait_for_job(life, life.store.jobs(project.project_id)[0])
        assert job.status is WorkStatus.COMPLETED
        artifact_id = str(job.result["artifact_id"])
        life.evaluate_artifact(
            project.project_id, artifact_id=artifact_id,
            technical_outcome=TechnicalOutcome.VALID,
            personal_judgment=PersonalJudgment.UNKNOWN,
            objective_results={"text_contains:Foxfire": True},
            reason="Original criterion is supported by the real artifact.",
            evidence_refs=(str(job.result["evidence_ref"]),),
            preserve_for_research=False, now=now + timedelta(seconds=4),
        )
        life.complete(
            project.project_id,
            reason="Original typed criterion verified.",
            now=now + timedelta(seconds=5),
        )
        verified = life.operator_diagnostics(
            now=now + timedelta(seconds=6),
        )["projects"][0]
        assert verified["has_verified_completion"] is True
        path, _media = life.creative_explorer.verified_preview(
            artifact_id, owner_principal_id="sofia", audience_id="local:text",
        )
        path.write_text("Content changed and the original digest was invalidated.")
        afterward = life.operator_diagnostics(
            now=now + timedelta(seconds=7),
        )["projects"][0]
        assert afterward["project_status"] == "completed"
        assert afterward["has_verified_completion"] is False
        assert life._project(project.project_id).status is ProjectStatus.COMPLETED
    finally:
        life.close()


def test_life_review_decision_key_is_stable_until_original_source_changes(
    tmp_path,
):
    """A new clock tick cannot mint a new LIFE decision without source change."""
    from sofia.creative import ArtifactKind

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        first = life.goal_dependency_view(now=now + timedelta(seconds=3))[0]
        later = life.goal_dependency_view(now=now + timedelta(hours=1))[0]
        assert later["review_decision_key"] == first["review_decision_key"]
        assert later["review_due_at"] == first["review_due_at"]
        job = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="Original source change",
            specification={"content": "A new pending original creative request."},
            evidence_ref=evidence, now=now + timedelta(hours=1, seconds=3),
        )
        pending = life.goal_dependency_view(
            now=now + timedelta(hours=1, seconds=4),
        )[0]
        assert pending["review_decision_key"] != first["review_decision_key"]
        assert pending["latest_run_job_id"] == job.job_id
        assert pending["awaiting_verification"] is False
        assert pending["next_action_candidate"] == "wait"
    finally:
        life.close()
