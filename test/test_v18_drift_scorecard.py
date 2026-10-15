from __future__ import annotations

import pytest

from sofia.verify.drift import (
    Direction,
    DriftError,
    MetricSpec,
    Sample,
    Verdict,
    compare_metrics,
)

FREE_TEXT_RECALL = MetricSpec(
    metric="source_recall", direction=Direction.HIGHER_IS_BETTER,
    warn_delta=0.02, fail_delta=0.05,
)
P95_LATENCY = MetricSpec(
    metric="p95_latency_ms", direction=Direction.LOWER_IS_BETTER,
    warn_delta=25, fail_delta=75,
)


def test_reproducible_improvement_is_reported_as_improved():
    result = compare_metrics(
        FREE_TEXT_RECALL, Sample(0.80, 500), Sample(0.85, 500),
    )
    assert result.verdict is Verdict.IMPROVED
    assert result.recommend_rollback is False


def test_regression_beyond_fail_threshold_recommends_rollback():
    result = compare_metrics(
        P95_LATENCY, Sample(120, 500), Sample(240, 500),
    )
    assert result.verdict is Verdict.REGRESSED
    assert result.recommend_rollback is True


def test_small_regression_is_warn_not_rollback():
    result = compare_metrics(
        P95_LATENCY, Sample(120, 500), Sample(150, 500),
    )
    assert result.verdict is Verdict.WARN
    assert result.recommend_rollback is False
    # A 20 ms regression is inside the tolerance band, not a warning.
    tolerated = compare_metrics(
        P95_LATENCY, Sample(120, 500), Sample(140, 500),
    )
    assert tolerated.verdict is Verdict.WITHIN_TOLERANCE


def test_within_tolerance_when_change_is_small():
    result = compare_metrics(
        FREE_TEXT_RECALL, Sample(0.80, 500), Sample(0.805, 500),
    )
    assert result.verdict is Verdict.WITHIN_TOLERANCE


def test_no_sample_size_is_never_an_improvement_claim():
    result = compare_metrics(
        FREE_TEXT_RECALL, Sample(0.80, 0), Sample(0.99, 500),
    )
    assert result.verdict is Verdict.UNVERIFIABLE
    assert result.baseline is None and result.current is None
    assert "no improvement" in result.reason


def test_direction_flips_the_meaning_of_a_metric():
    # Lower latency improving by more than warn threshold is an improvement.
    improved = compare_metrics(P95_LATENCY, Sample(200, 100), Sample(150, 100))
    assert improved.verdict is Verdict.IMPROVED
    assert improved.delta == pytest.approx(50.0)


def test_spec_and_sample_validation_fail_closed():
    with pytest.raises(DriftError):
        MetricSpec("BadName", Direction.HIGHER_IS_BETTER, 1, 2)
    with pytest.raises(DriftError):
        MetricSpec("recall", Direction.HIGHER_IS_BETTER, 5, 2)
    with pytest.raises(DriftError):
        Sample(float("nan"), 10)
    with pytest.raises(DriftError):
        Sample(0.5, -1)
    with pytest.raises(DriftError):
        MetricSpec("recall", Direction.HIGHER_IS_BETTER, -1, 2)
