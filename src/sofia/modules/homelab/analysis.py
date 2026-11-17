"""MOD-HOMELAB: impact assessment over bounded owner-supplied service topology.

Do not discover hosts, provision VMs or treat a service record as Fleet trust.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-HOMELAB"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "homelab.assess_services.v1"
PROFILE = "ADVISORY"
RESOURCES = (("cpu_millicores", 80), ("ram_mib", 48), ("gpu_mib", 0))
REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
REQUIRED_FIELDS = frozenset({"source_ref", "service_ref", "host_ref", "observed_at", "state", "depends_on"})
OPTIONAL_FIELDS = frozenset({"note"})
STATES = frozenset({"healthy", "degraded", "unavailable", "unknown"})
_MAX_NOTE = 280
_SENSITIVE_SEGMENTS = frozenset({"password", "passwd", "secret", "secrets", "token", "apikey", "api_key", "credential", "credentials", "private_key", "privkey", "access_key"})
_SECRET_ASSIGN = re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential)s?\s*[:=]\s*[^\s,;]{1,256}")
_BEARER = re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_URL_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s@]{1,256}@")
_WIN_PATH = re.compile(r"(?i)\b[A-Za-z]:\\(?:[^\s,;\\]+\\){0,12}[^\s,;\\]*")
_UNC_PATH = re.compile(r"\\\\[^\s,;]{1,256}")
_PRIVATE_PATH = re.compile(r"(?i)(?<![\w.-])/(?:home|users|root|private|etc|tmp|var|opt|srv|mnt|data)/[^\s,;]{1,256}")
_EMAIL = re.compile(r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _safe_ref(value: object, label: str) -> str:
    if not isinstance(value, str) or REF.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
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


def _redact_text(value: object) -> tuple[str | None, int]:
    if value is None:
        return None, 0
    if not isinstance(value, str) or len(value) > _MAX_NOTE:
        raise ValueError("invalid service note")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("control characters in service note")
    text = value
    removed = 0
    for pattern in (_SECRET_ASSIGN, _BEARER, _URL_USERINFO, _WIN_PATH, _UNC_PATH, _PRIVATE_PATH, _EMAIL):
        text, count = pattern.subn("<redacted>", text)
        removed += count
    return text, removed


def _time(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid observed_at")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("observed_at must include timezone")
    return result.astimezone(timezone.utc)


def assess_services(observations: list[Mapping[str, object]], *, now: datetime,
                    max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError("invalid max_age_seconds")
    if type(observations) is not list or not 1 <= len(observations) <= 64:
        raise ValueError("expect 1..64 service observations")
    entries: dict[str, dict[str, object]] = {}
    redactions = 0
    for item in observations:
        if not isinstance(item, Mapping) or not REQUIRED_FIELDS.issubset(item) or not set(item).issubset(REQUIRED_FIELDS | OPTIONAL_FIELDS):
            raise ValueError("service observation requires exact schema")
        source = _safe_ref(item["source_ref"], "source_ref")
        service = _safe_ref(item["service_ref"], "service_ref")
        host = _safe_ref(item["host_ref"], "host_ref")
        key = service
        if key in entries:
            raise ValueError("duplicate service_ref")
        if not isinstance(item["state"], str) or item["state"] not in STATES:
            raise ValueError("invalid service state")
        deps = item["depends_on"]
        if type(deps) is not list or len(deps) > 16 or any(not isinstance(d, str) or _safe_ref(d, "dependency") is None for d in deps):
            raise ValueError("invalid service dependencies")
        if len(set(deps)) != len(deps) or key in deps:
            raise ValueError("duplicate or self-dependent service")
        note, note_redactions = _redact_text(item.get("note"))
        redactions += note_redactions
        at = _time(item["observed_at"])
        age = (now.astimezone(timezone.utc) - at).total_seconds()
        freshness = "future" if age < -5 else "stale" if age > max_age_seconds else "fresh"
        entries[key] = {"source": source, "host": host, "state": item["state"], "note": note,
                        "freshness": freshness, "observed_at": at.isoformat(), "deps": tuple(deps)}
    # Never infer impact from an undeclared peer or a dependency from another provenance scope.
    for key, entry in entries.items():
        for dependency in entry["deps"]:
            if dependency not in entries:
                raise ValueError(f"unknown dependency for {key}")
            if entries[dependency]["source"] != entry["source"]:
                raise ValueError("cross-source dependency requires an authenticated Platform join")
    visiting, visited = set(), set()
    def check_cycle(key: str):
        if key in visiting:
            raise ValueError("cyclic service dependencies")
        if key in visited:
            return
        visiting.add(key)
        for dependency in entries[key]["deps"]:
            check_cycle(dependency)
        visiting.remove(key)
        visited.add(key)
    for key in entries:
        check_cycle(key)
    results: list[dict[str, object]] = []
    counts = {"fresh": 0, "stale": 0, "future": 0}
    for key in sorted(entries):
        item = entries[key]
        counts[item["freshness"]] += 1
        dependency_flags = []
        if item["freshness"] == "fresh":
            dependency_flags = sorted(dep for dep in item["deps"] if
                                      entries[dep]["freshness"] == "fresh" and entries[dep]["state"] == "unavailable")
        unknown_upstreams = sorted(dep for dep in item["deps"] if entries[dep]["freshness"] != "fresh" or entries[dep]["state"] == "unknown")
        classification = "unknown" if item["freshness"] != "fresh" or item["state"] == "unknown" else (
            "attention" if item["state"] != "healthy" or dependency_flags or unknown_upstreams else "no_issue_observed")
        results.append({"service_ref": key, "source_ref": item["source"], "host_ref": item["host"],
                        "observed_at": item["observed_at"], "freshness": item["freshness"],
                        "reported_state": item["state"] if item["freshness"] == "fresh" else "unknown",
                        "classification": classification, "unavailable_upstreams": dependency_flags,
                        "unknown_upstreams": unknown_upstreams, "note": item["note"]})
    return {"schema": "sofia.homelab.services.report.v1", "module_id": MODULE_ID,
            "sdk_protocol": str(SDK_PROTOCOL_VERSION), "services": results, "freshness_counts": counts,
            "redactions": redactions, "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Interpret a scoped, bounded homelab service dependency snapshot without host actions.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"observations"}:
            raise ValueError("invalid Homelab capability request")
        return assess_services(request.parameters["observations"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
