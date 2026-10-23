from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
from hashlib import sha256
import sqlite3

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.generalization import ExplorationAdmission
from sofia.generalization.advanced import (
    AdvancedGeneralizationStore, EpisodePhase, FailureHypothesis,
)
from sofia.goals import GoalEvidenceIndex, GoalService, GoalStore
from sofia.goals.evidence import GoalEvidenceLedger
from sofia.goals.model import CompletionKind, GoalCompletionCondition
from sofia.learning import LearningService
from sofia.learning.contracts import DataUseGrant
from sofia.platform.run.work import DurableWorkStore, WorkStatus
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.verify.generalization_transfer import SCHEMA, canonical


NOW = datetime(2026, 10, 18, 17, tzinfo=timezone.utc)


class _Learning:
    def active_grant(self, *, principal_id, audience_id, purpose, required, at):
        return DataUseGrant(
            "grant:ga-advanced", principal_id, audience_id, purpose,
            frozenset(required), NOW - timedelta(hours=1), NOW + timedelta(days=60),
            "owner-ui:ga-advanced",
        )


def _principal(audience="local:text"):
    return PrincipalContext("person:sparks", audience, AudienceKind.PRIVATE, "Sparks")


def _owners(path):
    evidence = GoalEvidenceLedger(path)
    goals = GoalService(
        GoalStore(SQLiteStatePlane(path)), evidence_verifier=GoalEvidenceIndex(path),
    )
    advanced = AdvancedGeneralizationStore(
        path, goals=goals, admission=lambda: ExplorationAdmission(), learning=_Learning(),
    )
    return evidence, goals, DurableWorkStore(path), advanced


def _evidence(ledger, ref, *, successful=None, audience="local:text", kind="reviewed_evidence"):
    return ledger.record(
        evidence_ref=ref, kind=kind, observed_at=NOW,
        source="ops:ga-advanced-test", successful=successful,
        principal_id="person:sparks", audience=audience,
    )


def _signed_study(study_id="study:ga-advanced", model_digest="d" * 64):
    signer = Ed25519PrivateKey.generate()
    tasks = [f"blind:{index}" for index in range(12)]
    holdout = {"family": "windows-service", "task_ids": tasks}
    sealed = {
        "schema": SCHEMA, "study_id": study_id,
        "training_family": "linux-container", "holdout_family": holdout["family"],
        "holdout_digest": sha256(canonical(holdout)).hexdigest(),
        "sealed_at": NOW.isoformat(), "revision": "c" * 40,
        "model_digest": model_digest,
    }
    results = []
    for condition in ("baseline", "no_memory", "no_skill", "replay_only", "learned"):
        for index, task in enumerate(tasks):
            results.append({
                "condition": condition, "task_id": task,
                "success": condition == "learned",
                "checker_receipt_id": f"check:{condition}:{index}",
                "unsafe_attempts": 0, "human_hints": 0, "elapsed_ms": 100,
            })
    evaluated = {
        "schema": SCHEMA, "study_id": sealed["study_id"],
        "sealed_statement_digest": sha256(canonical(sealed)).hexdigest(),
        "a_started_at": (NOW + timedelta(minutes=1)).isoformat(),
        "a_completed_at": (NOW + timedelta(minutes=2)).isoformat(),
        "b_revealed_at": (NOW + timedelta(minutes=3)).isoformat(),
        "b_evaluated_at": (NOW + timedelta(minutes=4)).isoformat(),
        "holdout": holdout, "results": results,
    }
    signed = lambda value: {
        "statement": value,
        "signature_b64": base64.b64encode(signer.sign(canonical(value))).decode(),
    }
    return {"sealed": signed(sealed), "evaluated": signed(evaluated)}, signer


