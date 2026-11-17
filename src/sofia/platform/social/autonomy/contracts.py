"""Bounded contracts for autonomous Core-to-Core social behavior.

The autonomy layer only decides whether a Core wants to participate and what
kind of social action it proposes. It never grants execution authority, never
generates a Core's voice by script, and never treats interpersonal trust as a
Platform permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import re
from typing import Protocol, runtime_checkable
from uuid import UUID


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_TEXT_LIMIT = 4000
MAX_INDEPENDENT_CORES = 7


def _utc(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be a bounded identifier")
    return value


def _text(value: str, name: str, maximum: int = _TEXT_LIMIT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError(f"{name} must be bounded nonempty text")
    return value.strip()


@dataclass(frozen=True, slots=True)
class CoreIdentity:
    """One independently identified Core, never inferred from a display name."""

    core_id: UUID
    platform_id: str
    generation: int
    display_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.core_id, UUID):
            raise TypeError("core_id must be a UUID")
        _identifier(self.platform_id, "platform_id")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be a positive integer")
        _text(self.display_name, "display_name", 120)


class RoomKind(str, Enum):
    GENERAL = "general"
    DIRECT = "direct"
    PRIVATE_GROUP = "private_group"


class Audience(str, Enum):
    PUBLIC = "public"
    PARTICIPANTS = "participants"
    PRIVATE = "private"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """Typed inbound/outbound message boundary used by the autonomy seam."""

    message_id: str
    room_id: str
    sender_core_id: UUID
    audience: str
    body: str
    created_at: datetime
    reply_to: str | None
    origin: str
    sequence: int
    provenance: str

    def __post_init__(self) -> None:
        _identifier(self.message_id, "message_id")
        _identifier(self.room_id, "room_id")
        if not isinstance(self.sender_core_id, UUID):
            raise TypeError("sender_core_id must be a UUID")
        _identifier(self.audience, "audience")
        _text(self.body, "body")
        if _utc(self.created_at, "created_at") != self.created_at:
            raise ValueError("created_at must be an exact UTC instant")
        if self.reply_to is not None:
            _identifier(self.reply_to, "reply_to")
        _identifier(self.origin, "origin")
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        _identifier(self.provenance, "provenance")


class SocialAction(str, Enum):
    SEND_MESSAGE = "send_message"
    REPLY = "reply"
    JOIN = "join"
    INVITE = "invite"
    START_PRIVATE = "start_private"
    CONTINUE_TOPIC = "continue_topic"
    DECLINE = "decline"
    PAUSE = "pause"
    LEAVE = "leave"
    BLOCK = "block"
    SILENCE = "silence"
    DEFER = "defer"
    SHARE = "share"
    REFUSED = "refused"


class SocialEventKind(str, Enum):
    MESSAGE_RECEIVED = "message_received"
    ROOM_ACTIVITY = "room_activity"
    PEER_JOINED = "peer_joined"
    TOPIC_DUE = "topic_due"
    INITIATION = "initiation"
    SCHEDULED_WAKE = "scheduled_wake"


@dataclass(frozen=True, slots=True)
class SocialEvent:
    """One wake-on-event stimulus; absence of events means no inference work."""

    event_id: str
    core_id: UUID
    kind: SocialEventKind
    occurred_at: datetime
    room_id: str | None = None
    chain_id: str | None = None
    peer_core_id: UUID | None = None
    topic_key: str | None = None
    message: ChatMessage | None = None
    recent_messages: tuple[ChatMessage, ...] = ()
    room_kind: RoomKind = RoomKind.GENERAL

    def __post_init__(self) -> None:
        _identifier(self.event_id, "event_id")
        if not isinstance(self.core_id, UUID):
            raise TypeError("core_id must be a UUID")
        if not isinstance(self.kind, SocialEventKind):
            raise TypeError("kind must be SocialEventKind")
        if _utc(self.occurred_at, "occurred_at") != self.occurred_at:
            raise ValueError("occurred_at must be an exact UTC instant")
        if self.room_id is not None:
            _identifier(self.room_id, "room_id")
        if self.chain_id is not None:
            _identifier(self.chain_id, "chain_id")
        if self.peer_core_id is not None and not isinstance(
            self.peer_core_id, UUID
        ):
            raise TypeError("peer_core_id must be a UUID")
        if self.topic_key is not None:
            _identifier(self.topic_key, "topic_key")
        if self.message is not None and not isinstance(self.message, ChatMessage):
            raise TypeError("message must be a ChatMessage")
        if not isinstance(self.recent_messages, tuple) or any(
            not isinstance(item, ChatMessage) for item in self.recent_messages
        ):
            raise TypeError("recent_messages must be a tuple of ChatMessage")
        if not isinstance(self.room_kind, RoomKind):
            raise TypeError("room_kind must be RoomKind")
        if self.kind is SocialEventKind.MESSAGE_RECEIVED and self.message is None:
            raise ValueError("message_received events require a message")
        if (
            self.kind in {SocialEventKind.TOPIC_DUE, SocialEventKind.INITIATION}
            and self.topic_key is None
        ):
            raise ValueError("topic events require a topic_key")


@dataclass(frozen=True, slots=True)
class SocialProposal:
    """An inert, planner-produced intention; the engine still gates it."""

    action: SocialAction
    relevance: float
    meaningful: bool
    body: str | None = None
    topic: str | None = None
    room_id: str | None = None
    audience: str | None = None
    target_core_id: UUID | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.action, SocialAction):
            raise TypeError("action must be SocialAction")
        if (
            isinstance(self.relevance, bool)
            or not isinstance(self.relevance, (int, float))
            or not 0.0 <= float(self.relevance) <= 1.0
        ):
            raise ValueError("relevance must be in 0..1")
        if type(self.meaningful) is not bool:
            raise ValueError("meaningful must be a bool")
        if self.body is not None:
            _text(self.body, "body")
        if self.topic is not None:
            _identifier(self.topic, "topic")
        if self.room_id is not None:
            _identifier(self.room_id, "room_id")
        if self.audience is not None:
            _identifier(self.audience, "audience")
        if self.target_core_id is not None and not isinstance(
            self.target_core_id, UUID
        ):
            raise TypeError("target_core_id must be a UUID")
        if not isinstance(self.evidence_refs, tuple) or len(
            self.evidence_refs
        ) > 8:
            raise ValueError("evidence_refs must be a bounded tuple")
        if any(
            not isinstance(item, str) or _IDENTIFIER.fullmatch(item) is None
            for item in self.evidence_refs
        ):
            raise ValueError("evidence refs must be bounded identifiers")


@dataclass(frozen=True, slots=True)
class SocialDecision:
    """A bounded outcome with no inherent execution or disclosure authority."""

    action: SocialAction
    core_id: UUID
    reason: str
    target_core_id: UUID | None = None
    room_id: str | None = None
    body: str | None = None
    permitted: bool = False
    duplicate_suppressed: bool = False
    deferred_until: datetime | None = None
    delivery_ref: str | None = None
    payload_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, SocialAction):
            raise TypeError("action must be SocialAction")
        if not isinstance(self.core_id, UUID):
            raise TypeError("core_id must be a UUID")
        _text(self.reason, "reason", 600)
        if self.deferred_until is not None and _utc(
            self.deferred_until, "deferred_until"
        ) != self.deferred_until:
            raise ValueError("deferred_until must be an exact UTC instant")

    @property
    def execution_authority(self) -> bool:
        return False

    @property
    def silent(self) -> bool:
        return self.action in {SocialAction.SILENCE, SocialAction.DEFER}


@dataclass(frozen=True, slots=True)
class AutonomyLimits:
    max_chain_turns: int = 6
    contact_cooldown: timedelta = timedelta(minutes=30)
    max_contacts_per_day: int = 40
    max_inference_units_per_day: int = 120
    relevance_threshold: float = 0.45
    topic_revisit_after: timedelta = timedelta(hours=24)

    def __post_init__(self) -> None:
        for name in (
            "max_chain_turns",
            "max_contacts_per_day",
            "max_inference_units_per_day",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if (
            not isinstance(self.contact_cooldown, timedelta)
            or self.contact_cooldown < timedelta(0)
        ):
            raise ValueError("contact_cooldown must be non-negative")
        if (
            not isinstance(self.topic_revisit_after, timedelta)
            or self.topic_revisit_after < timedelta(0)
        ):
            raise ValueError("topic_revisit_after must be non-negative")
        if (
            isinstance(self.relevance_threshold, bool)
            or not isinstance(self.relevance_threshold, (int, float))
            or not 0.0 <= float(self.relevance_threshold) <= 1.0
        ):
            raise ValueError("relevance_threshold must be in 0..1")


@dataclass(frozen=True, slots=True)
class SocialContext:
    """Read-only projection supplied to a Core's own planner."""

    now: datetime
    event: SocialEvent
    relationship: object
    interests: tuple
    goals: tuple
    boundaries: tuple
    unresolved_topics: tuple
    active_evidence: tuple
    recent_messages: tuple[ChatMessage, ...]
    remaining_contacts: int
    remaining_inference: int
    room_kind: RoomKind


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime:
        ...


