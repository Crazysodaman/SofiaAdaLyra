from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.generalization import (
    AttemptMetrics, ExplorationAdmission, GeneralizationService, NovelProblemCase,
    NovelProblemSuite, ProblemDomain, SuiteSplit, answer_digest,
)
from sofia.learning.contracts import DataUse, DataUseGrant
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
REVISION = "a" * 40


class _Learning:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def active_grant(self, *, principal_id, audience_id, purpose, required, at):
        if not self.allowed:
            return None
        assert purpose == "generalization-evaluation"
        assert set(required) == {DataUse.OBSERVATION, DataUse.STORAGE, DataUse.FEATURE_EXTRACTION}
        return DataUseGrant(
            grant_id="ga-grant", principal_id=principal_id, audience_id=audience_id,
            purpose=purpose, uses=frozenset(required), issued_at=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(days=60), approval_ref="owner-ui:ga-grant",
        )


class _Admission:
    def __init__(self):
        self.state = ExplorationAdmission()

    def __call__(self):
        return self.state


def _principal(audience="local:text"):
    return PrincipalContext("person:sparks", audience, AudienceKind.PRIVATE, "Sparks")


def _application_configuration(tmp_path: Path) -> SofiaConfiguration:
    project = Path(__file__).resolve().parents[1]
    personality = tmp_path / "personality.json"
    personality.write_text(
        '{"name":"Sofía","traits":["witty","warm","skeptical"],'
        '"communication_style":"Direct and evidence-minded."}',
        encoding="utf-8",
    )
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    return SofiaConfiguration(
        constitution_path=project / "src/sofia/constitution/constitution.md",
        constitution_hash_path=project / "src/sofia/constitution/constitution.sha256",
        identity_path=project / "src/sofia/identity/identity.json",
        personality_path=personality,
        avatar_path=project / "src/sofia/embodiment/avatar.json",
        state_path=state,
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=project,
    )


def _suite():
    domains = tuple(ProblemDomain)
    splits = (SuiteSplit.TRAIN, SuiteSplit.VALIDATION, SuiteSplit.TEST)
    cases = []
    for index, domain in enumerate(domains):
        split = splits[index % len(splits)]
        cases.append(NovelProblemCase(
            case_id=f"case:{index}", family_id=f"family:{index}", domain=domain,
            split=split, prompt=f"Unfamiliar {domain.value} case {index}",
            expected_answer_sha256=answer_digest({"answer": index}),
            milestone_digests=(("diagnosis", answer_digest(f"cause-{index}")),),
        ))
    # Ensure every split exists regardless of enum/domain order.
    assert {case.split for case in cases} == set(SuiteSplit)
    return NovelProblemSuite(
        "suite:unseen-v1", REVISION, tuple(cases), NOW,
        NOW + timedelta(days=30), "public-reviewed:sealed-suite-v1",
    )


def test_application_composes_one_generalization_owner_over_goals_run_and_life(tmp_path):
    application = SofiaApplication(_application_configuration(tmp_path))
    try:
        application.start()
        assert application.generalization.path == application.chat_state_path
        assert application.generalization.workflows is not None
        assert application.generalization.skills is not None
        assert application.generalization.workflows._goals is application.goals
        assert application.generalization.skills._procedures is application.life.procedures
        assert "generalization_retention" in application.background_coordinator._tasks
    finally:
        application.shutdown()


def test_sealed_suite_baseline_is_scoped_objectively_graded_and_restart_durable(
    canonical_state_path,
):
    service = GeneralizationService(
        canonical_state_path, learning=_Learning(), admission=_Admission(),
    )
    principal = _principal()
    suite = _suite()
    seal = service.register_suite(suite, principal=principal)
    assert len(seal) == 64
    run = service.begin_run(
        suite_id=suite.suite_id, principal=principal, condition="baseline",
        split=SuiteSplit.TEST, source_revision=REVISION,
        model_id="ollama:test-model@sha256:abc", now=NOW,
    )
    case = service.next_case(run, principal=principal, now=NOW)
    assert case is not None and case.split is SuiteSplit.TEST
    index = int(case.case_id.split(":")[-1])
    wrong = service.grade_case(
        run_id=run, case_id=case.case_id, principal=principal,
        answer={"answer": "model says success"},
        milestones={"diagnosis": f"cause-{index}"}, evidence_refs=(),
        metrics=AttemptMetrics("standard", "test-model", 10, 20, 0, 0), now=NOW,
    )
    assert wrong == {
        "objective_success": False, "partial_score": 0.5,
        "milestones": {"diagnosis": True}, "self_report_accepted": False,
    }
    assert service.grade_case(
        run_id=run, case_id=case.case_id, principal=principal,
        answer={"answer": "model says success"},
        milestones={"diagnosis": f"cause-{index}"}, evidence_refs=(),
        metrics=AttemptMetrics("standard", "test-model", 10, 20, 0, 0), now=NOW,
    ) == wrong
    with pytest.raises(PermissionError, match="immutable"):
        service.grade_case(
            run_id=run, case_id=case.case_id, principal=principal,
            answer={"answer": index},
            milestones={"diagnosis": f"cause-{index}"}, evidence_refs=(),
            metrics=AttemptMetrics("standard", "test-model", 10, 20, 0, 0), now=NOW,
        )
    # Restart reads the same canonical run and cannot regrade the case.
    restarted = GeneralizationService(
        canonical_state_path, learning=_Learning(), admission=_Admission(),
    )
    assert restarted.next_case(run, principal=principal, now=NOW) is None
    summary = restarted.finish_run(run, principal=principal, now=NOW + timedelta(seconds=1))
    assert summary["cases"] == 1
    assert summary["objective_successes"] == 0
    assert summary["authority"] is False
    assert restarted.finish_run(
        run, principal=principal, now=NOW + timedelta(seconds=2),
    ) == summary
    assert restarted.diagnostics(principal=principal)["runs"][0]["model_id"] == "ollama:test-model@sha256:abc"


