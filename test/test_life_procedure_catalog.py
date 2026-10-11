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


def test_original_life_draft_cites_only_current_twice_verified_procedure(
    tmp_path,
):
    """The third creative project sees source proof, never implicit tool rights."""
    from sofia.cognition.model import CognitiveResponse
    from sofia.life.draft_agent import ProjectDraftAgent

    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, evidence, now)
        second_start = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, first, second_start,
        )
        _original_authorized_completion(
            life, second, second_evidence, second_start,
        )
        assert life._reconcile_procedure_catalog(
            now=second_start + timedelta(seconds=8),
        ) == 2
        third_start = now + timedelta(minutes=2)
        third, _source = _second_same_capability_project(
            life, first, third_start,
        )
        original = life._current_verified_procedures_for_draft(
            third, now=third_start + timedelta(seconds=3),
        )
        assert len(original) == 1
        assert original[0].verified_projects == 2
        captured = []
        def model(request):
            captured.append(request)
            return CognitiveResponse(content=json.dumps({
                "content": (
                    "Foxfire is a new original story authored with an explicit "
                    "creative objective; this is not a copied prior artifact."
                ),
            }))
        specification = ProjectDraftAgent(model).draft(
            third, ArtifactKind.TEXT, verified_precedents=original,
        )
        assert "Foxfire" in specification["content"]
        assert captured[0].allow_tools is False
        assert "verified_precedents_non_authoritative" in captured[0].messages[1].content
        assert original[0].procedure_id in captured[0].messages[1].content
        assert "reproduce_original_work" in captured[0].messages[1].content
        assert life.store.jobs(third.project_id) == ()
    finally:
        life.close()


def test_procedure_source_rot_is_not_reused_for_subsequent_life_draft(
    tmp_path,
):
    """Current source invalidation withdraws precedents before model use."""
    from sofia.life.draft_agent import ProjectDraftAgent

    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        first_job, _ = _original_authorized_completion(
            life, first, evidence, now,
        )
        second_start = now + timedelta(minutes=1)
        second, evidence2 = _second_same_capability_project(
            life, first, second_start,
        )
        _original_authorized_completion(life, second, evidence2, second_start)
        assert life._reconcile_procedure_catalog(
            now=second_start + timedelta(seconds=8),
        ) == 2
        third, _ = _second_same_capability_project(
            life, first, now + timedelta(minutes=2),
        )
        first_path, _media = life.creative_explorer.verified_preview(
            str(first_job.result["artifact_id"]),
            owner_principal_id="sofia", audience_id="local:text",
        )
        first_path.write_text("Changed content invalidates the prior proof.")
        assert life._current_verified_procedures_for_draft(
            third, now=now + timedelta(minutes=2, seconds=4),
        ) == ()
        assert life.store.jobs(third.project_id) == ()
    finally:
        life.close()


def test_catalog_writer_rejects_stale_bytes_even_when_original_run_was_completed(
    tmp_path,
):
    """A future direct caller cannot promote old success labels after corruption."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, observation = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        job, receipt = _original_authorized_completion(
            life, project, observation, now,
        )
        artifact = str(job.result["artifact_id"])
        original, _mime = life.creative_explorer.verified_preview(
            artifact, owner_principal_id="sofia", audience_id="local:text",
        )
        original.write_text(
            "The source bytes changed after the original RUN receipt.",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="current original creative bytes"):
            life.procedures.record_verified_attempt(
                project=life._project(project.project_id),
                job_id=job.job_id,
                original_run_evidence_ref=receipt,
                now=now + timedelta(seconds=8),
            )
        assert life.procedures.has_source_project(project.project_id) is False
        assert life._reconcile_procedure_catalog(
            now=now + timedelta(seconds=9),
        ) == 0
    finally:
        life.close()
