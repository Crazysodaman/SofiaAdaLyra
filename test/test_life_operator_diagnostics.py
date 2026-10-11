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
