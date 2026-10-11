"""Real canonical LIFE/RUN proof required for repeatable skill history.

Authored for the final user-run test campaign. No synthetic tool result is
allowed to promote a procedure or create new SAFE/RUN authority.
"""
from datetime import timedelta
import sqlite3

import pytest

from sofia.creative import ArtifactKind
from sofia.life import (
    PersonalJudgment, ProjectIdea, ProjectScope, ProjectStatus,
    TechnicalOutcome,
)
from sofia.life.procedures import LifeProcedureCatalog
from sofia.run.work import WorkStatus
from test.test_life_project_forge import (
    active_project, infrastructure, wait_for_job,
)


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_run]


def _original_authorized_completion(life, project, evidence_ref, now):
    job = life.schedule_artifact(
        project.project_id, artifact_kind=ArtifactKind.TEXT,
        title="Original repeatable Foxfire note",
        specification={
            "content": (
                "Foxfire illuminated this original story, and its independently "
                "checkable project objective appears in the stored bytes."
            ),
        },
        evidence_ref=evidence_ref, now=now + timedelta(seconds=3),
    )
    life.manager.tick(now=now + timedelta(seconds=4))
    complete_job = wait_for_job(life, job.job_id)
    assert complete_job.status is WorkStatus.COMPLETED
    assert isinstance(complete_job.result, dict)
    artifact = str(complete_job.result["artifact_id"])
    revision = complete_job.result["revision"]
    receipt = str(complete_job.result["evidence_ref"])
    evaluation = life.evaluate_artifact(
        project.project_id, artifact_id=artifact,
        technical_outcome=TechnicalOutcome.VALID,
        personal_judgment=PersonalJudgment.UNKNOWN,
        objective_results={"text_contains:Foxfire": True},
        reason="Independently inspected original text source.",
        evidence_refs=(receipt,), preserve_for_research=False,
        now=now + timedelta(seconds=5),
    )
    assert evaluation.artifact_revision == revision
    assert life.complete(
        project.project_id,
        reason="Original text predicate passed on source bytes.",
        now=now + timedelta(seconds=6),
    ).status is ProjectStatus.COMPLETED
    return complete_job, receipt


def _second_same_capability_project(life, first, now):
    observation = life.record_observation(
        kind="independent-reproducibility",
        source="test:second-original-project",
        assertion="A distinct independent Foxfire writing experiment is selected.",
        now=now,
    )
    idea = ProjectIdea(
        "idea:repeatable-foxfire-second",
        "Second Independent Foxfire Note",
        "Reproduce the typed check with an independently authored second artifact.",
        first.originating_interest,
        ("text_contains:Foxfire",), (),
        "text", (observation,), 0.89, 0.87, now,
    )
    project = life.invent_project(
        idea, scope=ProjectScope.PERSONAL_PRIVATE,
    )
    project = life.propose_project(
        project.project_id, reason="A fresh original source experiment.",
        evidence_refs=(observation,), now=now + timedelta(seconds=1),
    )
    project = life.activate_project(
        project.project_id, reason="An independent source-verifiable reproduction.",
        evidence_refs=(observation,), now=now + timedelta(seconds=2),
    )
    return project, observation


