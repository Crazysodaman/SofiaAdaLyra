"""Strict, authority-free Platform management mutation v1 wire contract.

These bytes carry routing and mutation intent ONLY. Authentication, current
SAFE owner approval, STOP, generation/revision fencing and idempotency belong
to the running Platform service. Never accept a request object, payload,
operation scope or approval ID as execution authority.

The response schema is deliberately separate from the read-only v1 response:
a mutation can be *unknown* after handler execution, so an authenticated
correlation cannot imply that an effect did or did not occur.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import re
import unicodedata
from typing import Mapping

MANAGEMENT_MUTATION_SCHEMA = "aegis.platform.management_mutation.v1"
MANAGEMENT_MUTATION_PROTOCOL = "1.0"
MANAGEMENT_MUTATION_RESPONSE_SCHEMA = (
    "aegis.platform.management_mutation-response.v1"
)
MAX_MUTATION_REQUEST_BYTES = 32 * 1024
MAX_MUTATION_RESPONSE_BYTES = 32 * 1024
MAX_PAYLOAD_BYTES = 16 * 1024

MUTATION_OUTCOMES = frozenset({
    "SUCCEEDED", "DENIED", "FAILED", "OUTCOME_UNKNOWN",
})
MUTATION_ERROR_CODES = frozenset({
    "UNKNOWN_OPERATION",
    "SCOPE_NOT_PERMITTED",
    "TARGET_MISMATCH",
    "STALE_GENERATION",
    "STALE_REVISION",
    "STOPPED",
    "NOT_PERMITTED",
    "APPROVAL_MISSING",
    "APPROVAL_EXPIRED",
    "APPROVAL_REVOKED",
    "APPROVAL_MISMATCH",
    "APPROVAL_NOT_ACTIVE",
    "APPROVAL_UNVERIFIED",
    "APPROVAL_CONSUMED",
    "IDEMPOTENCY_MISMATCH",
    "INVALID_PAYLOAD",
    "HANDLER_FAILED",
    "HANDLER_FAILED_UNKNOWN",
    "AUTHORITY_CHANGED",
    "AUTHORITY_REVOKED",
    "STATE_CHANGED",
    "RECEIPT_UNAVAILABLE",
})

_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_FORBIDDEN = frozenset({"__proto__", "prototype", "constructor"})
_REQUEST_FIELDS = frozenset({
    "schema", "protocol_version", "request_id", "correlation_id",
    "idempotency_key", "target_platform_id", "operation",
    "operation_scope", "expected_generation", "expected_revision",
    "deadline", "approval_id", "payload",
})
_RESPONSE_FIELDS = frozenset({
    "schema", "protocol_version", "request_id", "correlation_id",
    "idempotency_key", "platform_id", "operation", "outcome", "receipt_id",
    "current_generation", "current_revision", "error_code", "detail",
    "observed_at",
})


def _pairs_unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate Platform management mutation field")
        result[key] = value
    return result


def _time(value: object, field: str) -> datetime:
    if not isinstance(value, str) or _RFC3339.fullmatch(value) is None:
        raise ValueError(f"{field} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an RFC3339 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must have a timezone")
    return parsed.astimezone(timezone.utc)


def _safe_payload(value: object, depth: int = 0) -> None:
    if depth > 4:
        raise ValueError("management mutation payload nesting exceeds limit")
    if isinstance(value, dict):
        if len(value) > 64:
            raise ValueError("management mutation payload has too many fields")
        for key, member in value.items():
            if (
                not isinstance(key, str)
                or not key
                or len(key) > 160
                or not key.isascii()
                or any(unicodedata.category(char) == "Cc" for char in key)
                or key.lower() in _FORBIDDEN
            ):
                raise ValueError("invalid management mutation payload key")
            _safe_payload(member, depth + 1)
    elif isinstance(value, list):
        if len(value) > 256:
            raise ValueError("unbounded management mutation payload list")
        for member in value:
            _safe_payload(member, depth + 1)
    elif isinstance(value, str):
        if len(value) > 4096 or any(
            unicodedata.category(char) in {"Cc", "Cs"} for char in value
        ):
            raise ValueError("invalid management mutation payload string")
    elif type(value) is float:
        if not math.isfinite(value) or abs(value) > (2**53 - 1):
            raise ValueError("nonportable management mutation number")
    elif type(value) is int:
        if abs(value) > (2**53 - 1):
            raise ValueError("nonportable management mutation integer")
    elif value is None or type(value) is bool:
        return
    else:
        raise ValueError("unsupported management mutation payload projection")


def _safe_detail(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("invalid management mutation detail")
    if any(unicodedata.category(char) in {"Cc", "Cs"} for char in value):
        raise ValueError("control or surrogate characters in mutation detail")
    return value


def _both_int(value: object, *, minimum: int, field: str) -> int:
    if type(value) is not int or not minimum <= value <= (2**53 - 1):
        raise ValueError(f"{field} is outside the portable integer range")
    return value


@dataclass(frozen=True, slots=True)
class UntrustedManagementMutation:
    """Valid syntax, but NOT authenticated, authorized, fresh or idempotent."""

    schema: str
    protocol_version: str
    request_id: str
    correlation_id: str
    idempotency_key: str
    target_platform_id: str
    operation: str
    operation_scope: str
    expected_generation: int
    expected_revision: int
    deadline: str
    approval_id: str
    payload: Mapping[str, object]

    @classmethod
    def from_payload(
        cls, payload: object, *, now: datetime,
    ) -> "UntrustedManagementMutation":
        if not isinstance(payload, Mapping) or set(payload) != _REQUEST_FIELDS:
            raise ValueError("unreviewed Platform management mutation fields")
        if (
            payload["schema"] != MANAGEMENT_MUTATION_SCHEMA
            or payload["protocol_version"] != MANAGEMENT_MUTATION_PROTOCOL
        ):
            raise ValueError("unsupported Platform management mutation protocol")
        for field in (
            "request_id", "correlation_id", "idempotency_key",
            "target_platform_id", "operation", "operation_scope", "approval_id",
        ):
            value = payload[field]
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"invalid {field}")
        _both_int(
            payload["expected_generation"], minimum=1,
            field="expected_generation",
        )
        _both_int(
            payload["expected_revision"], minimum=0,
            field="expected_revision",
        )
        body = payload["payload"]
        if not isinstance(body, Mapping):
            raise ValueError("management mutation payload must be an object")
        _safe_payload(dict(body))
        if len(json.dumps(
            dict(body), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValueError("management mutation payload exceeds bound")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("authoritative current time must be aware")
        moment = now.astimezone(timezone.utc)
        deadline = _time(payload["deadline"], "deadline")
        if (
            deadline <= moment
            or deadline > moment + timedelta(seconds=60)
        ):
            raise PermissionError(
                "Platform management mutation outside bounded execution window"
            )
        return cls(
            schema=payload["schema"],
            protocol_version=payload["protocol_version"],
            request_id=payload["request_id"],
            correlation_id=payload["correlation_id"],
            idempotency_key=payload["idempotency_key"],
            target_platform_id=payload["target_platform_id"],
            operation=payload["operation"],
            operation_scope=payload["operation_scope"],
            expected_generation=payload["expected_generation"],
            expected_revision=payload["expected_revision"],
            deadline=payload["deadline"],
            approval_id=payload["approval_id"],
            payload=dict(body),
        )

    @classmethod
    def parse(cls, raw: bytes, *, now: datetime) -> "UntrustedManagementMutation":
        if (
            not isinstance(raw, bytes)
            or not raw
            or len(raw) > MAX_MUTATION_REQUEST_BYTES
        ):
            raise ValueError(
                "Platform management mutation request is not bounded bytes"
            )
        try:
            document = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_pairs_unique,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError("non-finite JSON value")
                ),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
            raise ValueError("malformed Platform management mutation JSON") from error
        return cls.from_payload(document, now=now)

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "protocol_version": self.protocol_version,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "target_platform_id": self.target_platform_id,
            "operation": self.operation,
            "operation_scope": self.operation_scope,
            "expected_generation": self.expected_generation,
            "expected_revision": self.expected_revision,
            "deadline": self.deadline,
            "approval_id": self.approval_id,
            "payload": dict(self.payload),
        }


def mutation_fingerprint(
    request: UntrustedManagementMutation, authenticated_peer: str,
) -> str:
    """Bind the semantic request and kernel-verified peer for idempotency.

    Volatile transport fields (request_id, correlation_id, deadline) and the
    one-use approval_id are intentionally excluded so an honest retry with the
    same idempotency key is distinguishable from a different effect request.
    """
    if not isinstance(request, UntrustedManagementMutation):
        raise TypeError("typed management mutation request required")
    if not isinstance(authenticated_peer, str) or not authenticated_peer:
        raise ValueError("authenticated peer required")
    document = mutation_approval_parameters(request, authenticated_peer)
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def mutation_approval_parameters(
    request: UntrustedManagementMutation, authenticated_peer: str,
) -> dict[str, object]:
    """Exact SAFE execution-approval parameters for one mutation request."""
    if not isinstance(request, UntrustedManagementMutation):
        raise TypeError("typed management mutation request required")
    if not isinstance(authenticated_peer, str) or not authenticated_peer:
        raise ValueError("authenticated peer required")
    payload_document = json.dumps(
        dict(request.payload), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return {
        "peer": authenticated_peer,
        "operation": request.operation,
        "operation_scope": request.operation_scope,
        "target_platform_id": request.target_platform_id,
        "expected_generation": request.expected_generation,
        "expected_revision": request.expected_revision,
        "payload_sha256": sha256(payload_document).hexdigest(),
    }


@dataclass(frozen=True, slots=True)
class UntrustedManagementMutationResponse:
    """A syntax-checked mutation receipt, NEVER an authority or effect proof."""

    request_id: str
    correlation_id: str
    idempotency_key: str
    platform_id: str
    operation: str
    outcome: str
    receipt_id: str
    current_generation: int
    current_revision: int
    error_code: str | None
    detail: str | None
    observed_at: str

    @classmethod
    def parse(
        cls,
        raw: bytes,
        *,
        expected: UntrustedManagementMutation,
        now: datetime,
    ) -> "UntrustedManagementMutationResponse":
        if (
            type(raw) is not bytes
            or not raw
            or len(raw) > MAX_MUTATION_RESPONSE_BYTES
        ):
            raise ValueError("bounded management mutation response required")
        if not isinstance(expected, UntrustedManagementMutation):
            raise TypeError("expected typed management mutation request required")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("aware receiver time required")
        try:
            doc = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_pairs_unique,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError("nonfinite management mutation response")
                ),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("invalid management mutation response JSON") from exc
        if not isinstance(doc, dict) or set(doc) != _RESPONSE_FIELDS:
            raise ValueError("unknown or missing management mutation response fields")
        if (
            doc["schema"] != MANAGEMENT_MUTATION_RESPONSE_SCHEMA
            or doc["protocol_version"] != MANAGEMENT_MUTATION_PROTOCOL
            or doc["request_id"] != expected.request_id
            or doc["correlation_id"] != expected.correlation_id
            or doc["idempotency_key"] != expected.idempotency_key
            or doc["platform_id"] != expected.target_platform_id
            or doc["operation"] != expected.operation
        ):
            raise PermissionError("uncorrelated management mutation response")
        _both_int(
            doc["current_generation"], minimum=1,
            field="current_generation",
        )
        _both_int(
            doc["current_revision"], minimum=0,
            field="current_revision",
        )
        outcome = doc["outcome"]
        if outcome not in MUTATION_OUTCOMES:
            raise ValueError("unknown management mutation outcome")
        receipt_id = doc["receipt_id"]
        if not isinstance(receipt_id, str) or _ID.fullmatch(receipt_id) is None:
            raise ValueError("invalid management mutation receipt identity")
        error_code = doc["error_code"]
        if error_code is not None and (
            not isinstance(error_code, str)
            or _ERROR_CODE.fullmatch(error_code) is None
            or error_code not in MUTATION_ERROR_CODES
        ):
            raise ValueError("unreviewed management mutation error code")
        detail = _safe_detail(doc["detail"])
        if outcome == "SUCCEEDED":
            if error_code is not None:
                raise ValueError("successful mutation may not carry an error code")
        elif error_code is None:
            raise ValueError("non-successful mutation requires an error code")
        observed = _time(doc["observed_at"], "observed_at")
        moment = now.astimezone(timezone.utc)
        if observed > moment or moment - observed > timedelta(seconds=5):
            raise PermissionError(
                "stale or future management mutation observation"
            )
        return cls(
            request_id=doc["request_id"],
            correlation_id=doc["correlation_id"],
            idempotency_key=doc["idempotency_key"],
            platform_id=doc["platform_id"],
            operation=doc["operation"],
            outcome=outcome,
            receipt_id=receipt_id,
            current_generation=doc["current_generation"],
            current_revision=doc["current_revision"],
            error_code=error_code,
            detail=detail,
            observed_at=doc["observed_at"],
        )


def make_mutation_response(
    request: UntrustedManagementMutation,
    *,
    outcome: str,
    receipt_id: str,
    current_generation: int,
    current_revision: int,
    observed_at: datetime,
    error_code: str | None = None,
    detail: str | None = None,
) -> dict[str, object]:
    """Server wire builder. Caller MUST already have checked current authority."""
    if not isinstance(request, UntrustedManagementMutation):
        raise TypeError("typed management mutation request required")
    if outcome not in MUTATION_OUTCOMES:
        raise ValueError("unreviewed management mutation outcome")
    if not isinstance(receipt_id, str) or _ID.fullmatch(receipt_id) is None:
        raise ValueError("invalid management mutation receipt identity")
    if (
        not isinstance(observed_at, datetime)
        or observed_at.utcoffset() is None
    ):
        raise ValueError("aware service observation time required")
    _both_int(current_generation, minimum=1, field="current_generation")
    _both_int(current_revision, minimum=0, field="current_revision")
    if outcome == "SUCCEEDED":
        if error_code is not None:
            raise ValueError("successful mutation may not carry an error code")
    elif (
        not isinstance(error_code, str)
        or _ERROR_CODE.fullmatch(error_code) is None
        or error_code not in MUTATION_ERROR_CODES
    ):
        raise ValueError("reviewed management mutation error code required")
    safe_detail = _safe_detail(detail)
    doc: dict[str, object] = {
        "schema": MANAGEMENT_MUTATION_RESPONSE_SCHEMA,
        "protocol_version": MANAGEMENT_MUTATION_PROTOCOL,
        "request_id": request.request_id,
        "correlation_id": request.correlation_id,
        "idempotency_key": request.idempotency_key,
        "platform_id": request.target_platform_id,
        "operation": request.operation,
        "outcome": outcome,
        "receipt_id": receipt_id,
        "current_generation": current_generation,
        "current_revision": current_revision,
        "error_code": error_code,
        "detail": safe_detail,
        "observed_at": observed_at.astimezone(timezone.utc).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z"),
    }
    encoded = json.dumps(
        doc, ensure_ascii=False, allow_nan=False, separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > MAX_MUTATION_RESPONSE_BYTES:
        raise ValueError("bounded management mutation response size exceeded")
    return doc
