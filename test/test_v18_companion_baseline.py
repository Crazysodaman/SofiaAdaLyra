"""CA-002/CA-007: revision-pinned, evidence-honest Phase 00 baseline."""
from copy import deepcopy

import pytest

from sofia.platform.verify.v18_companion_baseline import (
    BaselineIntegrityError, SCENARIOS,
    capture_v18_baseline, summarize_control_baseline,
)

pytestmark = pytest.mark.pkg_verify


def _measured(revision="a" * 40):
    return {
        "schema": "sofia.core.cognition-v2.baseline-v1",
        "revision": revision,
        "environment": {"provider": "test", "model": "test"},
        "database": {"conversation_messages": 8, "matrix_traces": 4},
        "efficiency": {
            "sqlite_queries": 50, "sqlite_writes": 8,
            "cache_hits": 0, "cache_misses": 2, "llm_calls": 0,
        },
        "scenarios": {
            name: {"wall_ms": 1.5, "process_cpu_ms": 1, "peak_rss_bytes": None}
            for name in SCENARIOS
        },
        "startup": {"wall_ms": 3, "process_cpu_ms": 2, "peak_rss_bytes": None},
        "idle_250ms": {"wall_ms": 250, "process_cpu_ms": 0, "peak_rss_bytes": None},
        "unavailable": {
            "primary_model_inference": "not live",
            "secondary_model_inference": "not live",
            "vram_bytes": "no telemetry",
            "gpu_load": "no telemetry",
            "model_residency": "test engine",
        },
        "conversation_content": "a private secret that must not leak",
    }


def test_baseline_has_reproducible_contract_and_honest_acceptance_stages():
    baseline = summarize_control_baseline(_measured(), expected_revision="a" * 40)
    assert baseline["schema"] == "sofia.v18.companion-baseline-v1"
    assert baseline["durable_counts"] == {
        "conversation_messages": 8, "matrix_traces": 4,
    }
    assert baseline["instrumentation"]["llm_calls"] == 0
    assert all(
        value == "not_attested_by_baseline"
        for name, value in baseline["acceptance"].items()
        if name != "baseline_generated"
    )
    assert "memory_temporal_correctness" in baseline["not_measured"]
    assert "avatar_voice_synchronization" in baseline["not_measured"]
    assert "novel_problem_transfer" in baseline["not_measured"]
    assert "conversation_content" not in str(baseline)
    assert "private secret" not in str(baseline)


@pytest.mark.parametrize("change", (
    lambda m: m.update(revision="b" * 40),
    lambda m: m["environment"].update(provider="ollama"),
    lambda m: m["database"].update(matrix_traces=0),
    lambda m: m["scenarios"].pop("technical_question"),
    lambda m: m["efficiency"].update(llm_calls=1),
    lambda m: m["unavailable"].pop("gpu_load"),
    lambda m: m["scenarios"]["casual_conversation"].update(wall_ms=float("nan")),
    lambda m: m["efficiency"].update(sqlite_queries=0),
))
def test_baseline_rejects_fabricated_or_incomplete_evidence(change):
    measured = deepcopy(_measured())
    change(measured)
    with pytest.raises(BaselineIntegrityError):
        summarize_control_baseline(measured, expected_revision="a" * 40)


def test_baseline_rejects_wrong_git_revision_before_any_capture(tmp_path, monkeypatch):
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / ".git").mkdir()
    calls = []
    monkeypatch.setattr(
        "sofia.platform.verify.v18_companion_baseline._exact_revision",
        lambda path: "a" * 40,
    )
    with pytest.raises(BaselineIntegrityError, match="differs"):
        capture_v18_baseline(
            repo=repo, expected_revision="b" * 40,
            capture=lambda: calls.append("ran") or _measured(),
        )
    assert calls == []


def test_baseline_rejects_git_change_during_capture(tmp_path, monkeypatch):
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / ".git").mkdir()
    revisions = iter(("a" * 40, "b" * 40))
    monkeypatch.setattr(
        "sofia.platform.verify.v18_companion_baseline._exact_revision",
        lambda path: next(revisions),
    )
    with pytest.raises(BaselineIntegrityError, match="changed"):
        capture_v18_baseline(
            repo=repo, expected_revision="a" * 40,
            capture=lambda: _measured(),
        )


def test_phase00_baseline_runs_real_isolated_application_path(monkeypatch, tmp_path):
    from sofia.platform.verify import v18_companion_baseline as module

    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / ".git").mkdir()
    monkeypatch.setattr(module, "_exact_revision", lambda _: "a" * 40)
    # Existing Cognition V2 harness is the sole source of measured control
    # behavior. No mock engine, parallel database, or fabricated receipts.
    from sofia.platform.verify.cognition_v2_baseline import capture_baseline
    monkeypatch.setattr(
        "sofia.platform.verify.cognition_v2_baseline.PROJECT_ROOT", repo,
    )
    monkeypatch.setattr(
        "sofia.platform.verify.cognition_v2_baseline._revision", lambda: "a" * 40,
    )
    result = capture_v18_baseline(
        repo=repo, expected_revision="a" * 40,
        capture=capture_baseline,
    )
    assert result["durable_counts"]["conversation_messages"] == 8
    assert result["durable_counts"]["matrix_traces"] == 4
    assert result["instrumentation"]["sqlite_queries"] > 0
    assert result["acceptance"]["venus_live"] == "not_attested_by_baseline"



def test_repeated_control_baseline_percentiles_are_observed_not_inferred(tmp_path, monkeypatch):
    from sofia.platform.verify import v18_companion_baseline as module
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / ".git").mkdir()
    monkeypatch.setattr(module, "_exact_revision", lambda _: "a" * 40)
    values = iter((2, 4, 5, 12, 29))
    observed = []
    def sample():
        raw = deepcopy(_measured())
        latency = next(values)
        observed.append(latency)
        raw["scenarios"]["casual_conversation"]["wall_ms"] = latency
        return raw
    result = capture_v18_baseline(
        repo=repo, expected_revision="a" * 40,
        capture=sample, repetitions=5,
    )
    assert observed == [2, 4, 5, 12, 29]
    assert result["repetitions"] == 5
    assert result["timing_distributions"]["casual_conversation"]["wall_ms"] == {
        "samples": 5, "p50": 5, "p95": 29,
    }
    assert result["timing_distributions"]["startup"]["peak_rss_bytes"] == {
        "samples": 0, "p50": None, "p95": None,
    }
    assert result["distribution_scope"] == (
        "test-provider isolation, not live-model latency"
    )
    assert result["acceptance"]["venus_live"] == "not_attested_by_baseline"


@pytest.mark.parametrize("invalid", [0, 21, True, 2.3, -1])
def test_invalid_repetition_count_is_rejected_before_capture(tmp_path, invalid):
    path = tmp_path / "checkout"
    path.mkdir()
    (path / ".git").mkdir()
    with pytest.raises(BaselineIntegrityError, match="repetitions"):
        capture_v18_baseline(
            repo=path, expected_revision="a" * 40,
            repetitions=invalid, capture=lambda: pytest.fail("should not run"),
        )
