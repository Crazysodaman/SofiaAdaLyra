"""Strict untrusted management reply, not a credential or transport proof."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Mapping

from sofia.sdk.platform_management import UntrustedManagementRead

REPLY_SCHEMA = "aegis.platform.management.response.v1"
_MAX_REPLY = 32 * 1024
_REPLY_FIELDS = frozenset({
    "schema", "request_id", "platform_id", "generation",
    "observed_at", "operation", "payload",
})


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate management response key")
        out[key] = value
    return out


def _deny_sensitive_payload(value: object, depth: int = 0) -> None:
    if depth > 8:
        raise ValueError("unbounded management payload nesting")
    if isinstance(value, dict):
        for key, member in value.items():
            if not isinstance(key, str):
                raise ValueError("non-text management payload field")
            lowered = key.lower()
            if lowered in {"__proto__", "constructor", "prototype"} or any(
                part in lowered for part in (
                    "secret", "password", "credential", "access_token",
                    "refresh_token", "private_key", "api_key",
                )
            ):
                raise ValueError("sensitive or unsafe management field")
            _deny_sensitive_payload(member, depth + 1)
    elif isinstance(value, list):
        if len(value) > 1024:
            raise ValueError("unbounded management response list")
        for member in value:
            _deny_sensitive_payload(member, depth + 1)
    elif value is None or type(value) in (str, int, float, bool):
        return
    else:
        raise ValueError("unsupported management response data")


@dataclass(frozen=True, slots=True)
class UntrustedManagementReply:
    """Parsed response bound to a request, NEVER authenticated by JSON alone."""

    request_id: str
    platform_id: str
    generation: int
    observed_at: str
    operation: str
    payload: Mapping[str, object]

    @classmethod
    def parse(
        cls, raw: bytes, *,
        request: UntrustedManagementRead,
        now: datetime,
    ) -> "UntrustedManagementReply":
        if not isinstance(request, UntrustedManagementRead):
            raise TypeError("matching request required")
        if type(raw) is not bytes or not raw or len(raw) > _MAX_REPLY:
            raise ValueError("bounded response bytes required")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("aware receiver clock required")
        try:
            doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                             parse_constant=lambda c: (_ for _ in ()).throw(
                                 ValueError("nonfinite management response")))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("invalid management response JSON") from exc
        if not isinstance(doc, dict) or set(doc) != _REPLY_FIELDS:
            raise ValueError("unknown or missing management response fields")
        if doc["schema"] != REPLY_SCHEMA:
            raise ValueError("unexpected management response version")
        if (doc["request_id"] != request.request_id
                or doc["platform_id"] != request.target_platform_id
                or type(doc["generation"]) is not int
                or doc["generation"] != request.expected_generation
                or doc["operation"] != request.operation):
            raise PermissionError("management response does not match request")
        stamp = doc["observed_at"]
        if not isinstance(stamp, str):
            raise ValueError("management response timestamp missing")
        try:
            observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            created = datetime.fromisoformat(request.created_at.replace("Z", "+00:00"))
            deadline = datetime.fromisoformat(request.deadline.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("management response timestamp invalid") from exc
        if observed.tzinfo is None or created.tzinfo is None or deadline.tzinfo is None:
            raise ValueError("management response timezone missing")
        if observed < created or observed >= deadline or observed > now:
            raise PermissionError("management response is stale or future-dated")
        payload = doc["payload"]
        if not isinstance(payload, dict):
            raise ValueError("management response must be a scoped object")
        _deny_sensitive_payload(payload)
        # Raw JSON decode owns the new object; no serialized claims of trust.
        return cls(
            request_id=doc["request_id"], platform_id=doc["platform_id"],
            generation=doc["generation"], observed_at=stamp,
            operation=doc["operation"], payload=payload,
        )
