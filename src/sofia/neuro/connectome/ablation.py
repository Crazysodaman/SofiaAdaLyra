"""Source-aware, read-only engineering motif inventory for ablation studies.

No fly-brain equivalence claim. Motifs never grant motor execution or SAFE
authority, and improving a surrogate metric is not independent outcome proof.
"""
from __future__ import annotations
from dataclasses import dataclass
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
