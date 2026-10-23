from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.generalization.workflow import GeneralizationWorkflowStore, WorkflowStep
from sofia.goals import GoalEvidenceIndex, GoalService, GoalStore
from sofia.goals.evidence import GoalEvidenceLedger
from sofia.goals.model import CompletionKind, GoalCompletionCondition
from sofia.platform.run.work import DurableWorkStore, WorkStatus
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.platform.state.sqlite_plane import SQLiteStatePlane


NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)


def _principal(audience="local:text"):
    return PrincipalContext("person:sparks", audience, AudienceKind.PRIVATE, "Sparks")


def _owners(path):
    evidence = GoalEvidenceLedger(path)
    goals = GoalService(
        GoalStore(SQLiteStatePlane(path)), evidence_verifier=GoalEvidenceIndex(path),
    )
    return evidence, goals, DurableWorkStore(path)


def _record(evidence, *, ref, audience="local:text", kind="reviewed_evidence"):
    return evidence.record(
        kind=kind, observed_at=NOW, source="test:independent",
        evidence_ref=ref, principal_id="person:sparks", audience=audience,
    )


def _workflow(path):
    evidence, goals, work = _owners(path)
    principal = _principal()
    _record(evidence, ref="evidence:novel-problem")
    root = goals.create_user_goal(
        principal=principal, title="Diagnose an unfamiliar service",
        reason="Owner requested bounded investigation", base_priority=.7,
        confidence=1.0,
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner confirms all typed evidence",
        ), evidence_refs=("evidence:novel-problem",), now=NOW,
    )
    children = goals.decompose(
        parent=root, child_titles=("Inspect state", "Test hypothesis"), now=NOW,
    )
    jobs = []
    for index, child in enumerate(children):
        jobs.append(work.enqueue(
            kind="diagnostic", fingerprint=f"ga-job:{index}",
            payload={"principal_id": principal.principal_id,
                     "audience_id": principal.audience_id,
                     "goal_id": child.id},
            priority=50, resource_cost=10, risk="read_only",
            completion_condition="typed diagnostic receipt",
            now=NOW, deadline=NOW + timedelta(hours=1),
        ))
    steps = (
        WorkflowStep(
            "inspect", children[0].id, jobs[0].job_id, (),
            "Collect current state", "typed diagnostic receipt", "read_only", .9,
        ),
        WorkflowStep(
            "test", children[1].id, jobs[1].job_id, ("inspect",),
            "Discriminate the leading hypothesis", "typed diagnostic receipt",
            "read_only", .8,
        ),
    )
    owner = GeneralizationWorkflowStore(path, goals=goals)
    workflow = owner.create(
        root_goal_id=root.id, original_objective=root.title,
        principal=principal, steps=steps, evidence_ref="evidence:novel-problem",
        now=NOW, source_case_id="case:novel-1",
    )
    return evidence, goals, work, owner, principal, workflow, jobs, steps


def test_workflow_uses_existing_goals_and_run_jobs_and_survives_restart(
    canonical_state_path,
):
    evidence, goals, work, owner, principal, workflow, jobs, _steps = _workflow(
        canonical_state_path,
    )
    ready = owner.ready_steps(workflow, principal=principal)
    assert [item["step_id"] for item in ready] == ["inspect"]
    work.transition(
        jobs[0].job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.COMPLETED,
        reason="verified", result={"evidence_ref": "receipt:inspect"}, now=NOW,
    )
    assert [item["step_id"] for item in owner.ready_steps(workflow, principal=principal)] == ["test"]
    checkpoint = owner.checkpoint(
        workflow, principal=principal, now=NOW + timedelta(minutes=1),
        restart_observed=True,
    )
    assert checkpoint["unresolved"] == 1
    restarted = GeneralizationWorkflowStore(canonical_state_path, goals=goals)
    summary = restarted.resume_summary(workflow, principal=principal)
    assert summary["checkpoint"]["state_digest"] == checkpoint["state_digest"]
    assert summary["execution_authorized"] is False
    assert summary["transcript_included"] is False
    assert restarted.create(
        root_goal_id=summary["root_goal_id"],
        original_objective=summary["original_objective"], principal=principal,
        steps=_steps, evidence_ref="evidence:novel-problem", now=NOW,
        source_case_id="case:novel-1",
    ) == workflow
    assert checkpoint["states"][0]["external_controls"]["job_fingerprint"] == "ga-job:0"


