"""Strict, authority-free Platform management read-only v1 request contract.

These bytes carry routing and observation intent ONLY. Authentication, STOP,
current revocation and permission checks belong to the running Platform service.
Never accept a request object as execution authority or an owner grant.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Mapping

MANAGEMENT_READ_SCHEMA = "aegis.platform.management.read.v1"
MANAGEMENT_READ_PROTOCOL = "1.0"
_MAX_BYTES = 64 * 1024
_RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_READ_OPERATIONS = frozenset({
    "platform.status", "core.list", "module.list", "fleet.list",
    "settings.inspect", "security.status", "updates.status",
    "diagnostics.summary", "jobs.list",
})
_FIELDS = frozenset({
    "schema", "protocol", "request_id", "target_platform_id",
    "expected_generation", "operation", "created_at", "deadline",
})


def _pairs_unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate Platform management field")
        result[key] = value
    return result


def _time(value: object, field: str) -> datetime:
    if not isinstance(value, str) or _RFC3339.fullmatch(value) is None:
        raise ValueError(f"{field} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an RFC3339 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must have a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class UntrustedManagementRead:
    """Valid syntax, but NOT authenticated or authorized."""

    schema: str
    protocol: str
    request_id: str
    target_platform_id: str
    expected_generation: int
    operation: str
    created_at: str
    deadline: str

    @classmethod
    def from_payload(cls, payload: object, *, now: datetime) -> "UntrustedManagementRead":
        if not isinstance(payload, Mapping) or set(payload) != _FIELDS:
            raise ValueError("unreviewed Platform management fields")
        if (payload["schema"] != MANAGEMENT_READ_SCHEMA
                or payload["protocol"] != MANAGEMENT_READ_PROTOCOL):
            raise ValueError("unsupported Platform management read protocol")
        for field in ("request_id", "target_platform_id"):
            value = payload[field]
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"invalid {field}")
        if (type(payload["expected_generation"]) is not int
                or payload["expected_generation"] < 1):
            raise ValueError("expected generation must be positive")
        if not isinstance(payload["operation"], str) or payload["operation"] not in _READ_OPERATIONS:
            raise PermissionError("only reviewed read-only queries are allowed")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("authoritative current time must be aware")
        moment = now.astimezone(timezone.utc)
        created = _time(payload["created_at"], "created_at")
        deadline = _time(payload["deadline"], "deadline")
        if (created > moment or created < moment - timedelta(seconds=60)
                or deadline <= moment or deadline <= created
                or deadline > created + timedelta(seconds=60)):
            raise PermissionError("Platform management request outside bounded observation window")
        return cls(**dict(payload))

    @classmethod
    def parse(cls, raw: bytes, *, now: datetime) -> "UntrustedManagementRead":
        if not isinstance(raw, bytes) or len(raw) > _MAX_BYTES or not raw:
            raise ValueError("Platform management request is not bounded bytes")
        try:
            document = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_pairs_unique,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError("non-finite JSON value")),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
            raise ValueError("malformed Platform management JSON") from error
        return cls.from_payload(document, now=now)

    def to_payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in (
            "schema", "protocol", "request_id", "target_platform_id",
            "expected_generation", "operation", "created_at", "deadline",
        )}
