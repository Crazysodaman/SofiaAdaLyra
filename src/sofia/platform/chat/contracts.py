"""Inert, versioned contracts for the Platform multi-Core chat engine.

These types carry identity, provenance, audience and ordering metadata only.
Constructing or decoding one grants no execution authority, no membership and
no permission to read another Core's private rooms. Chat is data exchange, not
a capability or authority boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Mapping
from uuid import UUID

CHAT_CONTRACT_SCHEMA = "sofia.platform.chat.v1"
PEER_ENVELOPE_SCHEMA = "sofia.platform.chat.peer.v1"
GENERAL_ROOM_ID = "general"
MAX_CORE_IDENTITIES = 7
MAX_MESSAGE_BODY_BYTES = 64 * 1024

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _bounded_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _bounded_text(value: object, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value


def _optional_id(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _bounded_id(value, label)


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _positive_int(value: object, label: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


class RoomKind(str, Enum):
    GENERAL = "general"
    DIRECT = "direct"
    PRIVATE_GROUP = "private_group"


class RoomHistoryPolicy(str, Enum):
    """How much history a newly joining member may receive."""

    FULL_HISTORY = "full_history"
    NO_PRE_JOIN = "no_pre_join"
    EXPLICIT_GRANT = "explicit_grant"


class MembershipStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    DECLINED = "declined"
    LEFT = "left"
    REMOVED = "removed"
    BLOCKED = "blocked"
    REVOKED = "revoked"
    EXPIRED = "expired"


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ActorKind(str, Enum):
    OWNER = "owner"
    CORE = "core"


class MessageOrigin(str, Enum):
    OWNER = "owner"
    LOCAL_CORE = "local_core"
    PEER_CORE = "peer_core"


@dataclass(frozen=True, slots=True)
class CoreIdentity:
    """Stable independently issued Core identity, never a display label."""

    core_id: UUID
    platform_id: str
    generation: int
    display_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.core_id, UUID):
            raise TypeError("core_id must be UUID")
        _bounded_id(self.platform_id, "platform_id")
        _positive_int(self.generation, "generation")
        _bounded_text(self.display_name, "display_name", maximum=200)

    @property
    def core_id_text(self) -> str:
        return str(self.core_id)

    @classmethod
    def from_text(
        cls,
        core_id: str,
        *,
        platform_id: str,
        generation: int,
        display_name: str,
    ) -> CoreIdentity:
        if not isinstance(core_id, str):
            raise TypeError("core_id must be text")
        return cls(
            UUID(core_id),
            platform_id=platform_id,
            generation=generation,
            display_name=display_name,
        )


@dataclass(frozen=True, slots=True)
class ChatActor:
    """An authenticated caller projection, not a permission grant."""

    actor_id: str
    kind: ActorKind
    identity: CoreIdentity | None = None

    def __post_init__(self) -> None:
        _bounded_id(self.actor_id, "actor_id")
        if not isinstance(self.kind, ActorKind):
            raise TypeError("kind must be an ActorKind")
        if self.kind is ActorKind.CORE:
            if not isinstance(self.identity, CoreIdentity):
                raise TypeError("core actor requires a CoreIdentity")
            if self.identity.core_id_text != self.actor_id:
                raise ValueError("core actor_id must equal the Core identity UUID")
        elif self.identity is not None:
            raise ValueError("owner actor cannot carry a CoreIdentity")

    @classmethod
    def owner(cls, owner_id: str) -> ChatActor:
        return cls(owner_id, ActorKind.OWNER)

    @classmethod
    def core(cls, identity: CoreIdentity) -> ChatActor:
        if not isinstance(identity, CoreIdentity):
            raise TypeError("identity must be a CoreIdentity")
        return cls(identity.core_id_text, ActorKind.CORE, identity)


@dataclass(frozen=True, slots=True)
class RoomMembership:
    """One member's explicit membership and bounded history epoch."""

    room_id: str
    core_id: str
    epoch: int
    status: MembershipStatus
    joined_at: datetime | None
    history_from_sequence: int | None
    member_kind: ActorKind = ActorKind.CORE
    invited_by: str | None = None
    removed_by: str | None = None
    left_at: datetime | None = None

    def __post_init__(self) -> None:
        _bounded_id(self.room_id, "room_id")
        _bounded_id(self.core_id, "core_id")
        _positive_int(self.epoch, "epoch")
        if not isinstance(self.status, MembershipStatus):
            raise TypeError("status must be a MembershipStatus")
        if not isinstance(self.member_kind, ActorKind):
            raise TypeError("member_kind must be an ActorKind")
        if self.joined_at is not None:
            _aware(self.joined_at, "joined_at")
        if self.left_at is not None:
            _aware(self.left_at, "left_at")
        if self.history_from_sequence is not None:
            _positive_int(self.history_from_sequence, "history_from_sequence")
        if self.status is MembershipStatus.ACTIVE:
            if self.joined_at is None:
                raise ValueError("active membership requires joined_at")
            if self.history_from_sequence is None:
                raise ValueError("active membership requires a history floor")
        _optional_id(self.invited_by, "invited_by")
        _optional_id(self.removed_by, "removed_by")

    @property
    def is_active(self) -> bool:
        return self.status is MembershipStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class RoomInvitation:
    invite_id: str
    room_id: str
    invitee_id: str
    invited_by: str
    status: InvitationStatus
    created_at: datetime
    expires_at: datetime | None
    history_from_sequence: int | None
    epoch: int

    def __post_init__(self) -> None:
        for label, value in (
            ("invite_id", self.invite_id),
            ("room_id", self.room_id),
            ("invitee_id", self.invitee_id),
            ("invited_by", self.invited_by),
        ):
            _bounded_id(value, label)
        if not isinstance(self.status, InvitationStatus):
            raise TypeError("status must be an InvitationStatus")
        _aware(self.created_at, "created_at")
        if self.expires_at is not None:
            _aware(self.expires_at, "expires_at")
        if self.history_from_sequence is not None:
            _positive_int(self.history_from_sequence, "history_from_sequence")
        _positive_int(self.epoch, "epoch")