def test_two_distinct_real_checked_projects_promote_nonexecutable_procedure(
    tmp_path,
):
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        first_job, first_receipt = _original_authorized_completion(
            life, first, evidence, now,
        )
        assert life._reconcile_procedure_catalog(
            now=now + timedelta(seconds=7),
        ) == 1
        first_proof = life.procedures.has_source_project(first.project_id)
        assert first_proof
        assert life.procedures.available_for_project(first) == ()
        with sqlite3.connect(life.path) as db:
            assert db.execute(
                "SELECT status FROM life_procedure_catalog",
            ).fetchone()[0] == "candidate"
        assert life._reconcile_procedure_catalog(
            now=now + timedelta(seconds=8),
        ) == 0

        second_start = now + timedelta(minutes=1)
        second, other_evidence = _second_same_capability_project(
            life, first, second_start,
        )
        second_job, second_receipt = _original_authorized_completion(
            life, second, other_evidence, second_start,
        )
        assert first_job.job_id != second_job.job_id
        assert first_receipt != second_receipt
        assert life._reconcile_procedure_catalog(
            now=second_start + timedelta(seconds=7),
        ) == 1

        available = life.procedures.available_for_project(second)
        assert len(available) == 1
        procedure = available[0]
        assert procedure.status == "verified"
        assert procedure.verified_projects == 2
        assert procedure.version == 1
        assert procedure.exact_capabilities == second.brief.permission_requirements
        assert procedure.source_objectives == ("text_contains:Foxfire",)
        assert first_receipt in procedure.provenance_refs
        assert second_receipt in procedure.provenance_refs
        assert "no_remote_replay_authorized" in procedure.preconditions
        view = life.goal_dependency_view(
            now=second_start + timedelta(seconds=8),
        )
        assert {row["project_id"] for row in view} == {
            first.project_id, second.project_id,
        }
        assert all(
            procedure.procedure_id in row["verified_procedures"]
            for row in view
        )
        # Neither recording nor retrieval ever submits another RUN job.
        assert life.store.jobs(first.project_id) == (first_job.job_id,)
        assert life.store.jobs(second.project_id) == (second_job.job_id,)
        assert life.procedures.available_for_project(first) == available
        life.procedures.quarantine(
            procedure.procedure_id,
            reason="A human operator flagged incompatible source assumptions.",
            now=second_start + timedelta(seconds=9),
        )
        assert life.procedures.available_for_project(first) == ()
        assert life.procedures.available_for_project(second) == ()
    finally:
        life.close()


def test_procedure_catalog_refuses_fabricated_job_and_source_receipt(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        job, receipt = _original_authorized_completion(
            life, project, evidence, now,
        )
        catalog = LifeProcedureCatalog(life.path)
        with pytest.raises(ValueError, match="real original scoped RUN"):
            catalog.record_verified_attempt(
                project=project, job_id=job.job_id,
                original_run_evidence_ref="goal-evidence:imaginary",
                now=now + timedelta(seconds=7),
            )
        assert catalog.has_source_project(project.project_id) is False
        with pytest.raises(ValueError, match="real original scoped RUN"):
            catalog.record_verified_attempt(
                project=project, job_id="job:imaginary",
                original_run_evidence_ref=receipt,
                now=now + timedelta(seconds=7),
            )
        assert catalog.available_for_project(project) == ()
    finally:
        life.close()


def test_verified_procedure_quarantined_when_original_bytes_change(tmp_path):
    """A past pair of successes cannot mask current loss of source evidence."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, first_evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        first_job, _receipt = _original_authorized_completion(
            life, first, first_evidence, now,
        )
        second_start = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, first, second_start,
        )
        second_job, _receipt = _original_authorized_completion(
            life, second, second_evidence, second_start,
        )
        assert life._reconcile_procedure_catalog(
            now=second_start + timedelta(seconds=7),
        ) == 2
        assert len(life.procedures.available_for_project(first)) == 1
        original = life.goal_dependency_view(
            now=second_start + timedelta(seconds=8),
        )
        assert all(item["verified_procedures"] for item in original)
        artifact_id = str(first_job.result["artifact_id"])
        original_path, _media = life.creative_explorer.verified_preview(
            artifact_id,
            owner_principal_id="sofia",
            audience_id="local:text",
        )
        original_path.write_text(
            "These bytes are not the original independently verified work.",
            encoding="utf-8",
        )
        # Diagnostics should fail closed even before the mutation-free audit
        # gets a chance to record its quarantine decision.
        after = life.goal_dependency_view(
            now=second_start + timedelta(seconds=9),
        )
        assert not any(row["verified_procedures"] for row in after)
        assert life._audit_procedure_sources(
            now=second_start + timedelta(seconds=10),
        ) == 1
        assert life._audit_procedure_sources(
            now=second_start + timedelta(seconds=11),
        ) == 0
        assert life.procedures.available_for_project(second) == ()
        assert life.work_store.get(first_job.job_id).status is WorkStatus.COMPLETED
        assert life.work_store.get(second_job.job_id).status is WorkStatus.COMPLETED
        # Quarantine changes only the reliability of remembered procedure
        # knowledge, not historic LIFE/GOALS/RUN or file contents.
        assert life._project(first.project_id).status is ProjectStatus.COMPLETED
        assert life._project(second.project_id).status is ProjectStatus.COMPLETED
    finally:
        life.close()