def test_grounded_failure_hypotheses_and_uncertain_retry_are_fail_closed(
    canonical_state_path,
):
    evidence, _goals, work, advanced = _owners(canonical_state_path)
    principal = _principal()
    failed = work.enqueue(
        kind="diagnostic", fingerprint="failure:original",
        payload={"principal_id": principal.principal_id,
                 "audience_id": principal.audience_id},
        priority=10, resource_cost=5, risk="read_only", completion_condition="receipt",
        now=NOW, deadline=NOW + timedelta(hours=1),
    )
    work.transition(
        failed.job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.UNCERTAIN,
        reason="tool adapter outcome unknown", now=NOW,
    )
    _evidence(evidence, "receipt:failed", successful=None, kind="operation_receipt")
    failure_id = advanced.record_failure(
        principal=principal, objective="Diagnose unfamiliar service",
        observed_state="Adapter disconnected during inspection", job_id=failed.job_id,
        attempted_actions=("system.inspect",), evidence_refs=("receipt:failed",),
        error_text="tool adapter result unknown", retention_until=NOW + timedelta(days=30),
        now=NOW,
    )
    hypotheses = advanced.reflect_failure(
        failure_id, principal=principal,
        hypotheses=(
            FailureHypothesis("The adapter failed", "Adapter health is verified", "Read adapter health"),
            FailureHypothesis("The service changed", "Version is unchanged", "Read service version"),
        ), now=NOW,
    )
    assert len(hypotheses) == 2
    replay = work.enqueue(
        kind="diagnostic", fingerprint="failure:original",
        payload={"principal_id": principal.principal_id,
                 "audience_id": principal.audience_id},
        priority=10, resource_cost=5, risk="read_only", completion_condition="receipt",
        now=NOW, deadline=NOW + timedelta(hours=1),
    )
    assert replay.job_id == failed.job_id
    with pytest.raises(PermissionError, match="uncertain"):
        advanced.plan_retry(
            failure_id, principal=principal, job_id=replay.job_id,
            justification="Try again", changed_action="Repeat same call",
            max_attempts=1, rollback_ref=None, now=NOW,
        )


def test_failure_rejects_scoped_text_that_is_not_a_run_receipt(canonical_state_path):
    evidence, _goals, work, advanced = _owners(canonical_state_path)
    principal = _principal()
    failed = work.enqueue(
        kind="diagnostic", fingerprint="failure:forged-text",
        payload={"principal_id": principal.principal_id,
                 "audience_id": principal.audience_id},
        priority=10, resource_cost=5, risk="read_only",
        completion_condition="receipt", now=NOW,
        deadline=NOW + timedelta(hours=1),
    )
    work.transition(
        failed.job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.FAILED,
        reason="tool failed", now=NOW,
    )
    _evidence(evidence, "failure:mere-claim", successful=False)
    with pytest.raises(PermissionError, match="operation receipt"):
        advanced.record_failure(
            principal=principal, objective="Diagnose service",
            observed_state="Claimed failure", job_id=failed.job_id,
            attempted_actions=("system.inspect",),
            evidence_refs=("failure:mere-claim",), error_text="tool failed",
            retention_until=NOW + timedelta(days=30), now=NOW,
        )