@dataclass(frozen=True, slots=True)
class Room:
    """Durable room metadata, including creation record and membership epoch."""

    room_id: str
    kind: RoomKind
    name: str
    topic: str
    created_at: datetime
    created_by: str
    owner_core_id: str | None
    membership_epoch: int
    history_policy: RoomHistoryPolicy
    retention_seconds: int | None
    sequence: int

    def __post_init__(self) -> None:
        _bounded_id(self.room_id, "room_id")
        if not isinstance(self.kind, RoomKind):
            raise TypeError("kind must be a RoomKind")
        _bounded_text(self.name, "name", maximum=200)
        if not isinstance(self.topic, str) or len(self.topic) > 2000:
            raise ValueError("topic must be bounded text")
        _aware(self.created_at, "created_at")
        _bounded_id(self.created_by, "created_by")
        _optional_id(self.owner_core_id, "owner_core_id")
        _positive_int(self.membership_epoch, "membership_epoch")
        if not isinstance(self.history_policy, RoomHistoryPolicy):
            raise TypeError("history_policy must be a RoomHistoryPolicy")
        if self.retention_seconds is not None:
            _positive_int(self.retention_seconds, "retention_seconds")
        _positive_int(self.sequence, "sequence", minimum=0)

    @property
    def is_general(self) -> bool:
        return self.kind is RoomKind.GENERAL


@dataclass(frozen=True, slots=True)
class ChatAudience:
    """Exact active-room membership snapshot for one message."""

    room_id: str
    kind: RoomKind
    membership_epoch: int
    member_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _bounded_id(self.room_id, "room_id")
        if not isinstance(self.kind, RoomKind):
            raise TypeError("kind must be a RoomKind")
        _positive_int(self.membership_epoch, "membership_epoch")
        if not isinstance(self.member_ids, tuple) or not self.member_ids:
            raise ValueError("audience must contain at least one member")
        if len(set(self.member_ids)) != len(self.member_ids):
            raise ValueError("audience members must be unique")
        for member_id in self.member_ids:
            _bounded_id(member_id, "audience member")


