"""Real LIFE/RUN/CREATIVE milestone settlement contracts (deferred execution).

These use the same canonical SQLite/application-owned coordinator composition
as Project Forge's existing integration harness; no fake RUN completion or
model-generated objective result may be used as a milestone receipt.
"""
from datetime import timedelta

import pytest

from sofia.creative import ArtifactKind
from sofia.life import (
    MilestoneStatus, PersonalJudgment, ProjectIdea, ProjectStatus,
    TechnicalOutcome,
)
from sofia.run.work import WorkStatus

from test.test_life_project_forge import infrastructure, wait_for_job


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_run, pytest.mark.pkg_interact]


def prepared_project(life, now):
    evidence = life.record_observation(
        kind="creative-interest",
        source="test:explicit-interest",
        assertion="A real evidence-backed interest exists for the test project.",
        now=now,
    )
    interest = life.revise_interest(
        name="verified-violet-map",
        context="creative",
        strength=0.9,
        confidence=0.9,
        reason="Recorded original creative interest.",
        evidence_refs=(evidence,),
        now=now,
    )
    idea = ProjectIdea(
        "idea:verified-violet-map", "Violet Map",
        "Write a bounded document about a fictional violet map.",
        interest.interest_id,
        ("text_contains:violet sparks", "text_contains:quiet constellations"),
        (), "text", (evidence,), 0.9, 0.9, now,
    )
    project = life.invent_project(idea)
    life.propose_project(
        project.project_id, reason="Both objectives can be checked against file bytes.",
        evidence_refs=(evidence,), now=now + timedelta(seconds=1),
    )
    project = life.activate_project(
        project.project_id, reason="Original creative work is authorized.",
        evidence_refs=(evidence,), now=now + timedelta(seconds=2),
    )
    return project, evidence


def complete_real_job(life, project, evidence, now, content):
    job = life.schedule_artifact(
        project.project_id, artifact_kind=ArtifactKind.TEXT,
        title="Violet Map", specification={"content": content},
        evidence_ref=evidence, now=now + timedelta(seconds=3),
    )
    life.manager.tick(now=now + timedelta(seconds=3))
    assert wait_for_job(life, job.job_id).status is WorkStatus.COMPLETED
    return life.work_store.get(job.job_id)


def test_background_life_marks_original_objectives_from_real_artifact(tmp_path):
    life, goals, now = infrastructure(tmp_path)
    try:
        project, evidence = prepared_project(life, now)
        job = complete_real_job(
            life, project, evidence, now,
            "Violet sparks ripple across quiet constellations. The map is original and complete.",
        )
        result = life.tick(now=now + timedelta(seconds=8))
        assert result["follow_through"] == "independently_completed"
        assert life._project(project.project_id).status is ProjectStatus.COMPLETED
        milestones = life.store.milestones(project.project_id)
        assert len(milestones) == 2
        assert all(m.status is MilestoneStatus.COMPLETED for m in milestones)
        assert all(m.evidence_refs == (job.result["evidence_ref"],) for m in milestones)
        assert all(job.job_id in m.result for m in milestones)
        assert len(life.store.evaluations(project.project_id)) == 1
        # Restart-safe: a terminal project cannot replay milestones or work.
        old = tuple((m.milestone_id, m.updated_at) for m in milestones)
        life.tick(now=now + timedelta(seconds=9))
        assert old == tuple(
            (m.milestone_id, m.updated_at)
            for m in life.store.milestones(project.project_id)
        )
    finally:
        life.close()


def test_evaluation_crash_window_resumes_milestones_without_redrafting(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = prepared_project(life, now)
        job = complete_real_job(
            life, project, evidence, now,
            "Violet sparks have appeared but the other criterion has not.",
        )
        artifact_id = str(job.result["artifact_id"])
        receipt = str(job.result["evidence_ref"])
        # Simulate interruption immediately after durable evaluation commit
        # but before the background work owner settled milestone rows.
        life.evaluate_artifact(
            project.project_id, artifact_id=artifact_id,
            technical_outcome=TechnicalOutcome.INVALID,
            personal_judgment=PersonalJudgment.UNKNOWN,
            objective_results={
                "text_contains:violet sparks": True,
                "text_contains:quiet constellations": False,
            },
            reason="Independent checker observed one passing and one failed criterion.",
            evidence_refs=(receipt,), preserve_for_research=False,
            now=now + timedelta(seconds=5),
        )
        assert all(
            m.status is MilestoneStatus.PLANNED
            for m in life.store.milestones(project.project_id)
        )
        outcome = life.tick(now=now + timedelta(seconds=8))
        assert outcome["follow_through"] == "revision_requires_native_drafting"
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
        first, second = life.store.milestones(project.project_id)
        assert first.status is MilestoneStatus.COMPLETED
        assert second.status is MilestoneStatus.PLANNED
        assert len(life.store.jobs(project.project_id)) == 1
        first_time = first.updated_at
        life.close()
        life, _goals2, _restart = infrastructure(tmp_path)
        life.tick(now=now + timedelta(seconds=9))
        assert life.store.milestones(project.project_id)[0].updated_at == first_time
        assert len(life.store.jobs(project.project_id)) == 1
    finally:
        life.close()


def test_unsupported_or_unrelated_evidence_never_advances_milestone(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = prepared_project(life, now)
        job = complete_real_job(
            life, project, evidence, now,
            "Violet sparks appear, but no other mapped stars are shown.",
        )
        observation = life.record_observation(
            kind="unrelated",
            source="test:unrelated",
            assertion="This is not the completed RUN operation receipt.",
            now=now + timedelta(seconds=5),
        )
        life.evaluate_artifact(
            project.project_id, artifact_id=str(job.result["artifact_id"]),
            technical_outcome=TechnicalOutcome.INVALID,
            personal_judgment=PersonalJudgment.UNKNOWN,
            objective_results={
                "text_contains:violet sparks": True,
                "text_contains:quiet constellations": False,
            },
            reason="A recorded evaluation without the actual RUN receipt.",
            evidence_refs=(observation,), preserve_for_research=False,
            now=now + timedelta(seconds=6),
        )
        life.tick(now=now + timedelta(seconds=8))
        assert all(
            m.status is MilestoneStatus.PLANNED
            for m in life.store.milestones(project.project_id)
        )
    finally:
        life.close()
