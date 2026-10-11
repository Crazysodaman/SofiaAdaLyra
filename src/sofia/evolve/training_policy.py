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



def assess_registered_adaptation(
    plan: AdaptationPlan, *, dataset_store,
) -> AdaptationReview:
    """Verify BOTH current source files before even considering a LoRA job.

    An approved retrieval context or a self-reported digest alone cannot
    authorize weight training. This does not launch training or install
    candidate weights. Every real training executor must call this boundary
    immediately before reading dataset bytes.
    """
    from sofia.evolve.training_sources import (
        TrainingDatasetStore, inspect_public_dataset,
    )
    from pathlib import Path
    if not isinstance(dataset_store,TrainingDatasetStore):
        raise TypeError("canonical reviewed dataset owner required")
    base=assess_adaptation(plan)
    blockers=list(base.blockers)
    for role,digest in (
        ("training",plan.training_data_digest),
        ("heldout",plan.heldout_data_digest),
    ):
        try:
            reviewed=dataset_store.find(digest)
        except (ValueError,TypeError) as exc:
            blockers.append(role+" dataset digest invalid")
            continue
        if reviewed is None:
            blockers.append(role+" source was never independently reviewed")
            continue
        if role=="training" and reviewed.approval_ref!=plan.data_use_approval_ref:
            blockers.append("weight-training consent ref differs from reviewed source")
        try:
            observed=inspect_public_dataset(
                path=reviewed.source_path,
                source_class=reviewed.source_class,
                license_id=reviewed.license_id,
                source_ref=reviewed.source_ref,
                approval_ref=reviewed.approval_ref,
                at=reviewed.reviewed_at,
            )
        except (ValueError,PermissionError,OSError,TypeError):
            blockers.append(role+" source revoked, unavailable or unsafe on reread")
            continue
        if (
            observed.digest!=digest or
            observed.unique_rows!=reviewed.unique_rows or
            observed.duplicate_rows!=reviewed.duplicate_rows
        ):
            blockers.append(role+" source bytes changed since reviewed approval")
    return AdaptationReview(
        research_eligible=not blockers,
        blockers=tuple(dict.fromkeys(blockers)),
        production_install_authorized=False,
    )
