from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from sofia.generalization import (
    AttemptMetrics, ExplorationAdmission, GeneralizationService, NovelProblemCase,
    NovelProblemSuite, ProblemDomain, SuiteSplit, answer_digest,
)
from sofia.generalization.skills import LearnedSkillStore
from sofia.goals.evidence import GoalEvidenceLedger
from sofia.learning.contracts import DataUse, DataUseGrant
from sofia.life.procedures import ProcedureRecord
from sofia.platform.run.work import DurableWorkStore, WorkStatus
from sofia.core.social.model import AudienceKind, PrincipalContext


NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
REVISION = "b" * 40


class _Learning:
    def active_grant(self, *, principal_id, audience_id, purpose, required, at):
        return DataUseGrant(
            "grant:ga-skills", principal_id, audience_id, purpose,
            frozenset(required), NOW - timedelta(hours=1), NOW + timedelta(days=60),
            "owner-ui:ga-skills",
        )


class _Procedures:
    def __init__(self, refs):
        self.refs = tuple(refs)

    def proof_receipts_for_procedure(self, _procedure_id):
        return tuple(
            (f"project:{index}", f"job:{index}", ref)
            for index, ref in enumerate(self.refs)
        )


def _principal():
    return PrincipalContext("person:sparks", "local:text", AudienceKind.PRIVATE, "Sparks")


def _procedure():
    return ProcedureRecord(
        procedure_id="life-procedure:verified", version=1, status="verified",
        owner_principal_id="person:sparks", audience_id="local:text",
        purpose="Diagnose a bounded service", input_types=("ServiceState",),
        output_types=("DiagnosticReceipt",),
        preconditions=("dependency_available",), required_tools=("diagnostic-adapter",),
        exact_capabilities=("system.inspect",), source_objectives=("identify cause",),
        environment="portable-principle", verification_rule="two independent outcomes",
        verified_projects=2, provenance_refs=("receipt:one", "receipt:two"),
        updated_at=NOW,
    )


def _suite():
    cases = []
    for domain_index, domain in enumerate(ProblemDomain):
        for split_index, split in enumerate(SuiteSplit):
            case_id = f"skill-case:{domain_index}:{split_index}"
            cases.append(NovelProblemCase(
                case_id, f"skill-family:{domain_index}:{split_index}", domain, split,
                f"Withheld {domain.value} variation", answer_digest(case_id),
            ))
    return NovelProblemSuite(
        "suite:skill-heldout", REVISION, tuple(cases), NOW,
        NOW + timedelta(days=30), "public-reviewed:skill-heldout",
    )


def _completed_test_run(path, principal):
    service = GeneralizationService(
        path, learning=_Learning(), admission=lambda: ExplorationAdmission(),
    )
    suite = _suite()
    service.register_suite(suite, principal=principal)
    run = service.begin_run(
        suite_id=suite.suite_id, principal=principal, condition="learned",
        split=SuiteSplit.TEST, source_revision=REVISION,
        model_id="heldout-evaluator", now=NOW,
    )
    case_ids = []
    while (case := service.next_case(run, principal=principal, now=NOW)) is not None:
        case_ids.append(case.case_id)
        result = service.grade_case(
            run_id=run, case_id=case.case_id, principal=principal,
            answer=case.case_id, milestones={}, evidence_refs=(),
            metrics=AttemptMetrics("deterministic", "heldout-evaluator", 1, 0, 0, 0),
            now=NOW,
        )
        assert result["objective_success"] is True
    service.finish_run(run, principal=principal, now=NOW + timedelta(seconds=1))
    return run, case_ids


def _qualify(path, skills, candidate, principal):
    evidence = GoalEvidenceLedger(path)
    for platform_name in ("windows", "linux"):
        evidence.record(
            kind="reviewed_evidence", observed_at=NOW,
            source=f"skill-adapter:{platform_name}", successful=True,
            evidence_ref=f"adapter:{platform_name}",
            principal_id=principal.principal_id, audience=principal.audience_id,
        )
        skills.record_adapter(
            candidate.skill_id, principal=principal, platform_name=platform_name,
            adapter_id=f"{platform_name}-diagnostic", adapter_version="1.0",
            evidence_ref=f"adapter:{platform_name}", now=NOW,
        )
    run, case_ids = _completed_test_run(path, principal)
    for kind, case_id in zip(
        ("positive", "missing_dependency", "version_difference", "counterexample"),
        case_ids,
    ):
        assert skills.record_trial(
            candidate.skill_id, principal=principal, trial_kind=kind,
            run_id=run, case_id=case_id, now=NOW,
        )
    return skills.qualify(
        candidate.skill_id, principal=principal, now=NOW + timedelta(seconds=2),
    )


def test_skill_qualification_needs_verified_sources_two_platforms_and_four_variations(
    canonical_state_path,
):
    principal = _principal()
    procedures = _Procedures(("receipt:one", "receipt:two"))
    skills = LearnedSkillStore(canonical_state_path, procedures=procedures)
    candidate = skills.register_candidate(
        _procedure(), principal=principal, risk="read_only", now=NOW,
    )
    assert candidate.status == "candidate"
    with pytest.raises(PermissionError, match="cross-platform"):
        skills.qualify(candidate.skill_id, principal=principal, now=NOW)

    verified = _qualify(canonical_state_path, skills, candidate, principal)
    assert verified.status == "verified"
    assert verified.risk == "read_only"


