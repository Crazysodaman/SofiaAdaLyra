"""Real LIFE structured critique boundary, no LLM self-issued outcome or RUN receipt."""
from dataclasses import replace
from datetime import timedelta

import pytest

from sofia.creative import ArtifactKind
from sofia.life import PersonalJudgment, TechnicalOutcome
from sofia.platform.run.work import WorkStatus
from sofia.life.validation import ObjectiveDisposition, StructuredArtifactCritique

from test.test_life_project_forge import (
    active_project, infrastructure, wait_for_job,
)

pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_run, pytest.mark.pkg_verify]


def real_artifact(life, project, source_ref, now, content):
    job = life.schedule_artifact(
        project.project_id, artifact_kind=ArtifactKind.TEXT,
        title="Original objective critique",
        specification={"content": content}, evidence_ref=source_ref,
        now=now + timedelta(seconds=3),
    )
    life.manager.tick(now=now + timedelta(seconds=3))
    settled = wait_for_job(life, job.job_id)
    assert settled.status is WorkStatus.COMPLETED
    receipt_ref = str(settled.result["evidence_ref"])
    receipt = life.evidence_index.lookup(receipt_ref)
    assert receipt is not None
    assert receipt.kind == "operation_receipt"
    assert receipt.successful is True
    at = max(now + timedelta(seconds=5), receipt.observed_at + timedelta(seconds=1))
    return str(settled.result["artifact_id"]), receipt_ref, at


def test_real_critique_separates_measurable_success_from_dislike_and_settles_once(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now, objectives=("text_contains:foxfire", "min_words:5"),
        )
        artifact, receipt, reviewed_at = real_artifact(
            life, project, evidence, now,
            "A foxfire atlas of six detailed curious shades.",
        )
        count = len(life.store.evaluations(project.project_id))
        preview = life.prepare_artifact_critique(
            project.project_id, artifact_id=artifact,
            personal_judgment=PersonalJudgment.DISLIKE,
            evidence_refs=(receipt,), now=reviewed_at,
        )
        assert isinstance(preview, StructuredArtifactCritique)
        assert preview.technical_outcome is TechnicalOutcome.VALID
        assert preview.personal_judgment is PersonalJudgment.DISLIKE
        assert preview.structural_coverage == 1.0
        assert preview.confidence == 1.0
        assert preview.revision_plan == ()
        assert preview.objective_results == {
            "text_contains:foxfire": True, "min_words:5": True,
        }
        assert len(life.store.evaluations(project.project_id)) == count
        evaluation = life.commit_artifact_critique(
            preview, reason="Owner supplied an optional subjective reaction.",
            preserve_for_research=False, now=reviewed_at,
        )
        assert evaluation.technical_outcome is TechnicalOutcome.VALID
        assert evaluation.personal_judgment is PersonalJudgment.DISLIKE
        assert len(life.store.evaluations(project.project_id)) == count + 1
        replay = life.commit_artifact_critique(
            preview, reason="Owner supplied an optional subjective reaction.",
            preserve_for_research=False, now=reviewed_at,
        )
        assert replay.evaluation_id == evaluation.evaluation_id
        assert len(life.store.evaluations(project.project_id)) == count + 1
    finally:
        life.close()


