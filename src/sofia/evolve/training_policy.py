"""Research-only model adaptation manifests; no training or self-deployment.

Fine-tuning data needs source permissions, independent held-out evaluation
and resource budgets. Training a model does not transfer Sofía's identity.
"""
from __future__ import annotations
from dataclasses import dataclass
import re


_SHA=re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class AdaptationPlan:
    base_model_digest: str
    training_data_digest: str
    heldout_data_digest: str
    data_use_approval_ref: str
    adaptation_kind: str
    max_gpu_hours: float
    max_vram_mb: int
    preserve_source_privacy: bool


@dataclass(frozen=True, slots=True)
class AdaptationReview:
    research_eligible: bool
    blockers: tuple[str, ...]
    production_install_authorized: bool = False


def assess_adaptation(plan: AdaptationPlan) -> AdaptationReview:
    if not isinstance(plan, AdaptationPlan):
        raise TypeError("typed AdaptationPlan required")
    blockers=[]
    if any(_SHA.fullmatch(x) is None for x in (
        plan.base_model_digest,plan.training_data_digest,plan.heldout_data_digest
    )):
        blockers.append("base and datasets must be digest pinned")
    if plan.training_data_digest==plan.heldout_data_digest:
        blockers.append("held-out data must be independent of training input")
    if plan.adaptation_kind not in {"lora","qlora"}:
        blockers.append("unreviewed adaptation method")
    if not plan.data_use_approval_ref:
        blockers.append("no data-use permission receipt")
    if type(plan.max_gpu_hours) not in {int,float} or not 0<plan.max_gpu_hours<=120:
        blockers.append("GPU time budget outside policy")
    if type(plan.max_vram_mb) is not int or not 512<=plan.max_vram_mb<=98304:
        blockers.append("VRAM budget outside policy")
    if not plan.preserve_source_privacy:
        blockers.append("privacy-preserving training required")
    return AdaptationReview(not blockers,tuple(blockers),False)
