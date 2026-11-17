"""Client-facing chat projections over the assumed social contracts.

Nothing in this module authenticates a principal, grants authority, or creates
canonical state. These are immutable wire/view values used by CLI, TUI, desktop
and Android remote clients. The federation owner remains the authority for
identity verification, delivery and membership transitions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from uuid import UUID

_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_MAX_BODY = 16_000
_MAX_NAME = 120


def _utc(value: datetime, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _uuid(value: str, label: str) -> str:
    if not isinstance(value, str) or _UUID.fullmatch(value.lower()) is None:
        raise ValueError(f"{label} must be a canonical UUID")
    return str(UUID(value))


class RoomKind(str, Enum):
    GENERAL = "general"
    DIRECT = "direct"
    PRIVATE_GROUP = "private_group"


class MembershipStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    DECLINED = "declined"
    LEFT = "left"
    REVOKED = "revoked"


class MessageOrigin(str, Enum):
    OWNER = "owner"
    CORE = "core"
    SYSTEM = "system"


class ConnectionState(str, Enum):
    CONNECTED = "connected"
    OFFLINE = "offline"
    CONNECTING = "connecting"
    DEGRADED = "degraded"
    REVOKED = "revoked"


class SendStatus(str, Enum):
    PENDING = "pending"
    SENT_CONFIRMED = "sent_confirmed"
    SENT_UNCONFIRMED = "sent_unconfirmed"
    DENIED = "denied"
    OUTCOME_UNKNOWN = "outcome_unknown"


@dataclass(frozen=True, slots=True)
class CoreIdentity:
    core_id: str
    platform_id: str
    generation: int
    display_name: str

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        _identifier(self.platform_id, "platform_id")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be a positive integer")
        if (
            not isinstance(self.display_name, str)
            or not self.display_name.strip()
            or len(self.display_name) > _MAX_NAME
        ):
            raise ValueError("display_name must be bounded nonempty text")

    @property
    def normalized_core_id(self) -> str:
        return self.core_id.lower()


@dataclass(frozen=True, slots=True)
class ChatMessage:
    message_id: str
    room_id: str
    sender_core_id: str | None
    audience: str
    body: str
    created_at: datetime
    reply_to: str | None
    origin: MessageOrigin
    sequence: int
    provenance: str

    def __post_init__(self) -> None:
        _identifier(self.message_id, "message_id")
        _identifier(self.room_id, "room_id")
        if self.sender_core_id is not None:
            _uuid(self.sender_core_id, "sender_core_id")
        _identifier(self.audience, "audience")
        if not isinstance(self.body, str) or not self.body.strip():
            raise ValueError("body must be nonempty text")
        if len(self.body) > _MAX_BODY:
            raise ValueError("body exceeds the client bound")
        _utc(self.created_at, "created_at")
        if self.reply_to is not None:
            _identifier(self.reply_to, "reply_to")
        if not isinstance(self.origin, MessageOrigin):
            raise TypeError("origin must be a MessageOrigin")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be a positive integer")
        _identifier(self.provenance, "provenance")
        if self.origin is MessageOrigin.CORE and self.sender_core_id is None:
            raise ValueError("Core-origin messages require sender_core_id")
        if self.origin is MessageOrigin.SYSTEM and self.sender_core_id is not None:
            raise ValueError("system messages cannot claim a Core sender")


@dataclass(frozen=True, slots=True)
class RoomMembership:
    room_id: str
    core_id: str
    epoch: int
    status: MembershipStatus
    joined_at: datetime | None
    history_from_sequence: int

    def __post_init__(self) -> None:
        _identifier(self.room_id, "room_id")
        _uuid(self.core_id, "core_id")
        if type(self.epoch) is not int or self.epoch < 1:
            raise ValueError("epoch must be a positive integer")
        if not isinstance(self.status, MembershipStatus):
            raise TypeError("status must be a MembershipStatus")
        if self.joined_at is not None:
            _utc(self.joined_at, "joined_at")
        if (
            type(self.history_from_sequence) is not int
            or self.history_from_sequence < 0
        ):
            raise ValueError("history_from_sequence must be nonnegative")


@dataclass(frozen=True, slots=True)
class ChatRoom:
    room_id: str
    kind: RoomKind
    title: str
    created_by_core_id: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        _identifier(self.room_id, "room_id")
        if not isinstance(self.kind, RoomKind):
            raise TypeError("kind must be a RoomKind")
        if (
            not isinstance(self.title, str)
            or not self.title.strip()
            or len(self.title) > _MAX_NAME
        ):
            raise ValueError("title must be bounded nonempty text")
        if self.created_by_core_id is not None:
            _uuid(self.created_by_core_id, "created_by_core_id")
        _utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ChatEvent:
    revision: int
    core_id: str
    room_id: str
    message: ChatMessage | None
    kind: str
    mentioned_core_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        _uuid(self.core_id, "core_id")
        _identifier(self.room_id, "room_id")
        if self.message is not None and not isinstance(self.message, ChatMessage):
            raise TypeError("message must be a ChatMessage or None")
        _identifier(self.kind, "kind")
        if type(self.mentioned_core_ids) is not tuple:
            raise TypeError("mentioned_core_ids must be a tuple")
        for core_id in self.mentioned_core_ids:
            _uuid(core_id, "mentioned core_id")


@dataclass(frozen=True, slots=True)
class MessagePage:
    messages: tuple[ChatMessage, ...]
    before_sequence: int | None
    has_more: bool
    oldest_sequence: int | None
    newest_sequence: int | None

    def __post_init__(self) -> None:
        if type(self.messages) is not tuple:
            raise TypeError("messages must be a tuple")
        for message in self.messages:
            if not isinstance(message, ChatMessage):
                raise TypeError("messages must contain ChatMessage values")
        for label, value in (
            ("before_sequence", self.before_sequence),
            ("oldest_sequence", self.oldest_sequence),
            ("newest_sequence", self.newest_sequence),
        ):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{label} must be None or nonnegative")
        if not isinstance(self.has_more, bool):
            raise TypeError("has_more must be bool")


@dataclass(frozen=True, slots=True)
class SendReceipt:
    client_message_id: str
    room_id: str
    status: SendStatus
    message: ChatMessage | None = None
    denial_code: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.client_message_id, "client_message_id")
        _identifier(self.room_id, "room_id")
        if not isinstance(self.status, SendStatus):
            raise TypeError("status must be a SendStatus")
        if self.message is not None and not isinstance(self.message, ChatMessage):
            raise TypeError("message must be a ChatMessage or None")
        if self.denial_code is not None:
            _identifier(self.denial_code, "denial_code")
        if self.detail is not None and not isinstance(self.detail, str):
            raise TypeError("detail must be text or None")


class ChatPermissionDenied(PermissionError):
    def __init__(self, code: str, detail: str = "permission denied") -> None:
        _identifier(code, "denial code")
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class ChatOffline(RuntimeError):
    pass


def normalize_core_id(value: str) -> str:
    return _uuid(value, "core_id").lower()
