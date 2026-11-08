"""Bounded, untrusted Platform status reply wire syntax for GUI/TUI clients.

The sender's "source" string is self-asserted and cannot establish trust.
A separately authenticated OS transport must verify the live service before a
caller treats a correlated response as an observation.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping

from sofia.sdk.platform_management import UntrustedManagementRead

RESPONSE_SCHEMA = "aegis.platform.management.read-response.v1"
MAX_RESPONSE_BYTES = 65536
_OUTER = frozenset({
    "schema", "protocol", "request_id", "platform_id",
    "platform_generation", "operation", "source", "data",
})
_STATUS = frozenset({
    "platform_id", "generation", "operator_stop", "core_started",
})


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate Platform management response field")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class UntrustedManagementStatus:
    """Correlated, schema-valid status, explicitly NOT authenticated."""

    request_id: str
    platform_id: str
    generation: int
    core_started: bool
    operator_stop: bool

    @classmethod
    def parse(
        cls, raw: bytes, *, expected: UntrustedManagementRead
    ) -> "UntrustedManagementStatus":
        if (not isinstance(raw, bytes) or not raw
                or len(raw) > MAX_RESPONSE_BYTES):
            raise ValueError("management response exceeds bound")
        if not isinstance(expected, UntrustedManagementRead):
            raise TypeError("expected parsed management request required")
        if expected.operation != "platform.status":
            raise ValueError("status response requires status request")
        try:
            payload = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError("non-finite JSON value")),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
            raise ValueError("malformed Platform management response") from error
        if not isinstance(payload, Mapping) or set(payload) != _OUTER:
            raise ValueError("unreviewed management response fields")
        if (payload["schema"] != RESPONSE_SCHEMA
                or payload["protocol"] != "1.0"
                or payload["operation"] != expected.operation
                or payload["source"] != "PLATFORM_SESSION"
                or payload["request_id"] != expected.request_id
                or payload["platform_id"] != expected.target_platform_id
                or type(payload["platform_generation"]) is not int
                or payload["platform_generation"] != expected.expected_generation):
            raise ValueError("uncorrelated management response")
        data = payload["data"]
        if not isinstance(data, Mapping) or set(data) != _STATUS:
            raise ValueError("unreviewed Platform status data")
        if (data["platform_id"] != expected.target_platform_id
                or type(data["generation"]) is not int
                or data["generation"] != expected.expected_generation
                or data["core_started"] is not False
                or data["operator_stop"] is not False):
            raise ValueError("invalid or stale Platform status observation")
        return cls(
            request_id=expected.request_id,
            platform_id=expected.target_platform_id,
            generation=expected.expected_generation,
            core_started=False,
            operator_stop=False,
        )