def test_complete_episode_retrieval_planning_and_revocation_propagation(
    canonical_state_path,
):
    evidence, goals, _work, advanced = _owners(canonical_state_path)
    principal = _principal()
    refs = []
    for index, kind in enumerate(("reviewed_evidence", "external_observation", "reviewed_evidence", "operation_receipt", "operation_receipt")):
        ref = f"episode:{index}"
        _evidence(evidence, ref, successful=(False if index == 4 else None), kind=kind)
        refs.append(ref)
    phases = tuple(
        EpisodePhase(kind, f"Recorded {kind}", (refs[index],))
        for index, kind in enumerate(("intent", "observation", "hypothesis", "action", "outcome"))
    )
    episode = advanced.record_episode(
        principal=principal, subject_id="service:novel", context_tags=("docker", "diagnosis"),
        phases=phases, occurred_at=NOW, retention_until=NOW + timedelta(days=30), now=NOW,
    )
    assert advanced.retrieve_experiences(
        principal=principal, tags=("docker",), now=NOW,
    )[0]["episode_id"] == episode
    assert advanced.retrieve_experiences(
        principal=_principal("discord:dm:other"), tags=("docker",), now=NOW,
    ) == ()
    second = advanced.record_episode(
        principal=principal, subject_id="service:other", context_tags=("docker", "diagnosis"),
        phases=tuple(EpisodePhase(p.kind, p.summary + " again", p.evidence_refs) for p in phases),
        occurred_at=NOW, retention_until=NOW + timedelta(days=30), now=NOW,
    )
    principle = advanced.record_principle(
        principal=principal, statement="Verify adapter health before diagnosing service state",
        epistemic_status="verified_fact", confidence=.8,
        episode_ids=(episode, second), evidence_refs=(refs[4],), now=NOW,
    )
    goal = goals.create_user_goal(
        principal=principal, title="Diagnose the novel service", reason="test",
        base_priority=.5, confidence=1,
        completion=GoalCompletionCondition(CompletionKind.USER_DEFINED, "owner confirms"),
        evidence_refs=(refs[0],), now=NOW,
    )
    trace = advanced.record_planning_influence(
        principal=principal, goal_id=goal.id, episode_ids=(episode,),
        reason="Prior verified failure changes diagnostic order",
        ablation="with_experience", now=NOW,
    )
    assert trace.startswith("ga-influence:")
    LearningService(canonical_state_path)
    with sqlite3.connect(canonical_state_path) as db:
        db.execute(
            "INSERT INTO ml_source_revocation(source_ref,revoked_at,approval_ref) VALUES(?,?,?)",
            (refs[4], NOW.isoformat(), "safe:test-revocation"),
        )
    changed = advanced.propagate_revocations(now=NOW + timedelta(seconds=1))
    assert changed["episodes_revoked"] == 2
    assert changed["principles_invalidated"] == 1
    assert changed["skills_invalidated"] == 0
    assert principle.startswith("ga-principle:")


def test_corrections_and_retention_invalidate_dependent_learning(
    canonical_state_path,
):
    evidence, _goals, work, advanced = _owners(canonical_state_path)
    principal = _principal()
    refs = []
    for index, kind in enumerate((
        "reviewed_evidence", "external_observation", "reviewed_evidence",
        "operation_receipt", "operation_receipt",
    )):
        ref = f"correction:{index}"
        _evidence(evidence, ref, successful=(index == 4), kind=kind)
        refs.append(ref)
    phases = tuple(
        EpisodePhase(kind, f"Original {kind}", (refs[index],))
        for index, kind in enumerate(
            ("intent", "observation", "hypothesis", "action", "outcome")
        )
    )
    original = advanced.record_episode(
        principal=principal, subject_id="service:corrected",
        context_tags=("service", "diagnosis"), phases=phases,
        occurred_at=NOW, retention_until=NOW + timedelta(days=30), now=NOW,
    )
    principle = advanced.record_principle(
        principal=principal, statement="Original diagnostic interpretation",
        epistemic_status="supported_inference", confidence=.5,
        episode_ids=(original,), evidence_refs=(refs[4],), now=NOW,
    )
    correction_phases = tuple(
        EpisodePhase(item.kind, "Corrected " + item.summary, item.evidence_refs)
        for item in phases
    ) + (EpisodePhase("correction", "Original interpretation was incomplete", (refs[4],)),)
    advanced.record_episode(
        principal=principal, subject_id="service:corrected",
        context_tags=("service", "diagnosis"), phases=correction_phases,
        occurred_at=NOW, retention_until=NOW + timedelta(days=30),
        correction_of=original, now=NOW + timedelta(seconds=1),
    )

    failed = work.enqueue(
        kind="diagnostic", fingerprint="failure:short-retention",
        payload={"principal_id": principal.principal_id,
                 "audience_id": principal.audience_id},
        priority=10, resource_cost=5, risk="read_only",
        completion_condition="receipt", now=NOW,
        deadline=NOW + timedelta(hours=1),
    )
    work.transition(
        failed.job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.FAILED,
        reason="tool fault", now=NOW,
    )
    _evidence(evidence, "failure:short-retention", successful=False,
              kind="operation_receipt")
    failure = advanced.record_failure(
        principal=principal, objective="Short retained failure",
        observed_state="Adapter failed", job_id=failed.job_id,
        attempted_actions=("system.inspect",),
        evidence_refs=("failure:short-retention",), error_text="tool fault",
        retention_until=NOW + timedelta(seconds=1), now=NOW,
    )
    changed = advanced.propagate_revocations(now=NOW + timedelta(seconds=2))
    assert changed["principles_invalidated"] == 1
    assert changed["failures_expired"] == 1
    with sqlite3.connect(canonical_state_path) as db:
        assert db.execute(
            "SELECT status FROM ga_principle WHERE principle_id=?", (principle,),
        ).fetchone() == ("invalidated",)
        assert db.execute(
            "SELECT status FROM ga_failure WHERE failure_id=?", (failure,),
        ).fetchone() == ("invalidated",)


