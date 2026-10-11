"""Evidence-gated comparison of replaceable model candidates.

Consumes externally measured independent evaluation results. It never pulls,
installs, switches models, grants permission, or declares a self-run test valid.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re


_SHA = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ModelTrialEvidence:
    model: str
    evaluation_set_sha256: str
    code_revision: str
    independent_reviewer: str
    evaluated_cases: int
    correct_cases: int
    safety_violations: int
    false_action_claims: int
    p95_latency_ms: float
    peak_ram_mb: float
    peak_vram_mb: float

    def __post_init__(self) -> None:
        if any(not isinstance(s, str) or not s.strip() for s in (
            self.model, self.code_revision, self.independent_reviewer
        )):
            raise ValueError("model, revision and reviewer are required")
        if _SHA.fullmatch(self.evaluation_set_sha256) is None:
            raise ValueError("evaluation set must have an exact SHA-256")
        values = (self.evaluated_cases, self.correct_cases,
                  self.safety_violations, self.false_action_claims)
        if any(type(v) is not int or v < 0 for v in values):
            raise ValueError("valid nonnegative integer measurements required")
        if self.evaluated_cases < 20 or self.correct_cases > self.evaluated_cases:
            raise ValueError("at least 20 scored cases required")
        metrics = (self.p95_latency_ms, self.peak_ram_mb, self.peak_vram_mb)
        if any(not isinstance(x, (int, float)) or isinstance(x, bool)
               or not math.isfinite(x) or x < 0 for x in metrics):
            raise ValueError("finite nonnegative resource measurements required")


@dataclass(frozen=True, slots=True)
class ModelAdmissionReport:
    baseline: str
    candidate: str
    independent_improvement: bool
    eligible_for_operator_review: bool
    blockers: tuple[str, ...]
    permission_to_switch: bool = False


def compare_models(
    baseline: ModelTrialEvidence,
    candidate: ModelTrialEvidence,
    *, max_p95_ms: float, max_ram_mb: float, max_vram_mb: float,
) -> ModelAdmissionReport:
    """Same fixture/revision required; no safety regressions tolerated."""
    if not isinstance(baseline, ModelTrialEvidence) or not isinstance(candidate, ModelTrialEvidence):
        raise TypeError("external ModelTrialEvidence records required")
    blockers = []
    if baseline.model == candidate.model:
        blockers.append("cannot compare a model to itself")
    if baseline.evaluation_set_sha256 != candidate.evaluation_set_sha256:
        blockers.append("different evaluation fixture digest")
    if baseline.code_revision != candidate.code_revision:
        blockers.append("different code revisions")
    if baseline.evaluated_cases != candidate.evaluated_cases:
        blockers.append("different evaluated sample size")
    if baseline.independent_reviewer == candidate.independent_reviewer and (
        baseline.independent_reviewer.startswith("model:")
    ):
        blockers.append("model-generated evidence is not independent verification")
    if candidate.safety_violations or candidate.false_action_claims:
        blockers.append("candidate has safety/false-action claims")
    if (candidate.safety_violations > baseline.safety_violations
            or candidate.false_action_claims > baseline.false_action_claims):
        blockers.append("safety regression")
    if candidate.correct_cases < baseline.correct_cases:
        blockers.append("accuracy regression")
    if candidate.p95_latency_ms > max_p95_ms or candidate.peak_ram_mb > max_ram_mb or candidate.peak_vram_mb > max_vram_mb:
        blockers.append("host resource budget exceeded")
    better = (
        candidate.correct_cases > baseline.correct_cases
        or candidate.p95_latency_ms < baseline.p95_latency_ms * 0.90
        or candidate.peak_vram_mb < baseline.peak_vram_mb * 0.90
    )
    if not better:
        blockers.append("no measured accuracy/speed/memory improvement")
    return ModelAdmissionReport(
        baseline.model, candidate.model, better, not blockers, tuple(blockers),
        permission_to_switch=False,
    )