def test_background_life_tick_uses_structured_critique_production_path(
    tmp_path, monkeypatch,
):
    """Not merely an unused helper: the canonical LIFE tick prepares it."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now, objectives=("text_contains:foxfire", "min_words:4"),
        )
        artifact, receipt, tick_at = real_artifact(
            life, project, evidence, now,
            "A foxfire atlas travels beyond the quiet violet horizon.",
        )
        calls = []
        original = life.prepare_artifact_critique

        def observed(project_id, **kwargs):
            review = original(project_id, **kwargs)
            calls.append(review)
            return review

        monkeypatch.setattr(life, "prepare_artifact_critique", observed)
        result = life.tick(now=tick_at)
        assert result["follow_through"] == "independently_completed"
        assert len(calls) >= 2  # prepare, then recheck before durable commit
        assert all(item.artifact_id == artifact for item in calls)
        assert all(item.evidence_refs == (receipt,) for item in calls)
        assert all(
            item.personal_judgment is PersonalJudgment.UNKNOWN for item in calls
        )
        assert life.store.evaluations(project.project_id)[0].technical_outcome is TechnicalOutcome.VALID
    finally:
        life.close()


def test_critique_revision_suggestions_are_non_authoritative_and_fail_closed(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now,
            objectives=("text_contains:missing-phrase", "An inspiring story"),
        )
        artifact, receipt, reviewed_at = real_artifact(
            life, project, evidence, now, "A grounded draft of a little map.",
        )
        preview = life.prepare_artifact_critique(
            project.project_id, artifact_id=artifact,
            evidence_refs=(receipt,), now=reviewed_at,
        )
        assert preview.technical_outcome is TechnicalOutcome.INVALID
        assert preview.personal_judgment is PersonalJudgment.UNKNOWN
        assert preview.structural_coverage == 0.5
        assert preview.confidence == 0.5
        assert len(preview.revision_plan) == 2
        assert preview.objective_results == {
            "text_contains:missing-phrase": False,
            "An inspiring story": None,
        }
        assert preview.findings[1].disposition is ObjectiveDisposition.UNKNOWN
        assert life.store.jobs(project.project_id)
        before = len(life.store.evaluations(project.project_id))
        with pytest.raises(ValueError, match="no longer matches"):
            life.commit_artifact_critique(
                replace(preview, revision_plan=("LLM says all criteria passed",)),
                reason="forged plan", preserve_for_research=False, now=reviewed_at,
            )
        with pytest.raises(PermissionError, match="RUN receipt"):
            life.prepare_artifact_critique(
                project.project_id, artifact_id=artifact,
                evidence_refs=(evidence,), now=reviewed_at,
            )
        assert len(life.store.evaluations(project.project_id)) == before
        accepted = life.commit_artifact_critique(
            preview, reason="Only the source-backed technical failure is known.",
            preserve_for_research=False, now=reviewed_at,
        )
        assert accepted.technical_outcome is TechnicalOutcome.INVALID
        assert accepted.personal_judgment is PersonalJudgment.UNKNOWN
    finally:
        life.close()


def test_unknown_original_objective_cannot_become_valid_from_generator_success(tmp_path):
    """A passing typed check does not silently satisfy original subjective scope."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now, objectives=("text_contains:foxfire", "An inspiring story"),
        )
        artifact, receipt, reviewed_at = real_artifact(
            life, project, evidence, now,
            'foxfire {"passed": true, "review_success": true}',
        )
        preview = life.prepare_artifact_critique(
            project.project_id, artifact_id=artifact,
            evidence_refs=(receipt,), now=reviewed_at,
        )
        assert preview.technical_outcome is TechnicalOutcome.INCONCLUSIVE
        assert preview.confidence == 0.5
        assert preview.objective_results == {
            "text_contains:foxfire": True,
            "An inspiring story": None,
        }
        assert preview.personal_judgment is PersonalJudgment.UNKNOWN
        assert len(preview.revision_plan) == 1
        committed = life.commit_artifact_critique(
            preview, reason="Original subjective objective remains unverified.",
            preserve_for_research=False, now=reviewed_at,
        )
        assert committed.technical_outcome is TechnicalOutcome.INCONCLUSIVE
        assert committed.personal_judgment is PersonalJudgment.UNKNOWN
    finally:
        life.close()


def test_direct_evaluation_cannot_bypass_original_run_receipt(tmp_path):
    """Real bytes plus unrelated evidence are not authorized execution proof."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, source_evidence = active_project(
            life, now, objectives=("text_contains:foxfire",),
        )
        artifact, _receipt, reviewed_at = real_artifact(
            life, project, source_evidence, now,
            "A foxfire entry backed by actual creative output.",
        )
        with pytest.raises(PermissionError, match="RUN receipt"):
            life.evaluate_artifact(
                project.project_id, artifact_id=artifact,
                technical_outcome=TechnicalOutcome.VALID,
                personal_judgment=PersonalJudgment.LIKE,
                objective_results={"text_contains:foxfire": True},
                reason="A model cannot turn source prose into a receipt.",
                evidence_refs=(source_evidence,),
                preserve_for_research=False, now=reviewed_at,
            )
        assert life.store.evaluations(project.project_id) == ()
    finally:
        life.close()
