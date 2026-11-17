"""Typed durable federation projections.

These values describe observed local state.  They are not bearer credentials:
possessing a ``PeerRecord`` or ``InboundMessage`` never authorizes a privileged
instruction or external effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from uuid import UUID

from sofia.platform.social.contracts import (
    Audience,
    ChatMessage,
    CoreIdentity,
    RoomId,
)
from sofia.sdk.contracts import ProtocolVersion


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


class ContactDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class PeerState(str, Enum):
    PENDING_OUTBOUND = "pending_outbound"
    PENDING_INBOUND = "pending_inbound"
    ACTIVE = "active"
    DENIED = "denied"
    BLOCKED = "blocked"
    REVOKED = "revoked"


class DeliveryStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT_UNCONFIRMED = "SENT_UNCONFIRMED"
    RECEIVED = "RECEIVED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    HANDLED = "HANDLED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class TransportOutcome(str, Enum):
    DELIVERED = "DELIVERED"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True, slots=True)
class PeerRecord:
    peer_id: UUID
    remote_platform_id: str
    remote_core_id: UUID
    remote_generation: int
    display_name: str
    trust_anchor: str
    state: PeerState
    outbound_allowed: bool
    inbound_allowed: bool
    revision: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.peer_id, UUID) or self.peer_id.int == 0:
            raise ValueError("peer_id must be a nonzero UUID")
        if not isinstance(self.remote_platform_id, str) or _ID.fullmatch(self.remote_platform_id) is None:
            raise ValueError("remote_platform_id must be a bounded identifier")
        if not isinstance(self.remote_core_id, UUID) or self.remote_core_id.int == 0:
            raise ValueError("remote_core_id must be a nonzero UUID")
        if type(self.remote_generation) is not int or self.remote_generation < 1:
            raise ValueError("remote_generation must be positive")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("display_name is required")
        name = self.display_name.strip()
        if len(name) > 128 or any(ord(character) < 0x20 for character in name):
            raise ValueError("display_name must be a bounded printable label")
        _digest(self.trust_anchor, "trust_anchor")
        if not isinstance(self.state, PeerState):
            raise TypeError("state must be PeerState")
        if type(self.outbound_allowed) is not bool or type(self.inbound_allowed) is not bool:
            raise TypeError("direction permissions must be booleans")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")
        created = _utc(self.created_at, "created_at")
        updated = _utc(self.updated_at, "updated_at")
        expires = _utc(self.expires_at, "expires_at")
        if updated < created:
            raise ValueError("updated_at cannot precede created_at")
        if expires <= created:
            raise ValueError("expires_at must follow peer creation")

    def remote_identity(self) -> CoreIdentity:
        return CoreIdentity(
            core_id=self.remote_core_id,
            platform_id=self.remote_platform_id,
            generation=self.remote_generation,
            display_name=self.display_name,
        )


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    message_id: UUID
    destination_platform_id: str
    destination_core_id: UUID
    room_id: RoomId
    sequence: int
    idempotency_key: str
    payload_digest: str
    status: DeliveryStatus
    attempts: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    envelope_json: str

    def __post_init__(self) -> None:
        if not isinstance(self.message_id, UUID) or self.message_id.int == 0:
            raise ValueError("message_id must be a nonzero UUID")
        if not isinstance(self.destination_platform_id, str) or _ID.fullmatch(self.destination_platform_id) is None:
            raise ValueError("destination_platform_id must be a bounded identifier")
        if type(self.attempts) is not int or self.attempts < 0:
            raise ValueError("attempts must be nonnegative")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be positive")
        if not isinstance(self.room_id, RoomId):
            raise TypeError("room_id must be RoomId")
        if not isinstance(self.status, DeliveryStatus):
            raise TypeError("status must be DeliveryStatus")
        _digest(self.payload_digest, "payload_digest")
        _utc(self.created_at, "created_at")
        _utc(self.updated_at, "updated_at")
        _utc(self.expires_at, "expires_at")


@dataclass(frozen=True, slots=True)
class InboxRecord:
    message_id: UUID
    source_platform_id: str
    source_core_id: UUID
    room_id: RoomId
    sequence: int
    status: DeliveryStatus
    payload_digest: str
    received_at: datetime
    updated_at: datetime
    envelope_json: str

    def __post_init__(self) -> None:
        if not isinstance(self.message_id, UUID) or self.message_id.int == 0:
            raise ValueError("message_id must be a nonzero UUID")
        if not isinstance(self.room_id, RoomId):
            raise TypeError("room_id must be RoomId")
        if not isinstance(self.status, DeliveryStatus):
            raise TypeError("status must be DeliveryStatus")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be positive")
        _digest(self.payload_digest, "payload_digest")
        _utc(self.received_at, "received_at")
        _utc(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class AuthenticatedPeer:
    """Transport-verified peer identity.

    Only a pinned authenticated channel may construct this value for delivery.
    An envelope's claimed sender text is never a substitute for it.
    """

    platform_id: str
    core_id: UUID
    generation: int
    trust_anchor: str
    protocol_version: ProtocolVersion

    def __post_init__(self) -> None:
        if not isinstance(self.platform_id, str) or _ID.fullmatch(self.platform_id) is None:
            raise ValueError("platform_id must be a bounded identifier")
        if not isinstance(self.core_id, UUID) or self.core_id.int == 0:
            raise ValueError("core_id must be a nonzero UUID")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be positive")
        _digest(self.trust_anchor, "trust_anchor")
        if not isinstance(self.protocol_version, ProtocolVersion):
            raise TypeError("protocol_version must be ProtocolVersion")


@dataclass(frozen=True, slots=True)
class TransportReceipt:
    outcome: TransportOutcome
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, TransportOutcome):
            raise TypeError("outcome must be TransportOutcome")
        if self.detail is not None and not isinstance(self.detail, str):
            raise TypeError("detail must be text")


@dataclass(frozen=True, slots=True)
class PeerAcknowledgment:
    """Receiver-side logical status carried over an authenticated channel.

    A transport acknowledgment is *not* proof that a Core read, agreed with,
    remembered or executed the referenced message.
    """

    message_id: UUID
    status: DeliveryStatus
    acknowledging_platform_id: str
    acknowledging_core_id: UUID
    acknowledged_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.message_id, UUID) or self.message_id.int == 0:
            raise ValueError("message_id must be a nonzero UUID")
        if not isinstance(self.status, DeliveryStatus):
            raise TypeError("status must be DeliveryStatus")
        if self.status not in {
            DeliveryStatus.ACCEPTED,
            DeliveryStatus.DECLINED,
            DeliveryStatus.DENIED,
            DeliveryStatus.EXPIRED,
            DeliveryStatus.HANDLED,
        }:
            raise ValueError("acknowledgment status must be a terminal recipient decision")
        if (
            not isinstance(self.acknowledging_platform_id, str)
            or _ID.fullmatch(self.acknowledging_platform_id) is None
        ):
            raise ValueError("acknowledging_platform_id must be a bounded identifier")
        if not isinstance(self.acknowledging_core_id, UUID) or self.acknowledging_core_id.int == 0:
            raise ValueError("acknowledging_core_id must be a nonzero UUID")
        object.__setattr__(self, "acknowledged_at", _utc(self.acknowledged_at, "acknowledged_at"))


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """Untrusted peer content presented to the local Core.

    There is no capability, grant, principal override or instruction field.
    """

    message: ChatMessage
    source_platform_id: str
    untrusted: bool
    authority_granted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.message, ChatMessage):
            raise TypeError("message must be ChatMessage")
        if not isinstance(self.source_platform_id, str):
            raise ValueError("source_platform_id must be text")
        if type(self.untrusted) is not bool:
            raise TypeError("untrusted must be a boolean")
        if self.authority_granted is not False:
            raise ValueError("inbound peer content never grants authority")


@dataclass(frozen=True, slots=True)
class AudienceProjection:
    message_id: UUID
    room_id: RoomId
    sender_core_id: UUID
    recipient_core_id: UUID
    audience: Audience
    body: str
    created_at: datetime
    sequence: int
    untrusted: bool
    authority_granted: bool = False

    def __post_init__(self) -> None:
        if self.authority_granted is not False:
            raise ValueError("audience projections never grant authority")
        if not isinstance(self.audience, Audience):
            raise TypeError("audience must be Audience")
        _utc(self.created_at, "created_at")
