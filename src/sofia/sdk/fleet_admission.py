"""Strict, authority-free Fleet admission v1 request contract.

These bytes carry routing and requested admission intent only. The Platform
service must independently verify installation provenance, the active
owner-established autonomy policy, current revocation and exact endpoint
binding before any Fleet trust mutation. This module never authenticates a
candidate or grants trust.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Mapping

FLEET_ADMISSION_SCHEMA = "aegis.platform.fleet.admission.v1"
FLEET_ADMISSION_PROTOCOL = "1.0"
FLEET_ADMISSION_MAX_INITIAL_PERMISSION = 3
_MAX_BYTES = 64 * 1024
_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_OPERATIONS = frozenset({
    "fleet.admission.evaluate", "fleet.admission.enroll",
})
_ROLES = frozenset({"core_host", "core_link", "module_host", "standby"})
_FIELDS = frozenset({
    "schema", "protocol", "request_id", "target_platform_id",
    "expected_generation", "operation", "candidate_host_id",
    "candidate_node_id", "candidate_public_key_sha256",
    "installation_identity_id", "signer_key_id", "policy_id",
    "policy_revision", "requested_role", "initial_permission_level",
    "created_at", "deadline",
})


def _pairs_unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate Fleet admission field")
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
class UntrustedFleetAdmissionRequest:
    """Valid syntax, but NOT authenticated and NOT authorization."""

    schema: str
    protocol: str
    request_id: str
    target_platform_id: str
    expected_generation: int
    operation: str
    candidate_host_id: str
    candidate_node_id: str
    candidate_public_key_sha256: str
    installation_identity_id: str
    signer_key_id: str
    policy_id: str
    policy_revision: int
    requested_role: str
    initial_permission_level: int
    created_at: str
    deadline: str

    @classmethod
    def from_payload(
        cls, payload: object, *, now: datetime,
    ) -> "UntrustedFleetAdmissionRequest":
        if not isinstance(payload, Mapping) or set(payload) != _FIELDS:
            raise ValueError("unreviewed Fleet admission fields")
        if (
            payload["schema"] != FLEET_ADMISSION_SCHEMA
            or payload["protocol"] != FLEET_ADMISSION_PROTOCOL
        ):
            raise ValueError("unsupported Fleet admission protocol")
        for field in (
            "request_id", "target_platform_id", "candidate_host_id",
            "installation_identity_id", "signer_key_id", "policy_id",
        ):
            value = payload[field]
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"invalid {field}")
        if (
            not isinstance(payload["candidate_node_id"], str)
            or _UUID.fullmatch(payload["candidate_node_id"]) is None
            or not isinstance(payload["candidate_public_key_sha256"], str)
            or _DIGEST.fullmatch(payload["candidate_public_key_sha256"]) is None
        ):
            raise ValueError("invalid candidate identity evidence")
        if not isinstance(payload["operation"], str) or payload["operation"] not in _OPERATIONS:
            raise PermissionError("only reviewed automatic admission operations are allowed")
        if not isinstance(payload["requested_role"], str) or payload["requested_role"] not in _ROLES:
            raise PermissionError("requested role is not eligible for automatic admission")
        for field in ("expected_generation", "policy_revision"):
            value = payload[field]
            if type(value) is not int or not 1 <= value <= (2**53 - 1):
                raise ValueError(f"{field} is out of range")
        level = payload["initial_permission_level"]
        if type(level) is not int or not 1 <= level <= FLEET_ADMISSION_MAX_INITIAL_PERMISSION:
            raise PermissionError("automatic admission cannot assign protected authority")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("authoritative current time must be aware")
        moment = now.astimezone(timezone.utc)
        created = _time(payload["created_at"], "created_at")
        deadline = _time(payload["deadline"], "deadline")
        if (
            created > moment or created < moment - timedelta(seconds=60)
            or deadline <= moment or deadline <= created
            or deadline > created + timedelta(seconds=60)
        ):
            raise PermissionError("Fleet admission request outside bounded window")
        return cls(**dict(payload))

    @classmethod
    def parse(
        cls, raw: bytes, *, now: datetime,
    ) -> "UntrustedFleetAdmissionRequest":
        if not isinstance(raw, bytes) or not raw or len(raw) > _MAX_BYTES:
            raise ValueError("Fleet admission request is not bounded bytes")
        try:
            document = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_pairs_unique,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError("non-finite JSON value")
                ),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
            raise ValueError("malformed Fleet admission JSON") from error
        return cls.from_payload(document, now=now)

    def to_payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in (
            "schema", "protocol", "request_id", "target_platform_id",
            "expected_generation", "operation", "candidate_host_id",
            "candidate_node_id", "candidate_public_key_sha256",
            "installation_identity_id", "signer_key_id", "policy_id",
            "policy_revision", "requested_role", "initial_permission_level",
            "created_at", "deadline",
        )}