@runtime_checkable
class SocialPlanner(Protocol):
    def propose(
        self,
        *,
        core: CoreIdentity,
        event: SocialEvent,
        context: SocialContext,
    ) -> SocialProposal | None:
        ...


@runtime_checkable
class SocialTransport(Protocol):
    """Narrow chat-engine seam; the engine never imports the chat engine."""

    def deliver(self, decision: SocialDecision) -> str | None:
        ...


@runtime_checkable
class InferenceScheduler(Protocol):
    """Event-driven wake seam; no polling or implicit model calls."""

    def wake(
        self,
        *,
        core_id: UUID,
        reason: str,
        due_at: datetime,
        event_id: str,
    ) -> None:
        ...


@runtime_checkable
class StopAuthority(Protocol):
    def is_operator_stopped(self) -> bool:
        ...


@runtime_checkable
class SocialAuthorization(Protocol):
    def authorize(
        self,
        *,
        core: CoreIdentity,
        action: SocialAction,
        room_id: str | None,
        target_core_id: UUID | None,
        audience: str | None,
    ) -> bool:
        ...


@runtime_checkable
class InterestSource(Protocol):
    def interest_strength(self, *, core_id: UUID, topic: str) -> float:
        ...


@runtime_checkable
class BoundarySource(Protocol):
    def contact_allowed(
        self,
        *,
        core_id: UUID,
        peer_core_id: UUID,
        room_id: str | None,
    ) -> bool:
        ...


@runtime_checkable
class SocialProfileSource(Protocol):
    """Read seam for canonical LIFE/goals/boundary owners where available."""

    def interests(self, *, core_id: UUID) -> tuple:
        ...

    def goals(self, *, core_id: UUID) -> tuple:
        ...

    def boundaries(
        self, *, core_id: UUID, peer_core_id: UUID | None
    ) -> tuple:
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class DenyAllAuthorization:
    """Safe default: no social action is externally permitted."""

    def authorize(
        self,
        *,
        core: CoreIdentity,
        action: SocialAction,
        room_id: str | None,
        target_core_id: UUID | None,
        audience: str | None,
    ) -> bool:
        return False


class NotStopped:
    """Default stop seam used only when a host deliberately supplies no STOP."""

    def is_operator_stopped(self) -> bool:
        return False
