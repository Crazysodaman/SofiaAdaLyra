"""Controlled model-role replacement plans, not automatic model deployment.

Reuses RuntimeUserSettings, existing model lifecycle, and independent
ModelTrialEvidence. A cognitive provider cannot authorize its own switch.
The plan never rewrites canonical identity, memory or policy state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import closing
from hashlib import sha256
import json
import sqlite3
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


@dataclass(frozen=True, slots=True)
class ModelPromotionReceipt:
    """Canonical, human-authorized role mapping transition result."""

    operator_approval_ref: str
    role: str
    previous_model: str
    proposed_model: str
    status: str
    reason: str


class ModelPromotionUncertain(RuntimeError):
    """An attempted provider change lacks proven settled live state."""


def promote_prepared_model_role(
    *, plan: PreparedModelRoleChange,
    settings_store: RuntimeUserSettingsStore,
    verify_operator_fence_and_install: Callable[[PreparedModelRoleChange], bool],
    drain_active_role: Callable[[str], bool],
    apply_runtime_settings: Callable[[RuntimeUserSettings], bool],
    health_and_continuity_ok: Callable[[str, str], bool],
    at: datetime,
) -> ModelPromotionReceipt:
    """Approved two-stage model promotion with crash/uncertain recovery.

    A cognitive model NEVER supplies valid approval or writer fencing.
    The caller is a privileged host broker capable of actual role draining,
    runtime reconfiguration, and independent continuity/health checks. This
    function does not load models or make external host changes by itself.
    """
    if not isinstance(plan, PreparedModelRoleChange):
        raise TypeError("typed, independently prepared role plan required")
    if not isinstance(settings_store, RuntimeUserSettingsStore):
        raise TypeError("canonical settings owner required")
    if (
        plan.can_apply_now is not False or not plan.independently_reviewed
        or plan.role not in {"primary", "secondary"}
        or not plan.operator_approval_ref.strip()
    ):
        raise PermissionError("model promotion plan is not independently reviewed")
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("trusted aware promotion timestamp required")
    if not all(map(callable, (
        verify_operator_fence_and_install, drain_active_role,
        apply_runtime_settings, health_and_continuity_ok,
    ))):
        raise TypeError("all four independent host control callbacks are required")
    if verify_operator_fence_and_install(plan) is not True:
        raise PermissionError("owner approval / canonical writer fence denied")
    if drain_active_role(plan.role) is not True:
        raise RuntimeError("active model turns were not drained")
    expected = plan.previous_settings_sha256
    proposed_raw = RuntimeUserSettingsStore._encode(plan.proposed_settings)
    proposed_hash = sha256(proposed_raw.encode("utf-8")).hexdigest()
    if not plan.proposed_settings or proposed_hash == expected:
        raise ValueError("candidate model settings did not change")
    stamp = at.astimezone(timezone.utc).isoformat()
    sqlite_uri = settings_store.path.absolute().as_uri() + "?mode=rw"

    def connection() -> sqlite3.Connection:
        db = sqlite3.connect(sqlite_uri, uri=True, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def existing_receipt(db: sqlite3.Connection):
        return db.execute(
            "SELECT role,old_model,new_model,previous_hash,proposed_hash,"
            "status,reason FROM cognitive_model_promotion "
            "WHERE approval_ref=?", (plan.operator_approval_ref,),
        ).fetchone()

    # Create the durable role-transition marker in the SAME canonical DB.
    # There is no reusable "model is healthy" flag or shadow settings owner.
    with closing(connection()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS cognitive_model_promotion("
            "approval_ref TEXT PRIMARY KEY,role TEXT NOT NULL,"
            "old_model TEXT NOT NULL,new_model TEXT NOT NULL,"
            "previous_hash TEXT NOT NULL,proposed_hash TEXT NOT NULL,"
            "status TEXT NOT NULL CHECK(status IN "
            "('applying','accepted','rolled_back','uncertain')),"
            "reason TEXT NOT NULL,created_at TEXT NOT NULL,"
            "updated_at TEXT NOT NULL)"
        )
        old_receipt = existing_receipt(db)
        if old_receipt is not None:
            if tuple(old_receipt[:5]) != (
                plan.role,plan.old_model,plan.new_model,
                expected,proposed_hash,
            ):
                raise PermissionError("approval reference is bound to a different plan")
            if old_receipt[5] == "accepted":
                return ModelPromotionReceipt(
                    plan.operator_approval_ref, plan.role,
                    plan.old_model, plan.new_model, "accepted",
                    old_receipt[6],
                )
            # An interrupted hot-swap may have changed external model state.
            # Never re-run it because the first process left no completion.
            raise ModelPromotionUncertain(
                "previous model promotion has no replayable settled outcome"
            )
        old_row = db.execute(
            "SELECT value_json FROM ui_runtime_settings WHERE settings_key=?",
            (settings_store._KEY,),
        ).fetchone()
        baseline_raw = (
            RuntimeUserSettingsStore._encode(RuntimeUserSettings())
            if old_row is None else str(old_row[0])
        )
        if sha256(baseline_raw.encode("utf-8")).hexdigest() != expected:
            raise RuntimeError("canonical settings changed since role trial")
        prior_settings = RuntimeUserSettingsStore._decode(baseline_raw)
        if getattr(prior_settings, f"cognitive_{plan.role}_model") != plan.old_model:
            raise PermissionError("original role model differs from reviewed baseline")
        if getattr(plan.proposed_settings, f"cognitive_{plan.role}_model") != plan.new_model:
            raise PermissionError("proposed role model differs from reviewed candidate")
        settings_store.save(plan.proposed_settings, at=at, connection=db)
        db.execute(
            "INSERT INTO cognitive_model_promotion VALUES(?,?,?,?,?,?,?,?,?,?)",
            (plan.operator_approval_ref, plan.role, plan.old_model,
             plan.new_model, expected, proposed_hash, "applying",
             "runtime_reload_pending", stamp, stamp),
        )

    applied = False
    reason = "health_or_provider_transition_unconfirmed"
    try:
        applied = apply_runtime_settings(plan.proposed_settings) is True
        if applied and health_and_continuity_ok(plan.role, plan.new_model) is True:
            with closing(connection()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                saved = db.execute(
                    "SELECT value_json FROM ui_runtime_settings WHERE settings_key=?",
                    (settings_store._KEY,),
                ).fetchone()
                if saved is None or sha256(saved[0].encode("utf-8")).hexdigest() != proposed_hash:
                    raise ModelPromotionUncertain(
                        "canonical role settings changed during health acceptance"
                    )
                accepted = db.execute(
                    "UPDATE cognitive_model_promotion SET status='accepted',"
                    "reason='independent_health_continuity_accepted',updated_at=? "
                    "WHERE approval_ref=? AND status='applying'",
                    (datetime.now(timezone.utc).isoformat(),plan.operator_approval_ref),
                )
                if accepted.rowcount != 1:
                    raise ModelPromotionUncertain(
                        "model acceptance receipt was not durably transitioned"
                    )
            return ModelPromotionReceipt(
                plan.operator_approval_ref,plan.role,plan.old_model,
                plan.new_model,"accepted","independent_health_continuity_accepted",
            )
    except Exception as error:
        reason = type(error).__name__
    # Compensating rollback is permitted ONLY if this proposal still owns
    # the canonical role settings. A concurrent operator edit is not ours
    # to overwrite. Provider rollback must independently succeed as well.
    restored_settings = False
    with closing(connection()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        saved = db.execute(
            "SELECT value_json FROM ui_runtime_settings WHERE settings_key=?",
            (settings_store._KEY,),
        ).fetchone()
        if saved is not None and sha256(saved[0].encode("utf-8")).hexdigest() == proposed_hash:
            settings_store.save(prior_settings, at=at, connection=db)
            restored_settings = True
        unresolved = db.execute(
            "UPDATE cognitive_model_promotion SET status='uncertain',"
            "reason=?,updated_at=? WHERE approval_ref=? AND status='applying'",
            (reason, datetime.now(timezone.utc).isoformat(),
             plan.operator_approval_ref),
        )
        if unresolved.rowcount != 1:
            raise ModelPromotionUncertain(
                "model promotion no longer owns its transition receipt"
            )
    provider_restored = False
    if restored_settings:
        try:
            provider_restored = apply_runtime_settings(prior_settings) is True
        except Exception:
            provider_restored = False
    if restored_settings and provider_restored:
        with closing(connection()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            rolled_back = db.execute(
                "UPDATE cognitive_model_promotion SET status='rolled_back',"
                "reason='candidate_not_accepted_original_restored',updated_at=? "
                "WHERE approval_ref=? AND status='uncertain'",
                (datetime.now(timezone.utc).isoformat(),
                 plan.operator_approval_ref),
            )
            if rolled_back.rowcount != 1:
                raise ModelPromotionUncertain(
                    "model rollback receipt was not durably transitioned"
                )
        return ModelPromotionReceipt(
            plan.operator_approval_ref,plan.role,plan.old_model,
            plan.new_model,"rolled_back","candidate_not_accepted_original_restored",
        )
    raise ModelPromotionUncertain(
        "model promotion not settled; host operator recovery is required"
    )
