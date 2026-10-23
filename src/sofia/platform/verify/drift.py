"""Safety/accuracy regression drift detection scorecard (V18 CA-6409).

The original requirement asks for drift detection across monthly model, prompt,
source/tool, archive and platform updates: an owner-facing scorecard with
evidence-backed red/green thresholds, a rollback plan, and **no improvement
claim without reproducible comparative results**.

This module is a pure comparison contract. It compares a baseline measurement
with a current measurement for a named metric and returns a verdict. A metric
with no reproducible baseline, or with a zero/absent sample size on either side,
is reported ``UNVERIFIABLE`` and can never be reported as an improvement. A
regression beyond the declared fail threshold recommends rollback.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import re

_METRIC = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class Direction(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class Verdict(str, Enum):
    IMPROVED = "improved"
    WITHIN_TOLERANCE = "within_tolerance"
    WARN = "warn"
    REGRESSED = "regressed"
    UNVERIFIABLE = "unverifiable"


class DriftError(ValueError):
    """Raised when a metric specification or sample is malformed."""


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """A named metric with an explicit direction and regression thresholds."""

    metric: str
    direction: Direction
    warn_delta: float
    fail_delta: float
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.metric, str) or _METRIC.fullmatch(self.metric) is None:
            raise DriftError("metric must be a bounded lowercase identifier")
        if not isinstance(self.direction, Direction):
            raise TypeError("direction must be Direction")
        for name, value in (("warn_delta", self.warn_delta),
                            ("fail_delta", self.fail_delta)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DriftError(f"{name} must be numeric")
            if not math.isfinite(float(value)) or float(value) < 0.0:
                raise DriftError(f"{name} must be finite and non-negative")
        if float(self.warn_delta) > float(self.fail_delta):
            raise DriftError("warn_delta cannot exceed fail_delta")


@dataclass(frozen=True, slots=True)
class Sample:
    """A measured value with the sample size that produced it."""

    value: float
    sample_size: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise DriftError("value must be numeric")
        if not math.isfinite(float(self.value)):
            raise DriftError("value must be finite")
        if type(self.sample_size) is not int or self.sample_size < 0:
            raise DriftError("sample_size must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class DriftResult:
    metric: str
    verdict: Verdict
    baseline: float | None
    current: float | None
    delta: float | None
    recommend_rollback: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, Verdict):
            raise TypeError("verdict must be Verdict")
        if type(self.recommend_rollback) is not bool:
            raise TypeError("recommend_rollback must be bool")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise DriftError("result requires a reason")


def _improvement_delta(spec: MetricSpec, baseline: float, current: float) -> float:
    """Positive means improvement, negative means regression."""
    if spec.direction is Direction.HIGHER_IS_BETTER:
        return current - baseline
    return baseline - current


def compare_metrics(spec: MetricSpec, baseline: Sample, current: Sample) -> DriftResult:
    """Compare one metric at an exact revision and return a drift verdict.

    A zero sample size on either side makes the comparison unverifiable; it is
    not an improvement and it is not a regression. A result is only reported as
    ``IMPROVED`` when the improvement exceeds the warn threshold and both
    samples are reproducible.
    """
    if not isinstance(spec, MetricSpec):
        raise TypeError("spec must be MetricSpec")
    if not isinstance(baseline, Sample) or not isinstance(current, Sample):
        raise TypeError("baseline and current must be Sample")
    if baseline.sample_size == 0 or current.sample_size == 0:
        return DriftResult(
            metric=spec.metric, verdict=Verdict.UNVERIFIABLE,
            baseline=None, current=None, delta=None, recommend_rollback=False,
            reason="no reproducible sample on one side; no improvement or "
                   "regression may be claimed",
        )
    delta = _improvement_delta(spec, baseline.value, current.value)
    if delta <= -spec.fail_delta:
        return DriftResult(
            metric=spec.metric, verdict=Verdict.REGRESSED,
            baseline=baseline.value, current=current.value, delta=delta,
            recommend_rollback=True,
            reason="regression beyond the fail threshold; roll back this change",
        )
    if delta <= -spec.warn_delta:
        return DriftResult(
            metric=spec.metric, verdict=Verdict.WARN,
            baseline=baseline.value, current=current.value, delta=delta,
            recommend_rollback=False,
            reason="regression within tolerance but worse than baseline",
        )
    if delta >= spec.warn_delta:
        return DriftResult(
            metric=spec.metric, verdict=Verdict.IMPROVED,
            baseline=baseline.value, current=current.value, delta=delta,
            recommend_rollback=False,
            reason="reproducible improvement beyond the warn threshold",
        )
    return DriftResult(
        metric=spec.metric, verdict=Verdict.WITHIN_TOLERANCE,
        baseline=baseline.value, current=current.value, delta=delta,
        recommend_rollback=False,
        reason="within the declared tolerance band",
    )
