"""Authority-free Core Link wire contracts.

These contracts carry routing and idempotency data only.  The host derives the
principal, audience and effective scopes from the authenticated client
certificate; caller-supplied JSON can never mint that authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import re
from typing import Mapping

from .contracts import ProtocolVersion, SDK_PROTOCOL_VERSION


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_OPERATIONS = frozenset({
    "status", "conversation.create", "conversation.select",
    "conversation.send", "conversation.history", "conversation.result",
    "conversation.cancel",
})
_MAX_PAYLOAD_BYTES = 64 * 1024


def _utc(value: datetime, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _payload(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("Core Link payload must be an object")
    document = dict(value)
    try:
        raw = json.dumps(
            document, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise ValueError("Core Link payload must be finite JSON") from exc
    if len(raw) > _MAX_PAYLOAD_BYTES:
        raise ValueError("Core Link payload exceeds 64 KiB")
    return document


class CoreLinkResponseStatus(str, Enum):
    COMPLETED = "completed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    DENIED = "denied"
    CONFLICT = "conflict"
    OUTCOME_UNKNOWN = "outcome_unknown"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CoreLinkRequest:
    request_id: str
    idempotency_key: str
    local_platform_id: str
    remote_platform_id: str
    remote_core_identity_id: str
    remote_core_generation: int
    operation: str
    payload: dict[str, object]
    created_at: datetime
    deadline: datetime
    protocol: ProtocolVersion = SDK_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        for label in (
            "request_id", "idempotency_key", "local_platform_id",
            "remote_platform_id", "remote_core_identity_id",
        ):
            _identifier(getattr(self, label), label)
        if type(self.remote_core_generation) is not int or self.remote_core_generation < 1:
            raise ValueError("remote_core_generation must be positive")
        if self.operation not in _OPERATIONS:
            raise ValueError("unsupported Core Link operation")
        object.__setattr__(self, "payload", _payload(self.payload))
        created = _utc(self.created_at, "created_at")
        deadline = _utc(self.deadline, "deadline")
        if deadline <= created:
            raise ValueError("Core Link deadline must follow creation")
        if (deadline - created).total_seconds() > 300:
            raise ValueError("Core Link request lifetime exceeds five minutes")
        if not isinstance(self.protocol, ProtocolVersion):
            raise TypeError("protocol must be ProtocolVersion")

    def require_current(self, now: datetime) -> None:
        moment = _utc(now, "now")
        if moment < _utc(self.created_at, "created_at"):
            raise PermissionError("Core Link request is not active yet")
        if moment >= _utc(self.deadline, "deadline"):
            raise PermissionError("Core Link request expired")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "companion.platform.core_link_request.v1",
            "protocol": str(self.protocol),
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "local_platform_id": self.local_platform_id,
            "remote_platform_id": self.remote_platform_id,
            "remote_core_identity_id": self.remote_core_identity_id,
            "remote_core_generation": self.remote_core_generation,
            "operation": self.operation,
            "payload": self.payload,
            "created_at": _utc(self.created_at, "created_at").isoformat(),
            "deadline": _utc(self.deadline, "deadline").isoformat(),
        }

    @classmethod
    def from_payload(cls, value: object) -> "CoreLinkRequest":
        keys = {
            "schema", "protocol", "request_id", "idempotency_key",
            "local_platform_id", "remote_platform_id",
            "remote_core_identity_id", "remote_core_generation", "operation",
            "payload", "created_at", "deadline",
        }
        if not isinstance(value, Mapping) or set(value) != keys:
            raise ValueError("Core Link request has unreviewed fields")
        if value["schema"] != "companion.platform.core_link_request.v1":
            raise ValueError("unsupported Core Link request schema")
        try:
            return cls(
                request_id=value["request_id"],  # type: ignore[arg-type]
                idempotency_key=value["idempotency_key"],  # type: ignore[arg-type]
                local_platform_id=value["local_platform_id"],  # type: ignore[arg-type]
                remote_platform_id=value["remote_platform_id"],  # type: ignore[arg-type]
                remote_core_identity_id=value["remote_core_identity_id"],  # type: ignore[arg-type]
                remote_core_generation=value["remote_core_generation"],  # type: ignore[arg-type]
                operation=value["operation"],  # type: ignore[arg-type]
                payload=_payload(value["payload"]),
                created_at=datetime.fromisoformat(value["created_at"]),  # type: ignore[arg-type]
                deadline=datetime.fromisoformat(value["deadline"]),  # type: ignore[arg-type]
                protocol=ProtocolVersion.parse(value["protocol"]),  # type: ignore[arg-type]
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Core Link request is invalid") from exc


@dataclass(frozen=True, slots=True)
class CoreLinkResponse:
    request_id: str
    status: CoreLinkResponseStatus
    payload: dict[str, object]
    server_at: datetime
    protocol: ProtocolVersion = SDK_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        _identifier(self.request_id, "request_id")
        if not isinstance(self.status, CoreLinkResponseStatus):
            raise TypeError("status must be CoreLinkResponseStatus")
        object.__setattr__(self, "payload", _payload(self.payload))
        _utc(self.server_at, "server_at")
        if not isinstance(self.protocol, ProtocolVersion):
            raise TypeError("protocol must be ProtocolVersion")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "companion.platform.core_link_response.v1",
            "protocol": str(self.protocol),
            "request_id": self.request_id,
            "status": self.status.value,
            "payload": self.payload,
            "server_at": _utc(self.server_at, "server_at").isoformat(),
        }

    @classmethod
    def from_payload(cls, value: object) -> "CoreLinkResponse":
        keys = {"schema", "protocol", "request_id", "status", "payload", "server_at"}
        if not isinstance(value, Mapping) or set(value) != keys:
            raise ValueError("Core Link response has unreviewed fields")
        if value["schema"] != "companion.platform.core_link_response.v1":
            raise ValueError("unsupported Core Link response schema")
        try:
            return cls(
                request_id=value["request_id"],  # type: ignore[arg-type]
                status=CoreLinkResponseStatus(value["status"]),
                payload=_payload(value["payload"]),
                server_at=datetime.fromisoformat(value["server_at"]),  # type: ignore[arg-type]
                protocol=ProtocolVersion.parse(value["protocol"]),  # type: ignore[arg-type]
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Core Link response is invalid") from exc
