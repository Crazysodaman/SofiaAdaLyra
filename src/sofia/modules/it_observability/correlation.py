"""Deterministic incident correlation over bounded, pre-authorized observations."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Mapping
import re
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-IT-OBSERVABILITY"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "it.observability.correlate.v1"
PROFILE = "ADVISORY"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_STATES = frozenset({"ok", "warning", "critical", "unknown"})
_FIELDS = frozenset({"source_ref", "component_ref", "observed_at", "state", "signal"})
_SIGNALS = frozenset({"cpu", "memory", "disk", "service", "network", "temperature", "backup"})


def correlate(observations: list[Mapping[str, object]], *, now: datetime, max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware now required")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError("invalid age limit")
    if type(observations) is not list or not 1 <= len(observations) <= 128:
        raise ValueError("expected 1..128 observations")
    groups = {}
    dedupe = set()
    stale = 0
    for obs in observations:
        if not isinstance(obs, Mapping) or set(obs) != _FIELDS:
            raise ValueError("observation schema mismatch")
        source, component, signal = (obs[k] for k in ("source_ref", "component_ref", "signal"))
        if any(not isinstance(s, str) or not _ID.fullmatch(s) for s in (source, component)) or signal not in _SIGNALS or obs["state"] not in _STATES:
            raise ValueError("invalid observation identity or status")
        try:
            when = datetime.fromisoformat(obs["observed_at"])
            if when.tzinfo is None or when.utcoffset() is None:
                raise ValueError("timezone missing")
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid observation timestamp") from exc
        key = (source, component, signal)
        if key in dedupe:
            raise ValueError("ambiguous duplicate observation")
        dedupe.add(key)
        age = (now.astimezone(timezone.utc) - when.astimezone(timezone.utc)).total_seconds()
        if age < -5 or age > max_age_seconds:
            stale += 1
            continue
        groups.setdefault((source, component), []).append((signal, obs["state"]))
    incidents = []
    for (source, component), points in sorted(groups.items()):
        degraded = sorted(s for s, status in points if status in {"warning", "critical"})
        unknown = sorted(s for s, status in points if status == "unknown")
        severity = "critical" if any(st == "critical" for _, st in points) else "warning" if degraded else "unknown" if unknown else "ok"
        incidents.append({"source_ref": source, "component_ref": component, "severity": severity, "degraded_signals": degraded, "unknown_signals": unknown, "correlated": len(degraded) > 1})
    return {"schema": "sofia.it.observability.report.v1", "module_id": MODULE_ID, "sdk_protocol": str(SDK_PROTOCOL_VERSION), "incidents": incidents, "excluded_out_of_window": stale, "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Correlate bounded platform-supplied service and resource observations.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"observations"}:
            raise ValueError("invalid capability request")
        return correlate(request.parameters["observations"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
