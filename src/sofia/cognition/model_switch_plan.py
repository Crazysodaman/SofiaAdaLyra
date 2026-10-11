"""Controlled model-role replacement plans, not automatic model deployment.

Reuses RuntimeUserSettings, existing model lifecycle, and independent
ModelTrialEvidence. A cognitive provider cannot authorize its own switch.
The plan never rewrites canonical identity, memory or policy state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable

from sofia.cognition.model_admission import (
    ModelTrialEvidence, compare_models,
)
from sofia.config.user_settings import (
    RuntimeUserSettings, RuntimeUserSettingsStore,
)


@dataclass(frozen=True, slots=True)
class ModelRoleChangeRequest:
    role: str
    baseline: ModelTrialEvidence
    candidate: ModelTrialEvidence
    operator_approval_ref: str
    installed_model_evidence_ref: str
    max_p95_ms: float
    max_ram_mb: float
    max_vram_mb: float


@dataclass(frozen=True, slots=True)
class PreparedModelRoleChange:
    role: str
    old_model: str
    new_model: str
    previous_settings_sha256: str
    proposed_settings: RuntimeUserSettings
    operator_approval_ref: str
    rollback_model: str
    independently_reviewed: bool
    can_apply_now: bool = False


def prepare_model_role_change(
    *, current_settings: RuntimeUserSettings,
    change: ModelRoleChangeRequest,
    verify_operator_and_install_receipts: Callable[[ModelRoleChangeRequest], bool],
) -> PreparedModelRoleChange:
    """Prepare immutable settings only after host-reviewed evidence.

    This never saves settings, installs a model, activates a provider, changes
    a runtime process, or discards the known-good model. Actual promotion
    needs an external SAFE-controlled broker and measured rollback drill.
    """
    if not isinstance(current_settings, RuntimeUserSettings):
        raise TypeError("canonical RuntimeUserSettings required")
    if not isinstance(change, ModelRoleChangeRequest):
        raise TypeError("typed role change required")
    if change.role not in {"primary", "secondary"}:
        raise ValueError("only configured cognitive roles may be proposed")
    for value in (
        change.operator_approval_ref, change.installed_model_evidence_ref,
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > 300:
            raise ValueError("exact operator approval and installed-model evidence required")
    current_role_model = getattr(current_settings, f"cognitive_{change.role}_model")
    if current_role_model != change.baseline.model:
        raise ValueError("evaluated baseline is not the active configured role model")
    report = compare_models(
        change.baseline, change.candidate,
        max_p95_ms=change.max_p95_ms,
        max_ram_mb=change.max_ram_mb,
        max_vram_mb=change.max_vram_mb,
    )
    if not report.eligible_for_operator_review:
        raise PermissionError(
            "independent candidate evaluation failed: " + "; ".join(report.blockers)
        )
    if change.candidate.model == getattr(
        current_settings, "cognitive_secondary_model"
        if change.role == "primary" else "cognitive_primary_model"
    ):
        raise ValueError("dual cognitive roles must remain distinct")
    if not callable(verify_operator_and_install_receipts) or (
        verify_operator_and_install_receipts(change) is not True
    ):
        raise PermissionError("trusted operator/model-install evidence was not verified")
    # A plan is intentionally immutable and cannot be used as its own grant.
    from dataclasses import replace
    proposed = replace(
        current_settings,
        **{f"cognitive_{change.role}_model": change.candidate.model},
    )
    encoded = RuntimeUserSettingsStore._encode(current_settings)
    return PreparedModelRoleChange(
        role=change.role,
        old_model=change.baseline.model,
        new_model=change.candidate.model,
        previous_settings_sha256=sha256(encoded.encode("utf-8")).hexdigest(),
        proposed_settings=proposed,
        operator_approval_ref=change.operator_approval_ref,
        rollback_model=change.baseline.model,
        independently_reviewed=True,
        can_apply_now=False,
    )