def test_verified_skill_rehearsal_uses_existing_run_receipt_and_source_loss_invalidates(
    canonical_state_path,
):
    principal = _principal()
    procedures = _Procedures(("receipt:one", "receipt:two"))
    skills = LearnedSkillStore(canonical_state_path, procedures=procedures)
    candidate = skills.register_candidate(
        _procedure(), principal=principal, risk="read_only", now=NOW,
    )
    _qualify(canonical_state_path, skills, candidate, principal)
    work = DurableWorkStore(canonical_state_path)
    job = work.enqueue(
        kind="skill-rehearsal", fingerprint="skill-rehearsal:one",
        payload={"principal_id": principal.principal_id,
                 "audience_id": principal.audience_id},
        priority=10, resource_cost=5, risk="read_only",
        completion_condition="typed rehearsal receipt", now=NOW,
        deadline=NOW + timedelta(hours=1),
    )
    evidence = GoalEvidenceLedger(canonical_state_path)
    evidence.record(
        kind="operation_receipt", observed_at=NOW, source="run:skill-rehearsal",
        successful=True, action_id=job.job_id, evidence_ref="receipt:rehearsal",
        principal_id=principal.principal_id, audience=principal.audience_id,
    )
    work.transition(
        job.job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.COMPLETED,
        reason="verified", result={"evidence_ref": "receipt:rehearsal"}, now=NOW,
    )
    skills.record_rehearsal(
        candidate.skill_id, principal=principal, job_id=job.job_id,
        evidence_ref="receipt:rehearsal", rollback_ref=None, now=NOW,
    )
    procedures.refs = ()
    assert skills.reconcile_source(candidate.skill_id, now=NOW + timedelta(seconds=1))
    assert skills.visible(principal=principal)[0].status == "invalidated"


def test_unverified_or_cross_scope_procedure_cannot_become_skill(canonical_state_path):
    skills = LearnedSkillStore(
        canonical_state_path, procedures=_Procedures(("receipt:one", "receipt:two")),
    )
    with pytest.raises(PermissionError):
        skills.register_candidate(
            replace(_procedure(), status="candidate"),
            principal=_principal(), risk="read_only", now=NOW,
        )


def test_skill_risk_cannot_understate_protected_capability(canonical_state_path):
    skills = LearnedSkillStore(
        canonical_state_path, procedures=_Procedures(("receipt:one", "receipt:two")),
    )
    protected = replace(_procedure(), exact_capabilities=("service.manage",))
    with pytest.raises(PermissionError, match="cannot understate"):
        skills.register_candidate(
            protected, principal=_principal(), risk="read_only", now=NOW,
        )


def test_non_read_only_rehearsal_requires_rollback_and_scope(canonical_state_path):
    principal = _principal()
    procedures = _Procedures(("receipt:one", "receipt:two"))
    skills = LearnedSkillStore(canonical_state_path, procedures=procedures)
    candidate = skills.register_candidate(
        _procedure(), principal=principal, risk="isolated_change", now=NOW,
    )
    _qualify(canonical_state_path, skills, candidate, principal)
    work = DurableWorkStore(canonical_state_path)
    job = work.enqueue(
        kind="skill-rehearsal", fingerprint="skill-rehearsal:rollback",
        payload={"principal_id": principal.principal_id,
                 "audience_id": principal.audience_id},
        priority=10, resource_cost=5, risk="isolated_change",
        completion_condition="typed rehearsal receipt", now=NOW,
        deadline=NOW + timedelta(hours=1),
    )
    evidence = GoalEvidenceLedger(canonical_state_path)
    evidence.record(
        kind="operation_receipt", observed_at=NOW, source="run:skill-rehearsal",
        successful=True, action_id=job.job_id, evidence_ref="receipt:rollback-test",
        principal_id=principal.principal_id, audience=principal.audience_id,
    )
    work.transition(
        job.job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.COMPLETED,
        reason="verified", result={"evidence_ref": "receipt:rollback-test"}, now=NOW,
    )
    with pytest.raises(PermissionError, match="rollback"):
        skills.record_rehearsal(
            candidate.skill_id, principal=principal, job_id=job.job_id,
            evidence_ref="receipt:rollback-test", rollback_ref=None, now=NOW,
        )


def test_owner_reviewed_lifecycle_is_scoped_and_durable(canonical_state_path):
    principal = _principal()
    skills = LearnedSkillStore(
        canonical_state_path, procedures=_Procedures(("receipt:one", "receipt:two")),
    )
    candidate = skills.register_candidate(
        _procedure(), principal=principal, risk="read_only", now=NOW,
    )
    _qualify(canonical_state_path, skills, candidate, principal)
    evidence = GoalEvidenceLedger(canonical_state_path)
    evidence.record(
        kind="reviewed_evidence", observed_at=NOW, source="owner:skill-review",
        successful=None, evidence_ref="review:retire-skill",
        principal_id=principal.principal_id, audience=principal.audience_id,
    )
    changed = skills.transition_lifecycle(
        candidate.skill_id, principal=principal, to_status="deprecated",
        reason="A safer reviewed procedure replaced this technique",
        evidence_ref="review:retire-skill", now=NOW + timedelta(seconds=3),
    )
    assert changed.status == "deprecated"
    restarted = LearnedSkillStore(canonical_state_path, procedures=_Procedures(()))
    assert restarted.visible(principal=principal)[0].status == "deprecated"


def test_bounded_source_reconciliation_invalidates_changed_proof(canonical_state_path):
    procedures = _Procedures(("receipt:one", "receipt:two"))
    skills = LearnedSkillStore(canonical_state_path, procedures=procedures)
    candidate = skills.register_candidate(
        _procedure(), principal=_principal(), risk="read_only", now=NOW,
    )
    procedures.refs = ()
    assert skills.reconcile_sources(now=NOW + timedelta(seconds=1), limit=1) == 1
    assert skills.visible(principal=_principal())[0].skill_id == candidate.skill_id
    assert skills.visible(principal=_principal())[0].status == "invalidated"
