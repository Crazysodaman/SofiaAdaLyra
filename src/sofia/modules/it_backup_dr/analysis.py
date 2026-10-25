"""MOD-IT-BACKUP-DR: interpret supplied backup and restore-drill evidence.

Does not produce backups, perform restores, inspect canonical Sofía state,
or assert that a backup can be restored without a verified restore test.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-IT-BACKUP-DR"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "it.backup_dr.assess_recovery.v1"
PROFILE = "ADVISORY"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_FIELDS = frozenset({"source_ref", "dataset_ref", "observed_at", "last_backup_at", "backup_state", "integrity_check", "restore_drill", "rpo_seconds", "rto_seconds", "restore_duration_seconds"})


def _time(value: object, label: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(f"invalid {label}")
    try:
        t = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid {label}") from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError(f"{label} needs timezone")
    return t.astimezone(timezone.utc)


def _seconds(value: object, label: str) -> int:
    if type(value) is not int or not 1 <= value <= 31_536_000:
        raise ValueError(f"invalid {label}")
    return value


def assess_recovery(observation: Mapping[str, object], *, now: datetime, max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(observation, Mapping) or set(observation) != _FIELDS:
        raise ValueError("backup observation fields mismatch")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now requires timezone")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86_400:
        raise ValueError("invalid max_age_seconds")
    source, dataset = observation["source_ref"], observation["dataset_ref"]
    if any(not isinstance(x, str) or _REF.fullmatch(x) is None for x in (source, dataset)):
        raise ValueError("invalid scoped dataset")
    if observation["backup_state"] not in {"completed", "failed", "unknown"}:
        raise ValueError("invalid backup_state")
    if observation["integrity_check"] not in {"passed", "failed", "not_run"}:
        raise ValueError("invalid integrity_check")
    if observation["restore_drill"] not in {"passed", "failed", "not_run"}:
        raise ValueError("invalid restore_drill")
    rpo = _seconds(observation["rpo_seconds"], "rpo_seconds")
    rto = _seconds(observation["rto_seconds"], "rto_seconds")
    duration = observation["restore_duration_seconds"]
    if duration is not None and (type(duration) is not int or not 0 <= duration <= 31_536_000):
        raise ValueError("invalid restore_duration_seconds")
    if (observation["restore_drill"] == "not_run" and duration is not None) or (observation["restore_drill"] == "passed" and duration is None):
        raise ValueError("restore drill duration evidence mismatch")
    observed = _time(observation["observed_at"], "observed_at")
    last_backup = observation["last_backup_at"]
    backup_at = None if last_backup is None else _time(last_backup, "last_backup_at")
    if backup_at is not None and backup_at > observed:
        raise ValueError("backup cannot occur after observation")
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = "future" if age < -5 else "stale" if age > max_age_seconds else "fresh"
    flags: list[str] = []
    backup_age = None
    if freshness == "fresh":
        if observation["backup_state"] == "failed":
            flags.append("backup_failure_reported")
        elif observation["backup_state"] == "unknown":
            flags.append("backup_completion_unknown")
        if backup_at is None:
            flags.append("last_backup_unknown")
        else:
            backup_age = max(0, round((now.astimezone(timezone.utc) - backup_at).total_seconds()))
            if backup_age > rpo:
                flags.append("rpo_exceeded")
        if observation["integrity_check"] == "failed":
            flags.append("integrity_failure_reported")
        elif observation["integrity_check"] == "not_run":
            flags.append("integrity_not_verified")
        if observation["restore_drill"] == "failed":
            flags.append("restore_drill_failure_reported")
        elif observation["restore_drill"] == "not_run":
            flags.append("restore_not_verified")
        elif duration is not None and duration > rto:
            flags.append("rto_exceeded_in_drill")
    return {"schema": "sofia.it.backup_dr.report.v1", "module_id": MODULE_ID, "sdk_protocol": str(SDK_PROTOCOL_VERSION),
            "source_ref": source, "dataset_ref": dataset, "observed_at": observed.isoformat(), "freshness": freshness,
            "classification": "unknown" if freshness != "fresh" or observation["backup_state"] == "unknown" else "degraded" if flags else "no_issue_observed",
            "last_backup_age_seconds": backup_age,
            # The source claims a restore drill passed, but this is not an independently certified recovery outcome.
            "restore_claim": "supplied_pass" if freshness == "fresh" and observation["restore_drill"] == "passed" else "not_verified",
            "flags": flags, "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Review backup recency and supplied restore-drill outcomes without backup or restore effects.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"observation"}:
            raise ValueError("invalid backup capability request")
        return assess_recovery(request.parameters["observation"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
