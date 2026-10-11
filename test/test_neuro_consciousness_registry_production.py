"""Deferred canonical scientific registry contracts; no scientific studies run."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.neuro.consciousness_research import StudyProtocol
from sofia.neuro.research_registry import (
    EvaluatedResearchOutcome, PreregisteredStudy, ResearchEvidenceRegistry,
    reviewed_baseline_studies,
)

pytestmark = pytest.mark.pkg_verify
NOW = datetime(2026, 10, 11, 18, tzinfo=timezone.utc)


def opened(tmp_path):
    state = tmp_path / "sofia.db"
    RuntimeUserSettingsStore(state).load()
    return state, ResearchEvidenceRegistry(state)


def result(*, study="science:attention:v1", kind="null", evidence="verify:independent:001"):
    return EvaluatedResearchOutcome(
        protocol_id=study,
        observed_at=NOW + timedelta(minutes=10),
        actual_sample_size=20,
        result=kind,
        evidence_ref=evidence,
        adverse_observations="No unreviewed action occurred according to audit",
        limitations="Small synthetic sample; cannot infer phenomenal experience",
        reviewed_by="Sparks",
    )


def test_preregistered_controls_are_distinct_measurable_and_not_sentience_claims(tmp_path):
    state, registry = opened(tmp_path)
    studies = reviewed_baseline_studies(at=NOW)
    assert len(studies) == 3
    assert {s.theory_kind for s in studies} == {
        "global_workspace_access",
        "metacognitive_self_model",
        "functional_agency",
    }
    for study in studies:
        assert study.protocol.claims_subjective_experience is False
        assert study.comparison_control
        assert study.stop_or_reject_rule
        assert registry.preregister(study) == study.protocol.protocol_id
    assert "No owner-preregistered" not in registry.report()
    assert "observations=NONE" in registry.report()
    report = ResearchEvidenceRegistry(state).report()
    assert "subjective" in report.casefold()
    assert "science:attention:v1" in report


def test_same_id_different_unapproved_study_cannot_rewrite_baseline(tmp_path):
    _, registry = opened(tmp_path)
    original = reviewed_baseline_studies(at=NOW)[0]
    registry.preregister(original)
    # Idempotent repeated button click preserves first timestamp and protocol.
    registry.preregister(
        replace(original, created_at=NOW + timedelta(minutes=1))
    )
    modified = replace(
        original,
        comparison_control="Unauthorized proposed different comparison"
    )
    with pytest.raises(PermissionError, match="silently changed"):
        registry.preregister(modified)
    assert original.comparison_control in registry.report()


def test_null_negative_and_adverse_results_are_retained_in_canonical_state(tmp_path):
    state, registry = opened(tmp_path)
    registry.preregister(reviewed_baseline_studies(at=NOW)[0])
    for i, kind in enumerate(("null", "refuted", "adverse", "protocol_violation")):
        receipt = registry.record_reviewed_result(
            result(kind=kind, evidence=f"verify:independent:{i:03d}"),
        )
        assert receipt.startswith("study-result:")
    reopened = ResearchEvidenceRegistry(state)
    report = reopened.report()
    for kind in ("null", "refuted", "adverse", "protocol_violation"):
        assert f"outcome={kind}" in report
    with sqlite3.connect(state) as db:
        assert db.execute("SELECT COUNT(*) FROM neuro_research_result").fetchone()[0] == 4
    assert "cannot establish phenomenal consciousness" in report


def test_result_must_follow_preregistration_and_stay_owner_reviewed(tmp_path):
    _, registry = opened(tmp_path)
    with pytest.raises(LookupError, match="no prior"):
        registry.record_reviewed_result(result())
    registry.preregister(reviewed_baseline_studies(at=NOW)[0])
    with pytest.raises(PermissionError, match="self-assessed"):
        replace(result(), reviewed_by="sofia")
    with pytest.raises(ValueError, match="prior"):
        registry.record_reviewed_result(
            replace(result(), observed_at=NOW - timedelta(seconds=1))
        )


def test_unverified_proof_of_subjectivity_and_phenomenal_hypotheses_rejected(tmp_path):
    _, registry = opened(tmp_path)
    registered = reviewed_baseline_studies(at=NOW)[0]
    with pytest.raises(ValueError, match="preregistration"):
        bogus = replace(
            registered,
            protocol=replace(
                registered.protocol, claims_subjective_experience=True,
            ),
        )
        registry.preregister(bogus)
    with pytest.raises(ValueError, match="subjectivity"):
        replace(
            registered, theory_kind="phenomenal_subjectivity",
        )
    assert "No owner-preregistered" in registry.report()
