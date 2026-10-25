"""MOD-IT-DATABASE: bounded interpretation of database telemetry, never SQL.

Database credentials, query execution and actual connection status belong
entirely to approved producer adapters and the Platform trust boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = "MOD-IT-DATABASE"
MODULE_VERSION = "0.1.0"
CAPABILITY_ID = "it.database.analyze_status.v1"
PROFILE = "ADVISORY"
RESOURCES = (("cpu_millicores", 50), ("ram_mib", 32), ("gpu_mib", 0))
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
_FIELDS = frozenset({"source_ref", "database_ref", "observed_at", "service_state", "connections_used", "connections_limit", "replica_lag_seconds", "p95_query_ms", "errors_last_5m"})


def _bounded_number(value: object, label: str, maximum: float, *, integer: bool = False) -> float | int:
    if integer:
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError(f"invalid {label}")
        return value
    if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f"invalid {label}")
    return float(value)


def _time(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid observed_at")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timezone required")
    return result.astimezone(timezone.utc)


def analyze_status(status: Mapping[str, object], *, now: datetime, max_age_seconds: int = 300) -> dict[str, object]:
    if not isinstance(status, Mapping) or set(status) != _FIELDS:
        raise ValueError("database status fields mismatch")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now requires timezone")
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86_400:
        raise ValueError("invalid max_age_seconds")
    source, db = status["source_ref"], status["database_ref"]
    if any(not isinstance(x, str) or _REF.fullmatch(x) is None for x in (source, db)):
        raise ValueError("invalid database identity")
    state = status["service_state"]
    if not isinstance(state, str) or state not in {"up", "down", "unknown"}:
        raise ValueError("invalid service_state")
    used = _bounded_number(status["connections_used"], "connections_used", 10_000_000, integer=True)
    limit = _bounded_number(status["connections_limit"], "connections_limit", 10_000_000, integer=True)
    if limit == 0 or used > limit:
        raise ValueError("connections count exceeds declared limit")
    lag = status["replica_lag_seconds"]
    p95 = status["p95_query_ms"]
    if lag is not None:
        _bounded_number(lag, "replica_lag_seconds", 2_592_000)
    if p95 is not None:
        _bounded_number(p95, "p95_query_ms", 3_600_000)
    errors = _bounded_number(status["errors_last_5m"], "errors_last_5m", 10_000_000, integer=True)
    when = _time(status["observed_at"])
    age = (now.astimezone(timezone.utc) - when).total_seconds()
    freshness = "future" if age < -5 else "stale" if age > max_age_seconds else "fresh"
    ratio = None
    flags: list[str] = []
    if freshness == "fresh":
        ratio = round(100.0 * used / limit, 3)
        if state == "down":
            flags.append("database_down_reported")
        elif state == "unknown":
            flags.append("database_state_unknown")
        if ratio >= 90:
            flags.append("connection_pressure")
        if lag is not None and lag > 30:
            flags.append("replica_lag_elevated")
        if p95 is not None and p95 > 1000:
            flags.append("query_latency_elevated")
        if errors:
            flags.append("errors_reported")
    classification = "unknown" if freshness != "fresh" or state == "unknown" else "degraded" if flags else "no_issue_observed"
    return {"schema": "sofia.it.database.report.v1", "module_id": MODULE_ID, "sdk_protocol": str(SDK_PROTOCOL_VERSION),
            "source_ref": source, "database_ref": db, "observed_at": when.isoformat(), "freshness": freshness,
            "classification": classification, "connection_percent": ratio, "flags": flags,
            "evidence_class": "supplied_unverified", "effect": "none"}


def capability_registrations():
    cap = Capability(CAPABILITY_ID, "Summarize database service, connection, replica and latency observations without running SQL.")
    def handler(request: CapabilityRequest):
        if request.capability != cap or set(request.parameters) != {"status"}:
            raise ValueError("invalid database capability request")
        return analyze_status(request.parameters["status"], now=datetime.now(timezone.utc))
    return ((cap, handler),)
