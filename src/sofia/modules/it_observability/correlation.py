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
_REQUIRED_FIELDS = frozenset({"source_ref", "component_ref", "observed_at", "state", "signal"})
_OPTIONAL_FIELDS = frozenset({"summary"})
_SIGNALS = frozenset({"cpu", "memory", "disk", "service", "network", "temperature", "backup"})
_MAX_SUMMARY = 280
_SENSITIVE_SEGMENTS = frozenset({"password", "passwd", "secret", "secrets", "token", "apikey", "api_key", "credential", "credentials", "private_key", "privkey", "access_key"})
_SECRET_ASSIGN = re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential)s?\s*[:=]\s*[^\s,;]{1,256}")
_BEARER = re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_URL_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s@]{1,256}@")
_WIN_PATH = re.compile(r"(?i)\b[A-Za-z]:\\(?:[^\s,;\\]+\\){0,12}[^\s,;\\]*")
_UNC_PATH = re.compile(r"\\\\[^\s,;]{1,256}")
_PRIVATE_PATH = re.compile(r"(?i)(?<![\w.-])/(?:home|users|root|private|etc|tmp|var|opt|srv|mnt|data)/[^\s,;]{1,256}")
_EMAIL = re.compile(r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _safe_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"invalid observation {label}")
    if "\\" in value or "//" in value or re.match(r"^[A-Za-z]:/", value):
        raise ValueError(f"unsafe observation {label}")
    if re.search(r"(?i)(^|[:/])(?:home|users|root|private|etc|tmp|var|opt|srv|mnt|data)(?:/|$)", value):
        raise ValueError(f"private path in observation {label}")
    segments = re.split(r"[:/]", value)
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError(f"unsafe observation {label}")
    if any(segment.lower() in _SENSITIVE_SEGMENTS for segment in segments):
        raise ValueError(f"sensitive observation {label}")
    return value


def _redact_text(value: object) -> tuple[str | None, int]:
    if value is None:
        return None, 0
    if not isinstance(value, str) or len(value) > _MAX_SUMMARY:
        raise ValueError("invalid observation summary")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("control characters in observation summary")
    text = value
    removed = 0
    for pattern in (_SECRET_ASSIGN, _BEARER, _URL_USERINFO, _WIN_PATH, _UNC_PATH, _PRIVATE_PATH, _EMAIL):
        text, count = pattern.subn("<redacted>", text)
        removed += count
    return text, removed


def correlate(observations: list[Mapping[str, object]], *, now: datetime, max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware now required")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError("invalid age limit")
    if type(observations) is not list or not 1 <= len(observations) <= 128:
        raise ValueError("expected 1..128 observations")
    groups = {}
    summaries: dict[tuple[str, str], list[str]] = {}
    stale_rows = []
    dedupe = set()
    stale = 0
    redactions = 0
    for obs in observations:
        if not isinstance(obs, Mapping) or not _REQUIRED_FIELDS.issubset(obs) or not set(obs).issubset(_REQUIRED_FIELDS | _OPTIONAL_FIELDS):
            raise ValueError("observation schema mismatch")
        source = _safe_id(obs["source_ref"], "source_ref")
        component = _safe_id(obs["component_ref"], "component_ref")
        signal = obs["signal"]
        if not isinstance(signal, str) or signal not in _SIGNALS or not isinstance(obs["state"], str) or obs["state"] not in _STATES:
            raise ValueError("invalid observation identity or status")
        summary, redacted = _redact_text(obs.get("summary"))
        redactions += redacted
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
            stale_rows.append({"source_ref": source, "component_ref": component, "signal": signal,
                               "observed_at": when.astimezone(timezone.utc).isoformat(),
                               "freshness": "future" if age < -5 else "stale", "summary": summary})
            continue
        groups.setdefault((source, component), []).append((signal, obs["state"]))
        if summary is not None:
            summaries.setdefault((source, component), []).append(summary)
    incidents = []
    for (source, component), points in sorted(groups.items()):
        degraded = sorted(s for s, status in points if status in {"warning", "critical"})
        unknown = sorted(s for s, status in points if status == "unknown")
        severity = "critical" if any(st == "critical" for _, st in points) else "warning" if degraded else "unknown" if unknown else "ok"
        incidents.append({"source_ref": source, "component_ref": component, "severity": severity,
                          "freshness": "fresh", "degraded_signals": degraded, "unknown_signals": unknown,
                          "correlated": len(degraded) > 1, "summaries": sorted(summaries.get((source, component), []))})
    return {"schema": "sofia.it.observability.report.v1", "module_id": MODULE_ID, "sdk_protocol": str(SDK_PROTOCOL_VERSION),
            "incidents": incidents, "excluded_out_of_window": stale, "stale_observations": stale_rows,
            "redactions": redactions, "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Correlate bounded platform-supplied service and resource observations and redact summaries.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"observations"}:
            raise ValueError("invalid capability request")
        return correlate(request.parameters["observations"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