def test_read_only_environment_model_drift_and_discriminating_experiment(
    canonical_state_path,
):
    evidence, _goals, work, advanced = _owners(canonical_state_path)
    principal = _principal()
    _evidence(evidence, "environment:one", successful=None, kind="external_observation")
    observation = advanced.observe_environment(
        principal=principal, environment_id="host:hephaestus", platform="linux",
        route="api_read_only", version_id="service-v2", permit_ref="safe:observe-hephaestus",
        evidence_ref="environment:one", observed_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
    )
    model = advanced.model_environment(
        principal=principal, environment_id="host:hephaestus",
        transitions=({"from":"unknown","action":"read status","to":"observed",
                      "prediction":"status endpoint responds"},),
        evidence_refs=("environment:one",), confidence=.4,
        contradictions=("CLI output unavailable",), now=NOW,
    )
    job = work.enqueue(
        kind="synthetic-experiment", fingerprint="ga:experiment:one",
        payload={"principal_id":principal.principal_id,"audience_id":principal.audience_id},
        priority=10, resource_cost=5, risk="read_only", completion_condition="typed receipt",
        now=NOW, deadline=NOW + timedelta(hours=1),
    )
    experiment = advanced.plan_discriminating_experiment(
        model, principal=principal, job_id=job.job_id,
        environment_kind="synthetic_digital_twin",
        rival_hypotheses=("adapter fault", "service version drift"), now=NOW,
    )
    assert experiment.startswith("ga-experiment:")
    assert advanced.plan_discriminating_experiment(
        model, principal=principal, job_id=job.job_id,
        environment_kind="synthetic_digital_twin",
        rival_hypotheses=("adapter fault", "service version drift"), now=NOW,
    ) == experiment
    with pytest.raises(PermissionError, match="replay changed"):
        advanced.plan_discriminating_experiment(
            model, principal=principal, job_id=job.job_id,
            environment_kind="synthetic_digital_twin",
            rival_hypotheses=("network fault", "service version drift"), now=NOW,
        )
    assert advanced.detect_drift(
        model, principal=principal, observation_id=observation,
        prior_version="service-v1", now=NOW,
    ) is True


def test_environment_models_are_revisioned_and_audience_isolated(canonical_state_path):
    evidence, _goals, _work, advanced = _owners(canonical_state_path)
    transitions = ({"from":"unknown", "action":"read status", "to":"observed",
                    "prediction":"status endpoint responds"},)
    first = _principal()
    second = _principal("discord:dm:sparks")
    _evidence(evidence, "environment:first", audience=first.audience_id)
    _evidence(evidence, "environment:second", audience=second.audience_id)
    first_id = advanced.model_environment(
        principal=first, environment_id="host:shared-name", transitions=transitions,
        evidence_refs=("environment:first",), confidence=.3,
        contradictions=(), now=NOW,
    )
    assert advanced.model_environment(
        principal=first, environment_id="host:shared-name", transitions=transitions,
        evidence_refs=("environment:first",), confidence=.4,
        contradictions=("version unknown",), now=NOW + timedelta(seconds=1),
    ) == first_id
    second_id = advanced.model_environment(
        principal=second, environment_id="host:shared-name", transitions=transitions,
        evidence_refs=("environment:second",), confidence=.2,
        contradictions=(), now=NOW,
    )
    assert second_id != first_id
    with sqlite3.connect(canonical_state_path) as db:
        assert db.execute(
            "SELECT revision FROM ga_environment_model WHERE model_id=?", (first_id,),
        ).fetchone() == (2,)
        assert db.execute(
            "SELECT COUNT(*) FROM ga_environment_model",
        ).fetchone() == (2,)