def test_suite_family_leakage_scope_and_data_use_fail_closed(canonical_state_path):
    suite = _suite()
    with pytest.raises(ValueError, match="families"):
        replace(
            suite,
            cases=(
                replace(suite.cases[0], family_id=suite.cases[1].family_id),
                *suite.cases[1:],
            ),
        )
    denied = GeneralizationService(
        canonical_state_path, learning=_Learning(False), admission=_Admission(),
    )
    with pytest.raises(PermissionError, match="data-use"):
        denied.register_suite(suite, principal=_principal())

    allowed = GeneralizationService(
        canonical_state_path, learning=_Learning(), admission=_Admission(),
    )
    allowed.register_suite(suite, principal=_principal())
    with pytest.raises(PermissionError, match="scope"):
        allowed.begin_run(
            suite_id=suite.suite_id, principal=_principal("discord:dm:1"),
            condition="baseline", split=SuiteSplit.TEST,
            source_revision=REVISION, model_id="model", now=NOW,
        )


def test_operator_stop_blocks_new_generalization_run(canonical_state_path):
    service = GeneralizationService(
        canonical_state_path, learning=_Learning(), admission=_Admission(),
    )
    principal = _principal()
    suite = _suite()
    service.register_suite(suite, principal=principal)
    service._stop.set(active=True, updated_by="Sparks", reason="stop tests", at=NOW)
    with pytest.raises(PermissionError, match="STOP"):
        service.begin_run(
            suite_id=suite.suite_id, principal=principal, condition="baseline",
            split=SuiteSplit.TEST, source_revision=REVISION,
            model_id="model", now=NOW,
        )


def test_operator_stop_halts_an_already_active_evaluation(canonical_state_path):
    service = GeneralizationService(
        canonical_state_path, learning=_Learning(), admission=_Admission(),
    )
    principal = _principal()
    suite = _suite()
    service.register_suite(suite, principal=principal)
    run = service.begin_run(
        suite_id=suite.suite_id, principal=principal, condition="baseline",
        split=SuiteSplit.TEST, source_revision=REVISION,
        model_id="model", now=NOW,
    )
    case = service.next_case(run, principal=principal, now=NOW)
    assert case is not None
    service._stop.set(active=True, updated_by="Sparks", reason="halt active run", at=NOW)
    with pytest.raises(PermissionError, match="STOP"):
        service.next_case(run, principal=principal, now=NOW + timedelta(seconds=1))
    with pytest.raises(PermissionError, match="STOP"):
        service.grade_case(
            run_id=run, case_id=case.case_id, principal=principal,
            answer="not accepted", milestones={}, evidence_refs=(),
            metrics=AttemptMetrics("standard", "model", 1, 1, 0, 0),
            now=NOW + timedelta(seconds=1),
        )


def test_busy_and_observed_resource_pressure_block_start_and_active_run(
    canonical_state_path,
):
    admission = _Admission()
    service = GeneralizationService(
        canonical_state_path, learning=_Learning(), admission=admission,
    )
    principal = _principal()
    suite = _suite()
    service.register_suite(suite, principal=principal)
    admission.state = ExplorationAdmission(busy=True)
    with pytest.raises(PermissionError, match="gaming"):
        service.begin_run(
            suite_id=suite.suite_id, principal=principal, condition="baseline",
            split=SuiteSplit.TEST, source_revision=REVISION,
            model_id="model", now=NOW,
        )
    admission.state = ExplorationAdmission(cpu_percent=20, gpu_percent=30)
    run = service.begin_run(
        suite_id=suite.suite_id, principal=principal, condition="baseline",
        split=SuiteSplit.TEST, source_revision=REVISION,
        model_id="model", now=NOW,
    )
    admission.state = ExplorationAdmission(resource_pressure=.9)
    with pytest.raises(PermissionError, match="resource pressure"):
        service.next_case(run, principal=principal, now=NOW + timedelta(seconds=1))


def test_revocation_stops_active_run_and_expired_suite_content_is_retired(
    canonical_state_path,
):
    learning = _Learning()
    service = GeneralizationService(
        canonical_state_path, learning=learning, admission=_Admission(),
    )
    principal = _principal()
    suite = _suite()
    service.register_suite(suite, principal=principal)
    run = service.begin_run(
        suite_id=suite.suite_id, principal=principal, condition="baseline",
        split=SuiteSplit.TEST, source_revision=REVISION, model_id="model", now=NOW,
    )
    learning.allowed = False
    with pytest.raises(PermissionError, match="data-use"):
        service.next_case(run, principal=principal, now=NOW + timedelta(seconds=1))
    learning.allowed = True
    # Active runs retain their sealed case until explicitly reconciled.
    assert service.expire_retention(now=NOW + timedelta(days=31)) == 0
    with service._connect() as db:
        assert db.execute(
            "SELECT retired_at FROM ga_problem_suite WHERE suite_id=?", (suite.suite_id,),
        ).fetchone()[0] is None
    assert service.expire_run(
        run, principal=principal, now=NOW + timedelta(days=31), reason="grant revoked",
    )
    assert service.expire_retention(now=NOW + timedelta(days=31, seconds=1)) == 1
    with service._connect() as db:
        case = db.execute(
            "SELECT prompt,expected_answer_sha256 FROM ga_problem_case WHERE suite_id=? LIMIT 1",
            (suite.suite_id,),
        ).fetchone()
    assert tuple(case) == ("[retired]", "0" * 64)
