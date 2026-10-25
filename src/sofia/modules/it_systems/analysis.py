"""Read-only interpretation of externally measured system resources."""
from __future__ import annotations
from datetime import datetime, timezone
from math import isfinite
from typing import Mapping
import re
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-IT-SYSTEMS"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "it.systems.analyze_snapshot.v1"
PROFILE = "ADVISORY"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_FIELDS = frozenset({"source_ref", "observed_at", "cpu_percent", "memory_percent", "disk_percent", "uptime_seconds"})


def inspect_system(snapshot: Mapping[str, object], *, now: datetime, max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError("invalid system snapshot schema")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware now required")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError("invalid freshness limit")
    source = snapshot["source_ref"]
    if not isinstance(source, str) or not _ID.fullmatch(source):
        raise ValueError("invalid source_ref")
    try:
        observed = datetime.fromisoformat(snapshot["observed_at"])
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("timestamp timezone missing")
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid timestamp") from exc
    for field in ("cpu_percent", "memory_percent", "disk_percent"):
        value = snapshot[field]
        if value is not None and (type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 100):
            raise ValueError("invalid resource percent")
    uptime = snapshot["uptime_seconds"]
    if uptime is not None and (type(uptime) not in (int, float) or not isfinite(uptime) or not 0 <= uptime <= 1e10):
        raise ValueError("invalid uptime")
    age = (now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    freshness = "future" if age < -5 else "stale" if age > max_age_seconds else "fresh"
    flags = []
    if freshness == "fresh":
        for field, threshold in (("cpu_percent", 90), ("memory_percent", 90), ("disk_percent", 95)):
            value = snapshot[field]
            if value is not None and value >= threshold:
                flags.append(field.removesuffix("_percent") + "_pressure")
    return {"schema": "sofia.it.systems.report.v1", "module_id": MODULE_ID, "sdk_protocol": str(SDK_PROTOCOL_VERSION), "source_ref": source, "freshness": freshness, "pressure_flags": flags, "classification": "unknown" if freshness != "fresh" or all(snapshot[f] is None for f in ("cpu_percent", "memory_percent", "disk_percent")) else "pressure_observed" if flags else "no_pressure_observed", "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Interpret current authorized system resource snapshots, without executing commands.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"snapshot"}:
            raise ValueError("invalid capability request")
        return inspect_system(request.parameters["snapshot"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
