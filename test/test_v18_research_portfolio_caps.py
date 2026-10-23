"""Owner V18 5/15 scientific research admission regression contracts.

No model, tool or research experiment is executed by these tests.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.modules.neuro.research_registry import (
    EvaluatedResearchOutcome, ResearchEvidenceRegistry,
    reviewed_baseline_studies,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

pytestmark = pytest.mark.pkg_verify
NOW = datetime(2026, 10, 12, 18, tzinfo=timezone.utc)


def opened(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    return state, ResearchEvidenceRegistry(state)


def study(index):
    baseline = reviewed_baseline_studies(at=NOW)[0]
    return replace(
        baseline,
        protocol=replace(
            baseline.protocol, protocol_id=f"science:portfolio:{index:03d}",
        ),
    )


def reviewed(index, kind):
    return EvaluatedResearchOutcome(
        protocol_id=f"science:portfolio:{index:03d}",
        observed_at=NOW + timedelta(minutes=30),
        actual_sample_size=20,
        result=kind,
        evidence_ref=f"verify:portfolio:{index:03d}:{kind}",
        adverse_observations="No uncontrolled external action occurred in review",
        limitations="Bounded trial; negative and inconclusive results retained",
        reviewed_by="Sparks",
    )


def test_open_hypotheses_limit_is_atomic_persistent_and_closes_only_on_review(tmp_path):
    state, registry = opened(tmp_path)
    for index in range(15):
        assert registry.preregister(study(index)) == f"science:portfolio:{index:03d}"
    assert registry.portfolio_counts()["unresolved"] == 15
    with pytest.raises(PermissionError, match="15 unresolved"):
        registry.preregister(study(15))
    # Idempotent preregistration does not consume a new hypothesis slot.
    assert registry.preregister(study(2)) == "science:portfolio:002"
    registry.record_reviewed_result(reviewed(0, "inconclusive"))
    assert registry.portfolio_counts()["unresolved"] == 15
    with pytest.raises(PermissionError, match="15 unresolved"):
        registry.preregister(study(15))
    registry.record_reviewed_result(reviewed(0, "refuted"))
    assert registry.portfolio_counts()["unresolved"] == 14
    assert ResearchEvidenceRegistry(state).preregister(study(15)) == "science:portfolio:015"


def test_five_active_slots_pause_restart_and_conclusive_review(tmp_path):
    state, registry = opened(tmp_path)
    for index in range(6):
        registry.preregister(study(index))
    assert all(registry.activate_experiment(
        f"science:portfolio:{i:03d}", reviewed_by="Sparks"
    ) for i in range(5))
    assert registry.activate_experiment(
        "science:portfolio:001", reviewed_by="Sparks",
    ) is False
    with pytest.raises(PermissionError, match="5 active"):
        registry.activate_experiment(
            "science:portfolio:005", reviewed_by="Sparks",
        )
    assert registry.pause_experiment(
        "science:portfolio:001", reviewed_by="Sparks",
    ) is True
    assert registry.activate_experiment(
        "science:portfolio:005", reviewed_by="Sparks",
    ) is True
    assert ResearchEvidenceRegistry(state).portfolio_counts()["active"] == 5
    # Inconclusive result frees the worker but not the open hypothesis.
    registry.record_reviewed_result(reviewed(5, "inconclusive"))
    counts = registry.portfolio_counts()
    assert counts["active"] == 4 and counts["unresolved"] == 6
    registry.record_reviewed_result(reviewed(5, "null"))
    assert registry.portfolio_counts()["unresolved"] == 5
    with pytest.raises(PermissionError, match="resolved"):
        registry.activate_experiment(
            "science:portfolio:005", reviewed_by="Sparks",
        )
    assert "active=4/5" in registry.report()
    assert "unanswered=5/15" in registry.report()


def test_atomic_slot_reservations_cannot_race_past_five(tmp_path):
    _, registry = opened(tmp_path)
    for index in range(10):
        registry.preregister(study(index))

    def attempt(i):
        try:
            return registry.activate_experiment(
                f"science:portfolio:{i:03d}", reviewed_by="Sparks",
            )
        except PermissionError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        approved = list(pool.map(attempt, range(10)))
    assert sum(approved) == 5
    assert registry.portfolio_counts()["active"] == 5


def test_no_scope_escalation_or_secret_owner_reclassification(tmp_path):
    state, registry = opened(tmp_path)
    registry.preregister(study(0))
    with pytest.raises(PermissionError, match="owner-reviewed"):
        registry.activate_experiment(
            "science:portfolio:000", reviewed_by="model",
        )
    with pytest.raises(PermissionError, match="owner-reviewed"):
        registry.pause_experiment(
            "science:portfolio:000", reviewed_by="model",
        )
    with pytest.raises(LookupError, match="not preregistered"):
        registry.activate_experiment(
            "science:portfolio:999", reviewed_by="Sparks",
        )
    assert registry.portfolio_counts()["active"] == 0
    # Legacy original protocols with no portfolio row become proposed or
    # resolved based on actual independently reviewed source outcomes.
    registry.record_reviewed_result(reviewed(0, "refuted"))
    with sqlite3.connect(state) as db:
        db.execute(
            "DELETE FROM neuro_research_portfolio_state WHERE protocol_id=?",
            ("science:portfolio:000",),
        )
    assert ResearchEvidenceRegistry(state).portfolio_counts()["resolved"] == 1
