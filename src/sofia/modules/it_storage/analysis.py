"""MOD-IT-STORAGE: effect-free classification of authorized volume observations.

No filesystem access, path traversal, mount probing or destructive repairs.
All input is an untrusted projection until Platform verifies its producer.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-IT-STORAGE"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "it.storage.analyze_volumes.v1"
PROFILE = "OBSERVE"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_FIELDS = frozenset({"source_ref", "volume_ref", "observed_at", "total_bytes", "used_bytes", "read_only", "io_errors"})
_MAX_CAPACITY = 1 << 65


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid observation timestamp")
    try:
        at = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid observation timestamp") from exc
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("timezone required")
    return at.astimezone(timezone.utc)


def _integer(value: object, label: str, upper: int) -> int:
    if type(value) is not int or not 0 <= value <= upper:
        raise ValueError(f"invalid {label}")
    return value


def analyze_volumes(volumes: list[Mapping[str, object]], *, now: datetime, max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now requires timezone")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86_400:
        raise ValueError("max_age_seconds out of bounds")
    if type(volumes) is not list or not 1 <= len(volumes) <= 64:
        raise ValueError("volumes must contain 1..64 items")
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, object]] = []
    for item in volumes:
        if not isinstance(item, Mapping) or set(item) != _FIELDS:
            raise ValueError("volume observation fields mismatch")
        source, volume = item["source_ref"], item["volume_ref"]
        if any(not isinstance(v, str) or _REF.fullmatch(v) is None for v in (source, volume)):
            raise ValueError("invalid scoped volume identifier")
        if (source, volume) in seen:
            raise ValueError("duplicate volume observation")
        seen.add((source, volume))
        total = _integer(item["total_bytes"], "total_bytes", _MAX_CAPACITY)
        used = _integer(item["used_bytes"], "used_bytes", _MAX_CAPACITY)
        if total == 0 or used > total:
            raise ValueError("inconsistent volume byte counts")
        io_errors = _integer(item["io_errors"], "io_errors", 1_000_000_000)
        if type(item["read_only"]) is not bool:
            raise ValueError("read_only must be bool")
        observed = _timestamp(item["observed_at"])
        delta = (now.astimezone(timezone.utc) - observed).total_seconds()
        freshness = "future" if delta < -5 else "stale" if delta > max_age_seconds else "fresh"
        flags: list[str] = []
        utilization: float | None = None
        if freshness == "fresh":
            utilization = round(100.0 * used / total, 3)
            if utilization >= 95.0:
                flags.append("capacity_critical")
            elif utilization >= 85.0:
                flags.append("capacity_warning")
            if item["read_only"]:
                flags.append("read_only_observed")
            if io_errors > 0:
                flags.append("io_errors_observed")
        rows.append({"source_ref": source, "volume_ref": volume, "observed_at": observed.isoformat(), "freshness": freshness,
                     "classification": "unknown" if freshness != "fresh" else "degraded" if flags else "no_issue_observed",
                     "used_percent": utilization, "flags": flags})
    return {"schema": "sofia.it.storage.report.v1", "module_id": MODULE_ID, "sdk_protocol": str(SDK_PROTOCOL_VERSION),
            "volumes": rows, "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Interpret supplied scoped volume usage and failure counters without storage access.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"volumes"}:
            raise ValueError("invalid storage capability request")
        return analyze_volumes(request.parameters["volumes"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