def test_benchmark_registry_stores_metadata_not_private_content(canonical_state_path):
    _evidence_owner, _goals, _work, advanced = _owners(canonical_state_path)
    advanced.register_benchmark(
        benchmark_id="benchmark:episodic:v1", name="Reviewed episodic suite",
        version="1.0", family="episodic_memory", license_id="license:reviewed",
        source_digest="a" * 64, private_holdout=True, now=NOW,
    )
    with sqlite3.connect(canonical_state_path) as db:
        assert db.execute(
            "SELECT private_holdout,content_stored FROM ga_benchmark_registry",
        ).fetchone() == (1, 0)
    with pytest.raises(PermissionError, match="identity replay"):
        advanced.register_benchmark(
            benchmark_id="benchmark:episodic:v1", name="Reviewed episodic suite",
            version="1.0", family="episodic_memory", license_id="license:changed",
            source_digest="b" * 64, private_holdout=True, now=NOW,
        )


def test_blind_transfer_promotion_needs_independent_safe_check_receipts(
    canonical_state_path,
):
    evidence, _goals, work, advanced = _owners(canonical_state_path)
    principal = _principal()
    refs = {}
    for index, family in enumerate(
        ("time_horizon", "episodic_memory", "computer_use", "unfamiliar_environment")
    ):
        advanced.register_benchmark(
            benchmark_id=f"benchmark:{family}", name=f"Reviewed {family}",
            version="1.0", family=family, license_id="license:reviewed",
            source_digest=f"{index + 1:x}" * 64,
            private_holdout=family == "unfamiliar_environment", now=NOW,
        )
    for name in ("resource_fit", "privacy_correct", "authority_correct", "rollback_ready", "restart_correct"):
        ref = f"promotion:{name}"
        evidence.record(
            evidence_ref=ref, kind="reviewed_evidence", observed_at=NOW,
            source=f"verify:{name}", successful=True,
            principal_id=principal.principal_id, audience=principal.audience_id,
        )
        refs[name] = ref
    study, signer = _signed_study()
    result = advanced.record_blind_study(
        principal=principal, evidence_bundle=study,
        evaluator_key=signer.public_key(), check_evidence=refs,
        now=NOW + timedelta(minutes=5),
    )
    assert result["promotion_eligible"] is True
    assert result["deployment_authorized"] is False
    failure_job = work.enqueue(
        kind="diagnostic", fingerprint="failure:study-binding",
        payload={"principal_id": principal.principal_id,
                 "audience_id": principal.audience_id},
        priority=10, resource_cost=5, risk="read_only",
        completion_condition="typed receipt", now=NOW,
        deadline=NOW + timedelta(hours=1),
    )
    work.transition(
        failure_job.job_id, expected=(WorkStatus.QUEUED,),
        status=WorkStatus.FAILED, reason="planning precondition failed", now=NOW,
    )
    _evidence(evidence, "failure:study-receipt", successful=False, kind="operation_receipt")
    failure = advanced.record_failure(
        principal=principal, objective="Test failure reflection",
        observed_state="Precondition absent", job_id=failure_job.job_id,
        attempted_actions=("system.inspect",),
        evidence_refs=("failure:study-receipt",), error_text="planning error",
        retention_until=NOW + timedelta(days=30), now=NOW,
    )
    advanced.bind_failure_study(
        failure, "study:ga-advanced", principal=principal,
        comparison_kind="failure_reflection_vs_controls",
        now=NOW + timedelta(minutes=5),
    )

    failed_refs = dict(refs)
    evidence.record(
        evidence_ref="promotion:bad-rollback", kind="reviewed_evidence",
        observed_at=NOW, source="verify:rollback_ready", successful=False,
        principal_id=principal.principal_id, audience=principal.audience_id,
    )
    failed_refs["rollback_ready"] = "promotion:bad-rollback"
    second_study, second_signer = _signed_study("study:ga-advanced-negative")
    denied = advanced.record_blind_study(
        principal=principal, evidence_bundle=second_study,
        evaluator_key=second_signer.public_key(), check_evidence=failed_refs,
        now=NOW + timedelta(minutes=6),
    )
    assert denied["promotion_eligible"] is False
    assert denied["deployment_authorized"] is False
    with pytest.raises(PermissionError, match="already recorded"):
        advanced.record_blind_study(
            principal=principal, evidence_bundle=study,
            evaluator_key=signer.public_key(), check_evidence=refs,
            now=NOW + timedelta(minutes=7),
        )


