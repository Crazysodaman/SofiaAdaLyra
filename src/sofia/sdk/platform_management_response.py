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
_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_SENSITIVE = (
    "secret", "password", "credential", "access_token", "refresh_token",
    "private_key", "api_key", "owner_proof", "authorization",
)
_FORBIDDEN = frozenset({"__proto__", "prototype", "constructor"})


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
                or data["core_started"] is not False
                or data["operator_stop"] is not False
            ):
                raise PermissionError("inconsistent Platform status projection")
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
