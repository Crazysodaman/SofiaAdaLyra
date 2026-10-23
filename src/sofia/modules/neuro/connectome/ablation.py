"""Source-aware, read-only engineering motif inventory for ablation studies.

No fly-brain equivalence claim. Motifs never grant motor execution or SAFE
authority, and improving a surrogate metric is not independent outcome proof.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from .circuits import selected_circuits


@dataclass(frozen=True, slots=True)
class MotifAblationPlan:
    circuit_id: str
    biological_reference: str
    engineering_edge_count: int
    source_coverage: bool
    baseline_required: bool
    deployment_authorized: bool = False


def ablation_inventory() -> tuple[MotifAblationPlan, ...]:
    entries = []
    for motif in selected_circuits():
        if not motif.source_url.startswith("https://"):
            raise ValueError("connectome motif lacks source URL")
        if any(not 0.0<=abs(edge.weight)<=1.0 for edge in motif.edges):
            raise ValueError("normalized prototype edge out of bounds")
        entries.append(MotifAblationPlan(
            motif.circuit_id,motif.source_url,len(motif.edges),
            bool(motif.biological_source and motif.simplifications),
            baseline_required=True, deployment_authorized=False,
        ))
    return tuple(entries)


@dataclass(frozen=True, slots=True)
class PairedCompetitionObservation:
    """One genuinely measured, same-input control/candidate ablation pair."""

    observation_id: str
    baseline_winner: str | None
    candidate_winner: str | None
    expected_winner: str
    baseline_elapsed_ms: float
    candidate_elapsed_ms: float

    def __post_init__(self) -> None:
        if not isinstance(self.observation_id, str) or not self.observation_id.strip():
            raise ValueError("paired observation requires an identifier")
        if not isinstance(self.expected_winner, str) or not self.expected_winner.strip():
            raise ValueError("independent expected winner required")
        for field in ("baseline_elapsed_ms", "candidate_elapsed_ms"):
            value = getattr(self, field)
            if type(value) not in (int, float) or not isfinite(value) or value < 0:
                raise ValueError("observed elapsed time must be finite and nonnegative")


def summarize_paired_competition(
    observations: tuple[PairedCompetitionObservation, ...],
) -> dict[str, float | int | None]:
    """Compare supplied independent outcomes; never synthesize measurement.

    This is an offline, authority-free evaluator. Actual paired runner and
    host resource instrumentation are owned by their production callers.
    """
    if not isinstance(observations, tuple) or len(observations) > 100_000:
        raise ValueError("bounded paired observation tuple required")
    if any(not isinstance(x, PairedCompetitionObservation) for x in observations):
        raise TypeError("typed paired measurements required")
    ids = [x.observation_id for x in observations]
    if len(ids) != len(set(ids)):
        raise ValueError("one observation may not be counted twice")
    count = len(observations)
    if not count:
        return {"paired": 0, "baseline_accuracy": None,
                "candidate_accuracy": None, "accuracy_delta": None,
                "mean_latency_delta_ms": None}
    baseline = sum(x.baseline_winner == x.expected_winner for x in observations) / count
    candidate = sum(x.candidate_winner == x.expected_winner for x in observations) / count
    return {"paired": count, "baseline_accuracy": baseline,
            "candidate_accuracy": candidate,
            "accuracy_delta": candidate - baseline,
            "mean_latency_delta_ms": sum(
                x.candidate_elapsed_ms - x.baseline_elapsed_ms for x in observations
            ) / count}