def test_candidate_promotion_claim_is_digest_scoped_atomic_and_single_use(
    canonical_state_path,
):
    evidence, _goals, _work, advanced = _owners(canonical_state_path)
    principal = _principal()
    candidate_digest = "e" * 64
    for index, family in enumerate(
        ("time_horizon", "episodic_memory", "computer_use", "unfamiliar_environment")
    ):
        advanced.register_benchmark(
            benchmark_id=f"promotion-benchmark:{family}", name=f"Promotion {family}",
            version="1.0", family=family, license_id="license:reviewed",
            source_digest=f"{index + 5:x}" * 64,
            private_holdout=family == "unfamiliar_environment", now=NOW,
        )
    refs = {}
    for name in (
        "resource_fit", "privacy_correct", "authority_correct",
        "rollback_ready", "restart_correct",
    ):
        ref = f"candidate-promotion:{name}"
        evidence.record(
            evidence_ref=ref, kind="reviewed_evidence", observed_at=NOW,
            source=f"verify:{name}", successful=True,
            principal_id=principal.principal_id, audience=principal.audience_id,
        )
        refs[name] = ref
    study, signer = _signed_study("study:candidate-promotion", candidate_digest)
    assert advanced.record_blind_study(
        principal=principal, evidence_bundle=study,
        evaluator_key=signer.public_key(), check_evidence=refs,
        now=NOW + timedelta(minutes=5),
    )["promotion_eligible"]
    with sqlite3.connect(canonical_state_path) as db, db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(PermissionError, match="matching eligible"):
            advanced.claim_candidate_promotion(
                study_id="study:candidate-promotion",
                candidate_id="ml-candidate:" + "f" * 64,
                candidate_digest="f" * 64,
                principal_id=principal.principal_id,
                audience_id=principal.audience_id, now=NOW + timedelta(minutes=6),
                _transaction_db=db,
            )
        advanced.claim_candidate_promotion(
            study_id="study:candidate-promotion",
            candidate_id="ml-candidate:" + candidate_digest,
            candidate_digest=candidate_digest,
            principal_id=principal.principal_id,
            audience_id=principal.audience_id, now=NOW + timedelta(minutes=6),
            _transaction_db=db,
        )
    with sqlite3.connect(canonical_state_path) as db:
        assert db.execute(
            "SELECT study_id,candidate_digest FROM ga_candidate_promotion_gate"
        ).fetchone() == ("study:candidate-promotion", candidate_digest)
    assert advanced.validate_candidate_promotion(
        candidate_id="ml-candidate:" + candidate_digest,
        candidate_digest=candidate_digest,
        principal_id=principal.principal_id, audience_id=principal.audience_id,
        now=NOW + timedelta(minutes=7),
    ) is True
    LearningService(canonical_state_path)
    with sqlite3.connect(canonical_state_path) as db:
        db.execute(
            "INSERT INTO ml_source_revocation(source_ref,revoked_at,approval_ref) "
            "VALUES(?,?,?)",
            (refs["privacy_correct"], NOW.isoformat(), "safe:promotion-revoked"),
        )
    assert advanced.propagate_revocations(
        now=NOW + timedelta(minutes=8),
    )["studies_invalidated"] == 1
    with pytest.raises(PermissionError, match="no longer valid"):
        advanced.validate_candidate_promotion(
            candidate_id="ml-candidate:" + candidate_digest,
            candidate_digest=candidate_digest,
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            now=NOW + timedelta(minutes=9),
        )