def test_uncertain_external_effect_requires_evidence_backed_bounded_replan(
    canonical_state_path,
):
    evidence, goals, work, owner, principal, workflow, jobs, steps = _workflow(
        canonical_state_path,
    )
    work.transition(
        jobs[0].job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.UNCERTAIN,
        reason="external outcome unknown", now=NOW,
    )
    _record(evidence, ref="evidence:environment-changed")
    revision = owner.replan(
        workflow, principal=principal, steps=steps,
        reason="Authenticated observation changed; do not replay uncertain effect",
        evidence_ref="evidence:environment-changed", expected_revision=1,
        now=NOW + timedelta(minutes=1),
    )
    assert revision == 2
    checkpoint = owner.checkpoint(
        workflow, principal=principal, now=NOW + timedelta(minutes=2),
    )
    assert checkpoint["states"][0]["uncertain_external_effect"] is True
    assert owner.ready_steps(workflow, principal=principal) == ()
    with pytest.raises(RuntimeError, match="changed"):
        owner.replan(
            workflow, principal=principal, steps=steps, reason="replay",
            evidence_ref="evidence:environment-changed", expected_revision=1,
            now=NOW + timedelta(minutes=3),
        )


def test_cross_channel_resume_requires_evidence_from_both_scopes(
    canonical_state_path,
):
    evidence, _goals, _work, owner, principal, workflow, _jobs, _steps = _workflow(
        canonical_state_path,
    )
    discord = _principal("discord:dm:42")
    with pytest.raises(PermissionError):
        owner.resume_summary(workflow, principal=discord)
    _record(
        evidence, ref="message:local-bind", audience="local:text",
        kind="conversation_message",
    )
    _record(
        evidence, ref="message:discord-bind", audience="discord:dm:42",
        kind="conversation_message",
    )
    owner.bind_channel(
        workflow, source=principal, target=discord,
        source_evidence_ref="message:local-bind",
        target_evidence_ref="message:discord-bind", now=NOW,
    )
    summary = owner.resume_summary(workflow, principal=discord)
    assert summary["workflow_id"] == workflow
    assert summary["transcript_included"] is False


def test_cross_scope_job_and_dependency_cycle_are_rejected(canonical_state_path):
    evidence, goals, work = _owners(canonical_state_path)
    principal = _principal()
    _record(evidence, ref="evidence:novel-problem")
    root = goals.create_user_goal(
        principal=principal, title="Scoped goal", reason="test",
        base_priority=.5, confidence=1.0,
        completion=GoalCompletionCondition(CompletionKind.USER_DEFINED, "owner"),
        evidence_refs=("evidence:novel-problem",), now=NOW,
    )
    job = work.enqueue(
        kind="diagnostic", fingerprint="ga-job:wrong-scope",
        payload={"principal_id": principal.principal_id, "audience_id": "discord:dm:other"},
        priority=1, resource_cost=1, risk="read_only",
        completion_condition="receipt", now=NOW, deadline=NOW + timedelta(hours=1),
    )
    owner = GeneralizationWorkflowStore(canonical_state_path, goals=goals)
    with pytest.raises(PermissionError, match="scope"):
        owner.create(
            root_goal_id=root.id, original_objective=root.title, principal=principal,
            steps=(WorkflowStep("one", root.id, job.job_id, (), "read", "receipt", "read_only", 1.0),),
            evidence_ref="evidence:novel-problem", now=NOW,
        )