@dataclass(frozen=True, slots=True)
class MessageProvenance:
    """Where a message came from and whether its text is trusted data."""

    source_platform_id: str
    source_generation: int | None
    transport_verified: bool
    untrusted_content: bool
    received_at: datetime
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        _bounded_id(self.source_platform_id, "source_platform_id")
        if self.source_generation is not None:
            _positive_int(self.source_generation, "source_generation")
        if type(self.transport_verified) is not bool:
            raise TypeError("transport_verified must be bool")
        if type(self.untrusted_content) is not bool:
            raise TypeError("untrusted_content must be bool")
        _aware(self.received_at, "received_at")
        _optional_id(self.idempotency_key, "idempotency_key")


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One immutable stored message projection."""

    message_id: str
    room_id: str
    sender_core_id: str
    audience: ChatAudience
    body: str
    created_at: datetime
    reply_to: str | None
    origin: MessageOrigin
    sequence: int
    provenance: MessageProvenance
    edited_at: datetime | None = None
    revision: int = 0
    deleted_at: datetime | None = None
    deleted_by: str | None = None

    def __post_init__(self) -> None:
        _bounded_id(self.message_id, "message_id")
        _bounded_id(self.room_id, "room_id")
        _bounded_id(self.sender_core_id, "sender_core_id")
        if not isinstance(self.audience, ChatAudience):
            raise TypeError("audience must be a ChatAudience")
        if self.audience.room_id != self.room_id:
            raise ValueError("audience room_id must match message room_id")
        if not isinstance(self.body, str):
            raise TypeError("body must be text")
        if len(self.body.encode("utf-8")) > MAX_MESSAGE_BODY_BYTES:
            raise ValueError("message body exceeds the bounded maximum")
        _aware(self.created_at, "created_at")
        _optional_id(self.reply_to, "reply_to")
        if not isinstance(self.origin, MessageOrigin):
            raise TypeError("origin must be a MessageOrigin")
        _positive_int(self.sequence, "sequence")
        if not isinstance(self.provenance, MessageProvenance):
            raise TypeError("provenance must be MessageProvenance")
        if self.edited_at is not None:
            _aware(self.edited_at, "edited_at")
        _positive_int(self.revision, "revision", minimum=0)
        if self.deleted_at is not None:
            _aware(self.deleted_at, "deleted_at")
            if self.deleted_by is None:
                raise ValueError("tombstone requires deleted_by")
            if self.body != "":
                raise ValueError("tombstone body must be empty")
        elif self.deleted_by is not None:
            raise ValueError("deleted_by requires a tombstone")

    @property
    def is_tombstone(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_untrusted(self) -> bool:
        return self.provenance.untrusted_content

    def as_untrusted_data(self) -> dict[str, object]:
        """Project peer text for a consumer that must never see instructions."""
        return {
            "schema": CHAT_CONTRACT_SCHEMA,
            "message_id": self.message_id,
            "room_id": self.room_id,
            "sender_core_id": self.sender_core_id,
            "body": self.body,
            "trust": "UNTRUSTED_DATA",
            "is_instruction": False,
            "grants_authority": False,
        }


@dataclass(frozen=True, slots=True)
class Draft:
    actor_id: str
    room_id: str
    body: str
    reply_to: str | None
    updated_at: datetime

    def __post_init__(self) -> None:
        _bounded_id(self.actor_id, "actor_id")
        _bounded_id(self.room_id, "room_id")
        if not isinstance(self.body, str):
            raise TypeError("body must be text")
        if len(self.body.encode("utf-8")) > MAX_MESSAGE_BODY_BYTES:
            raise ValueError("draft body exceeds the bounded maximum")
        _optional_id(self.reply_to, "reply_to")
        _aware(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True)
class MessagePage:
    room_id: str
    messages: tuple[ChatMessage, ...]
    next_cursor: int | None
    has_more: bool
    membership_epoch: int
    history_from_sequence: int

    def __post_init__(self) -> None:
        _bounded_id(self.room_id, "room_id")
        if not isinstance(self.messages, tuple):
            raise TypeError("messages must be a tuple")
        if self.next_cursor is not None:
            _positive_int(self.next_cursor, "next_cursor")
        _positive_int(self.membership_epoch, "membership_epoch")
        _positive_int(self.history_from_sequence, "history_from_sequence")


@dataclass(frozen=True, slots=True)
class RoomSync:
    room_id: str
    messages: tuple[ChatMessage, ...]
    next_cursor: int
    has_more: bool


@dataclass(frozen=True, slots=True)
class SyncResult:
    actor_id: str
    rooms: tuple[RoomSync, ...]

    def __post_init__(self) -> None:
        _bounded_id(self.actor_id, "actor_id")
        if not isinstance(self.rooms, tuple):
            raise TypeError("rooms must be a tuple")


@dataclass(frozen=True, slots=True)
class ChatAuditEvent:
    sequence: int
    event_id: str
    occurred_at: datetime
    actor_id: str
    event_type: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        _positive_int(self.sequence, "sequence", minimum=0)


@dataclass(frozen=True, slots=True)
class OutboxEntry:
    outbox_id: str
    message_id: str
    room_id: str
    destination_core_id: str
    destination_platform_id: str
    status: str
    created_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("outbox_id", self.outbox_id),
            ("message_id", self.message_id),
            ("room_id", self.room_id),
            ("destination_core_id", self.destination_core_id),
            ("destination_platform_id", self.destination_platform_id),
            ("status", self.status),
        ):
            _bounded_id(value, label)
        _aware(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class RetentionResult:
    deleted_messages: int
    expired_invitations: int

    def __post_init__(self) -> None:
        _positive_int(self.deleted_messages, "deleted_messages", minimum=0)
        _positive_int(self.expired_invitations, "expired_invitations", minimum=0)


@dataclass(frozen=True, slots=True)
class PeerEnvelope:
    """Strict peer payload. Audience is always recomputed by the receiver."""

    message_id: str
    source_core_id: str
    source_platform_id: str
    source_generation: int
    room_id: str
    body: str
    created_at: datetime
    reply_to: str | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("message_id", self.message_id),
            ("source_core_id", self.source_core_id),
            ("source_platform_id", self.source_platform_id),
            ("room_id", self.room_id),
        ):
            _bounded_id(value, label)
        _positive_int(self.source_generation, "source_generation")
        if not isinstance(self.body, str) or not self.body.strip():
            raise ValueError("body must be nonempty text")
        if len(self.body.encode("utf-8")) > MAX_MESSAGE_BODY_BYTES:
            raise ValueError("message body exceeds the bounded maximum")
        _aware(self.created_at, "created_at")
        _optional_id(self.reply_to, "reply_to")
        _optional_id(self.idempotency_key, "idempotency_key")

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> PeerEnvelope:
        if not isinstance(payload, Mapping):
            raise TypeError("peer payload must be a mapping")
        allowed = {
            "schema",
            "message_id",
            "source_core_id",
            "source_platform_id",
            "source_generation",
            "room_id",
            "body",
            "created_at",
            "reply_to",
            "idempotency_key",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(
                "peer payload contains unsupported fields: "
                + ", ".join(sorted(str(key) for key in unknown))
            )
        if payload.get("schema") != PEER_ENVELOPE_SCHEMA:
            raise ValueError("unsupported peer envelope schema")
        required = allowed - {"reply_to", "idempotency_key"}
        missing = required - set(payload)
        if missing:
            raise ValueError(
                "peer payload is missing fields: "
                + ", ".join(sorted(missing))
            )
        created_at = payload["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            message_id=payload["message_id"],
            source_core_id=payload["source_core_id"],
            source_platform_id=payload["source_platform_id"],
            source_generation=payload["source_generation"],
            room_id=payload["room_id"],
            body=payload["body"],
            created_at=created_at,
            reply_to=payload.get("reply_to"),
            idempotency_key=payload.get("idempotency_key"),
        )


__all__ = [
    "ActorKind",
    "CHAT_CONTRACT_SCHEMA",
    "ChatActor",
    "ChatAudience",
    "ChatAuditEvent",
    "ChatMessage",
    "CoreIdentity",
    "Draft",
    "GENERAL_ROOM_ID",
    "InvitationStatus",
    "MAX_CORE_IDENTITIES",
    "MAX_MESSAGE_BODY_BYTES",
    "MembershipStatus",
    "MessageOrigin",
    "MessagePage",
    "MessageProvenance",
    "OutboxEntry",
    "PEER_ENVELOPE_SCHEMA",
    "PeerEnvelope",
    "RetentionResult",
    "Room",
    "RoomHistoryPolicy",
    "RoomInvitation",
    "RoomKind",
    "RoomMembership",
    "RoomSync",
    "SyncResult",
]
