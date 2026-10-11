"""Production LIFE background follow-through: real work, evidence, revision.

Tests are deliberately authored but NOT run until the final user-authorized
verification campaign. No simulated receipt may count as project success.
"""
from datetime import datetime, timedelta, timezone
import json

from sofia.cognition.model import CognitiveResponse
from sofia.life import (
    PersonalJudgment, ProjectIdea, ProjectScope, ProjectStatus,
    TechnicalOutcome,
)
from sofia.run.work import WorkStatus
from test.test_life_project_forge import (
    infrastructure, active_project, wait_for_job,
)


def typed_active_project(life, now, *, objectives, name="A Checkable Foxfire Note"):
    observation = life.record_observation(
        kind="curiosity", source="test:typed-objective",
        assertion="A source-backed interest in original experimental stories.",
        now=now,
    )
    idea = ProjectIdea(
        "idea:checkable-foxfire", name,
        "Make a small original foxfire note with independently checkable text.",
        "foxfire-notes", objectives, (), "text", (observation,),
        0.92, 0.90, now,
    )
    project = life.invent_project(
        idea, scope=ProjectScope.PERSONAL_PRIVATE,
    )
    project = life.propose_project(
        project.project_id,
        reason="An independently checkable creative experiment is feasible.",
        evidence_refs=(observation,), now=now + timedelta(seconds=1),
    )
    project = life.activate_project(
        project.project_id,
        reason="Choose a bounded personal experiment without promising success.",
        evidence_refs=(observation,), now=now + timedelta(seconds=2),
    )
    return project


def _draft(text):
    return CognitiveResponse(content=json.dumps({"content": text}))


def test_life_auto_reviews_and_completes_only_independently_verified_artifact(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        created = life.tick(
            now=now + timedelta(seconds=3),
            generate=lambda request: _draft(
                "Foxfire gathered above the ancient orchard, lighting a "
                "very small and original fictional map."
            ),
        )
        assert created["scheduled"] == 1
        first = life.store.jobs(project.project_id)[0]
        assert wait_for_job(life, first).status is WorkStatus.COMPLETED
        completed = life.tick(now=now + timedelta(seconds=8))
        assert completed["follow_through"] == "independently_completed"
        assert life._project(project.project_id).status is ProjectStatus.COMPLETED
        evaluation = life.store.evaluations(project.project_id)[0]
        assert evaluation.technical_outcome is TechnicalOutcome.VALID
        assert evaluation.personal_judgment is PersonalJudgment.UNKNOWN
        assert evaluation.objective_results["text_contains:Foxfire"] is True

        # Completion remains idempotent, with no new creative job or judgment.
        life.tick(now=now + timedelta(seconds=9))
        assert len(life.store.jobs(project.project_id)) == 1
        assert len(life.store.evaluations(project.project_id)) == 1
    finally:
        life.close()


def test_life_revises_failed_original_text_after_daily_budget_reset(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    attempts = []

    def generator(request):
        brief = request.messages[-1].content
        attempts.append(brief)
        if len(attempts) == 1:
            return _draft(
                "Moonlight collected above the imagined valley, with "
                "no named fire or special glowing phenomenon."
            )
        return _draft(
            "Foxfire returned to the imaginary valley on the second night, "
            "and the forest's maps glowed quietly at the water's edge."
        )

    try:
        life.tick(now=now + timedelta(seconds=3), generate=generator)
        assert wait_for_job(life, life.store.jobs(project.project_id)[0]).status is WorkStatus.COMPLETED

        inspected = life.tick(now=now + timedelta(seconds=7), generate=generator)
        assert inspected["follow_through"] == "deferred_daily_draft_limit"
        assert len(life.store.evaluations(project.project_id)) == 1
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE

        next_day = now + timedelta(days=1)
        revised = life.tick(now=next_day, generate=generator)
        assert revised["follow_through"] == "revision_scheduled"
        assert revised["scheduled"] == 1
        assert "text_contains:Foxfire" in attempts[-1]
        jobs = life.store.jobs(project.project_id)
        assert len(jobs) == 2
        assert wait_for_job(life, jobs[-1]).status is WorkStatus.COMPLETED

        completed = life.tick(now=next_day + timedelta(seconds=8), generate=generator)
        assert completed["follow_through"] == "independently_completed"
        assert life._project(project.project_id).status is ProjectStatus.COMPLETED
        assert len(life.store.evaluations(project.project_id)) == 2
    finally:
        life.close()


def test_life_abstains_on_uncheckable_subjective_objectives(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project, _evidence = active_project(life, now)
    try:
        life.tick(
            now=now + timedelta(seconds=3),
            generate=lambda request: _draft(
                "Foxfire blue shifts gently toward amber in the first "
                "movement of this small imaginary color atlas."
            ),
        )
        assert wait_for_job(life, life.store.jobs(project.project_id)[0]).status is WorkStatus.COMPLETED
        result = life.tick(now=now + timedelta(seconds=8))
        assert result["follow_through"] == "needs_independent_objective_review"
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
        assert len(life.store.jobs(project.project_id)) == 1
        evals = life.store.evaluations(project.project_id)
        assert len(evals) == 1
        assert evals[0].technical_outcome is TechnicalOutcome.INCONCLUSIVE
        assert all(value is None for value in evals[0].objective_results.values())
    finally:
        life.close()


def test_life_corrupt_artifact_does_not_revise_or_complete(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        life.tick(
            now=now + timedelta(seconds=3),
            generate=lambda request: _draft(
                "Foxfire drifted above the meadow, painting the mountains "
                "of a tiny imaginary world for the first edition."
            ),
        )
        assert wait_for_job(life, life.store.jobs(project.project_id)[0]).status is WorkStatus.COMPLETED
        artifact_id, _revision = life.store.artifacts(project.project_id)[0]
        path, _media = life.creative_explorer.verified_preview(
            artifact_id, owner_principal_id="sofia", audience_id="local:text",
        )
        path.write_text("tampered", encoding="utf-8")
        result = life.tick(now=now + timedelta(seconds=8))
        assert result["follow_through"] == "artifact_integrity_review_required"
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
        assert len(life.store.jobs(project.project_id)) == 1
        assert len(life.store.evaluations(project.project_id)) == 0
        assert all(
            milestone.status.value == "planned"
            for milestone in life.store.milestones(project.project_id)
        )
        assert life._current_verified_objective_completion(
            life._project(project.project_id), now=now + timedelta(seconds=9),
        ) is False
    finally:
        life.close()


def test_life_restart_recovers_completed_artifact_and_finishes_once(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        life.tick(
            now=now + timedelta(seconds=3),
            generate=lambda request: _draft(
                "Foxfire climbed the eastern hill, marking a tiny imaginary "
                "border in an original story about learning new places."
            ),
        )
        assert wait_for_job(life, life.store.jobs(project.project_id)[0]).status is WorkStatus.COMPLETED
    finally:
        life.close()

    restarted, _goals, _ = infrastructure(tmp_path)
    try:
        completed = restarted.tick(now=now + timedelta(minutes=1))
        assert completed["follow_through"] == "independently_completed"
        assert restarted._project(project.project_id).status is ProjectStatus.COMPLETED
        assert len(restarted.store.jobs(project.project_id)) == 1
        assert len(restarted.store.evaluations(project.project_id)) == 1
    finally:
        restarted.close()
