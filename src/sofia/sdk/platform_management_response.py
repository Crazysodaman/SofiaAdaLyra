"""Untrusted, bounded and correlated Platform management response v1.

Schema validity DOES NOT authenticate the service. Clients MUST authenticate
the native socket/pipe server independently. Server-side admission and live
SAFE/STOP checks are never derived from this wire document.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import re
import unicodedata
from typing import Mapping

from sofia.sdk.platform_management import UntrustedManagementRead

RESPONSE_SCHEMA = "aegis.platform.management.read-response.v1"
MAX_RESPONSE_BYTES = 32 * 1024
DENIAL_CODES = frozenset({
    "NOT_PERMITTED", "REVOKED", "STOPPED", "STALE_GENERATION",
    "EXPIRED", "UNAVAILABLE",
})
_OUTER = frozenset({
    "schema", "protocol", "request_id", "platform_id",
    "platform_generation", "operation", "source", "observed_at",
    "outcome", "data", "denial",
})
_STATUS = frozenset({
    "platform_id", "generation", "operator_stop", "core_started",
})
_STARTUP = frozenset({
    "platform_id", "generation", "operator_stop", "core_started",
    "core_count", "active_core_count", "startup_state",
    "autostart_enabled_count", "autostart_reconciled_at",
    "management_listening",
})
_STARTUP_STATES = frozenset({
    "ZERO_CORE_HEALTHY", "CORES_RUNNING", "CORES_DISABLED", "DEGRADED",
    "UNKNOWN",
})
_CORE_FIELDS = frozenset({
    "core_id", "installed", "enabled", "startup_mode", "observed_state",
    "generation", "last_error_code",
})
_STARTUP_MODES = frozenset({"on_platform_ready", "manual", "on_demand"})
_OBSERVED_STATES = frozenset({
    "RUNNING", "STOPPED", "STARTING", "FAILED", "UNKNOWN", "NOT_OBSERVED",
})
_CORE_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_ERROR_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
_MAX_COUNT = 65535
_MAX_CORES = 256
_MAX_PORTABLE_INT = 2**53 - 1
_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_SENSITIVE = (
    "secret", "password", "credential", "access_token", "refresh_token",
    "private_key", "api_key", "owner_proof", "authorization",
)
_FORBIDDEN = frozenset({"__proto__", "prototype", "constructor"})


def _startup_data(data: Mapping[str, object], expected: UntrustedManagementRead) -> None:
    if (set(data) != _STARTUP
            or data["platform_id"] != expected.target_platform_id
            or type(data["generation"]) is not int
            or data["generation"] != expected.expected_generation
            or data["operator_stop"] is not False
            or type(data["core_started"]) is not bool
            or type(data["core_count"]) is not int
            or not 0 <= data["core_count"] <= _MAX_COUNT
            or type(data["active_core_count"]) is not int
            or not 0 <= data["active_core_count"] <= data["core_count"]
            or type(data["startup_state"]) is not str
            or data["startup_state"] not in _STARTUP_STATES
            or type(data["autostart_enabled_count"]) is not int
            or not 0 <= data["autostart_enabled_count"] <= _MAX_COUNT
            or type(data["management_listening"]) is not bool):
        raise PermissionError("inconsistent Platform startup status projection")
    reconciled = data["autostart_reconciled_at"]
    if reconciled is not None:
        _timestamp(reconciled)
    if data["core_count"] == 0 and (
        data["active_core_count"] != 0 or data["core_started"]
    ):
        raise PermissionError("inconsistent zero-core startup status")
    if data["startup_state"] == "ZERO_CORE_HEALTHY" and data["core_count"] != 0:
        raise PermissionError("inconsistent zero-core startup state")
    if data["startup_state"] == "CORES_RUNNING" and data["active_core_count"] == 0:
        raise PermissionError("inconsistent running-core startup state")


def _core_data(data: Mapping[str, object], expected: UntrustedManagementRead) -> None:
    if (set(data) != {
            "platform_id", "generation", "operator_stop", "cores",
        }
            or data["platform_id"] != expected.target_platform_id
            or type(data["generation"]) is not int
            or data["generation"] != expected.expected_generation
            or data["operator_stop"] is not False):
        raise PermissionError("inconsistent Platform Core inventory projection")
    rows = data["cores"]
    if isinstance(rows, Mapping) or not isinstance(rows, (list, tuple)):
        raise PermissionError("invalid Platform Core inventory")
    if len(rows) > _MAX_CORES:
        raise PermissionError("Platform Core inventory exceeds bound")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != _CORE_FIELDS:
            raise PermissionError("invalid Platform Core inventory row")
        core_id = row["core_id"]
        installed = row["installed"]
        enabled = row["enabled"]
        startup_mode = row["startup_mode"]
        observed_state = row["observed_state"]
        generation = row["generation"]
        last_error_code = row["last_error_code"]
        if (not isinstance(core_id, str)
                or _CORE_ID.fullmatch(core_id) is None
                or core_id in seen):
            raise PermissionError("invalid or duplicate Platform Core identity")
        if type(installed) is not bool or type(enabled) is not bool:
            raise PermissionError("invalid Platform Core inventory flags")
        if not isinstance(startup_mode, str) or startup_mode not in _STARTUP_MODES:
            raise PermissionError("invalid Platform Core startup mode")
        if (not isinstance(observed_state, str)
                or observed_state not in _OBSERVED_STATES):
            raise PermissionError("invalid Platform Core observed state")
        if (type(generation) is not int
                or not 0 <= generation <= _MAX_PORTABLE_INT):
            raise PermissionError("invalid Platform Core generation")
        if last_error_code is not None and (
            not isinstance(last_error_code, str)
            or _ERROR_CODE.fullmatch(last_error_code) is None
        ):
            raise PermissionError("invalid Platform Core error code")
        seen.add(core_id)


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate management response key")
        out[key] = value
    return out


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not _RFC3339.fullmatch(value):
        raise ValueError("management observation must be RFC3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid management response timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError("management timestamp lacks timezone")
    return parsed.astimezone(timezone.utc)


def _safe_data(value: object, depth: int = 0) -> None:
    if depth > 8:
        raise ValueError("management response nesting exceeds limit")
    if isinstance(value, dict):
        if len(value) > 256:
            raise ValueError("management response contains too many fields")
        for key, member in value.items():
            if (not isinstance(key, str) or not key or len(key) > 160
                    or not key.isascii()
                    or any(unicodedata.category(char) == "Cc" for char in key)):
                raise ValueError("invalid management response key")
            lower = key.lower()
            if lower in _FORBIDDEN or any(part in lower for part in _SENSITIVE):
                raise ValueError("sensitive or unsafe management response key")
            _safe_data(member, depth + 1)
    elif isinstance(value, list):
        if len(value) > 1024:
            raise ValueError("unbounded management response list")
        for member in value:
            _safe_data(member, depth + 1)
    elif isinstance(value, str):
        if any(unicodedata.category(char) in {"Cc", "Cs"} for char in value):
            raise ValueError("control or surrogate characters in management response")
    elif type(value) is float:
        if not math.isfinite(value) or abs(value) > (2**53 - 1):
            raise ValueError("nonportable management number")
    elif type(value) is int:
        if abs(value) > (2**53 - 1):
            raise ValueError("nonportable management integer")
    elif value is None or type(value) is bool:
        return
    else:
        raise ValueError("unsupported management response projection")


@dataclass(frozen=True, slots=True)
class UntrustedManagementResponse:
    """A syntax-checked observation or denial, NEVER an authentication grant."""

    request_id: str
    platform_id: str
    generation: int
    operation: str
    observed_at: str
    outcome: str
    data: Mapping[str, object] | None
    denial_code: str | None

    @classmethod
    def parse(
        cls,
        raw: bytes,
        *,
        expected: UntrustedManagementRead,
        now: datetime,
    ) -> "UntrustedManagementResponse":
        if type(raw) is not bytes or not raw or len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("bounded management response bytes required")
        if not isinstance(expected, UntrustedManagementRead):
            raise TypeError("expected typed request required")
        if (not isinstance(now, datetime) or now.utcoffset() is None):
            raise ValueError("aware receiver time required")
        try:
            doc = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique,
                parse_constant=lambda x: (_ for _ in ()).throw(
                    ValueError("nonfinite management response")
                ),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("invalid management response JSON") from exc
        if not isinstance(doc, dict) or set(doc) != _OUTER:
            raise ValueError("unknown or missing management response fields")
        if (doc["schema"] != RESPONSE_SCHEMA
                or doc["protocol"] != "1.0"
                or doc["source"] != "PLATFORM_SESSION"
                or doc["request_id"] != expected.request_id
                or doc["platform_id"] != expected.target_platform_id
                or type(doc["platform_generation"]) is not int
                or doc["platform_generation"] != expected.expected_generation
                or doc["operation"] != expected.operation):
            raise PermissionError("uncorrelated management response")
        observed = _timestamp(doc["observed_at"])
        created = _timestamp(expected.created_at)
        deadline = _timestamp(expected.deadline)
        moment = now.astimezone(timezone.utc)
        if (observed < created or observed > moment
                or moment >= deadline or observed >= deadline
                or moment - observed > timedelta(seconds=5)):
            raise PermissionError("stale, future or expired management observation")
        outcome = doc["outcome"]
        data, denial = doc["data"], doc["denial"]
        if outcome == "OK":
            if denial is not None or not isinstance(data, dict):
                raise ValueError("successful management response requires data only")
            _safe_data(data)
            if expected.operation == "platform.status" and (
                set(data) != _STATUS
                or data["platform_id"] != expected.target_platform_id
                or type(data["generation"]) is not int
                or data["generation"] != expected.expected_generation
                or type(data["core_started"]) is not bool
                or data["operator_stop"] is not False
            ):
                raise PermissionError("inconsistent Platform status projection")
            if expected.operation == "startup.status":
                _startup_data(data, expected)
            if expected.operation == "core.list":
                _core_data(data, expected)
            code = None
        elif outcome == "DENIED":
            if (data is not None or not isinstance(denial, dict)
                    or set(denial) != {"code"}
                    or type(denial["code"]) is not str
                    or denial["code"] not in DENIAL_CODES):
                raise ValueError("invalid typed management denial")
            code = denial["code"]
        else:
            raise ValueError("unknown management outcome")
        return cls(
            expected.request_id, expected.target_platform_id,
            expected.expected_generation, expected.operation,
            doc["observed_at"], outcome, data, code,
        )


def make_response(
    request: UntrustedManagementRead,
    *,
    observed_at: datetime,
    data: Mapping[str, object] | None = None,
    denial_code: str | None = None,
) -> dict[str, object]:
    """Server wire builder. Caller MUST already have checked current authority."""
    if not isinstance(request, UntrustedManagementRead):
        raise TypeError("typed management request required")
    if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
        raise ValueError("aware service observation time required")
    moment = observed_at.astimezone(timezone.utc)
    if (data is None) == (denial_code is None):
        raise ValueError("exactly one of data or denial_code required")
    if denial_code is not None and denial_code not in DENIAL_CODES:
        raise ValueError("unreviewed denial code")
    if data is not None:
        _safe_data(dict(data))
    doc: dict[str, object] = {
        "schema": RESPONSE_SCHEMA,
        "protocol": "1.0",
        "request_id": request.request_id,
        "platform_id": request.target_platform_id,
        "platform_generation": request.expected_generation,
        "operation": request.operation,
        "source": "PLATFORM_SESSION",
        "observed_at": moment.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "outcome": "DENIED" if denial_code is not None else "OK",
        "data": None if data is None else dict(data),
        "denial": None if denial_code is None else {"code": denial_code},
    }
    raw = json.dumps(doc, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("bounded management response size exceeded")
    return doc
