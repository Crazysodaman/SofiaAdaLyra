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
_REQUIRED_FIELDS = frozenset({"source_ref", "volume_ref", "observed_at", "total_bytes", "used_bytes", "read_only", "io_errors"})
_OPTIONAL_FIELDS = frozenset({"smart_state", "growth_bytes_per_day", "note"})
_MAX_CAPACITY = 1 << 65
_MAX_NOTE = 280
_SMART_STATES = frozenset({"passed", "warning", "failed", "unknown"})
_SENSITIVE_SEGMENTS = frozenset({"password", "passwd", "secret", "secrets", "token", "apikey", "api_key", "credential", "credentials", "private_key", "privkey", "access_key"})
_SECRET_ASSIGN = re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential)s?\s*[:=]\s*[^\s,;]{1,256}")
_BEARER = re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_URL_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s@]{1,256}@")
_WIN_PATH = re.compile(r"(?i)\b[A-Za-z]:\\(?:[^\s,;\\]+\\){0,12}[^\s,;\\]*")
_UNC_PATH = re.compile(r"\\\\[^\s,;]{1,256}")
_PRIVATE_PATH = re.compile(r"(?i)(?<![\w.-])/(?:home|users|root|private|etc|tmp|var|opt|srv|mnt|data)/[^\s,;]{1,256}")
_EMAIL = re.compile(r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _safe_ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise ValueError(f"invalid scoped {label}")
    if "\\" in value or "//" in value or re.match(r"^[A-Za-z]:/", value):
        raise ValueError(f"unsafe {label}")
    if re.search(r"(?i)(^|[:/])(?:home|users|root|private|etc|tmp|var|opt|srv|mnt|data)(?:/|$)", value):
        raise ValueError(f"private path in {label}")
    segments = re.split(r"[:/]", value)
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError(f"unsafe {label}")
    if any(segment.lower() in _SENSITIVE_SEGMENTS for segment in segments):
        raise ValueError(f"sensitive {label}")
    return value


def _redact_text(value: object, label: str) -> tuple[str | None, int]:
    if value is None:
        return None, 0
    if not isinstance(value, str) or len(value) > _MAX_NOTE:
        raise ValueError(f"invalid {label}")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"control characters in {label}")
    text = value
    removed = 0
    for pattern in (_SECRET_ASSIGN, _BEARER, _URL_USERINFO, _WIN_PATH, _UNC_PATH, _PRIVATE_PATH, _EMAIL):
        text, count = pattern.subn("<redacted>", text)
        removed += count
    return text, removed


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
    total_redactions = 0
    for item in volumes:
        if not isinstance(item, Mapping) or not _REQUIRED_FIELDS.issubset(item) or not set(item).issubset(_REQUIRED_FIELDS | _OPTIONAL_FIELDS):
            raise ValueError("volume observation fields mismatch")
        source = _safe_ref(item["source_ref"], "source_ref")
        volume = _safe_ref(item["volume_ref"], "volume_ref")
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
        smart = item.get("smart_state")
        if smart is not None and (not isinstance(smart, str) or smart not in _SMART_STATES):
            raise ValueError("invalid smart_state")
        growth = item.get("growth_bytes_per_day")
        if growth is not None:
            growth = _integer(growth, "growth_bytes_per_day", _MAX_CAPACITY)
        note, note_redactions = _redact_text(item.get("note"), "note")
        total_redactions += note_redactions
        observed = _timestamp(item["observed_at"])
        delta = (now.astimezone(timezone.utc) - observed).total_seconds()
        freshness = "future" if delta < -5 else "stale" if delta > max_age_seconds else "fresh"
        flags: list[str] = []
        utilization: float | None = None
        projected: float | None = None
        smart_observation: str | None = None
        growth_observation: int | None = None
        if freshness == "fresh":
            utilization = round(100.0 * used / total, 3)
            smart_observation = smart
            growth_observation = growth
            if utilization >= 95.0:
                flags.append("capacity_critical")
            elif utilization >= 85.0:
                flags.append("capacity_warning")
            if item["read_only"]:
                flags.append("read_only_observed")
            if io_errors > 0:
                flags.append("io_errors_observed")
            if smart == "failed":
                flags.append("smart_failure_reported")
            elif smart == "warning":
                flags.append("smart_warning_reported")
            elif smart == "unknown":
                flags.append("smart_state_unknown")
            if growth is not None and growth > 0 and used < total:
                projected = round((total - used) / growth, 3)
                if projected <= 30:
                    flags.append("capacity_growth_high")
        unknown_smart = freshness == "fresh" and smart == "unknown"
        rows.append({"source_ref": source, "volume_ref": volume, "observed_at": observed.isoformat(), "freshness": freshness,
                     "classification": "unknown" if freshness != "fresh" or unknown_smart else "degraded" if flags else "no_issue_observed",
                     "used_percent": utilization, "smart_state": smart_observation, "growth_bytes_per_day": growth_observation,
                     "projected_days_to_full": projected, "flags": flags, "note": note, "redactions": note_redactions})
    return {"schema": "sofia.it.storage.report.v1", "module_id": MODULE_ID, "sdk_protocol": str(SDK_PROTOCOL_VERSION),
            "volumes": rows, "redactions": total_redactions, "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Interpret supplied scoped volume usage, growth, SMART-like state and failure counters without storage access.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"volumes"}:
            raise ValueError("invalid storage capability request")
        return analyze_volumes(request.parameters["volumes"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
