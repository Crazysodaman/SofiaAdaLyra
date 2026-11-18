"""Composition layer for independent multi-Core conversation.

Canonical identity, membership, audience, delivery and history remain owned by
:class:`sofia.platform.chat.ChatEngine`.  This module adds only composition:

* register independently issued Core identities;
* create or reuse general, owner-direct, Core-to-Core and group channels;
* route a persisted message to selected Cores through the participation policy;
* invoke each Core's injected responder and persist its output under that
  Core's authenticated identity.

A responder's output is data.  It cannot choose a sender identity, cannot
address an audience outside the stored message audience and never grants tool,
lifecycle or execution authority.  No dialogue is authored here.
"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from hashlib import sha256
import re
from types import MappingProxyType
from typing import Iterable, Protocol, runtime_checkable
from uuid import UUID

from sofia.core.multicore.contracts import ChannelKind
from sofia.core.multicore.routing import (
    ParticipationAction,
    ParticipationDecision,
    ParticipationRouter,
    RoutingLimits,
)
from sofia.platform.chat import (
    ActorKind,
    ChatActor,
    ChatEngine,
    ChatMessage,
    CoreIdentity,
    MessageOrigin,
    Room,
    RoomHistoryPolicy,
    RoomInvitation,
    RoomKind,
    RoomMembership,
)


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_MENTION = re.compile(r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159})")
_SLUG = re.compile(r"[^a-z0-9]+")
_RESPONSE_METADATA_LIMIT = 32
_AUTHORITY_KEYS = frozenset(
    {
        "actor_id",
        "author",
        "authority",
        "capabilities",
        "core_id",
        "execute",
        "execution_authority",
        "grants_authority",
        "permissions",
        "sender",
        "sender_core_id",
        "tool_calls",
        "tools",
    }
)
_RESPONSE_KEYS = frozenset({"body", "metadata", "reply_to"})


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _profile_value(record: object, *names: str) -> object | None:
    for name in names:
        if isinstance(record, Mapping):
            if name in record:
                return record[name]
        elif hasattr(record, name):
            return getattr(record, name)
    return None


def chat_identity_from_profile(
    record: object,
    *,
    platform_id: str,
    generation: int | None = None,
    display_name: str | None = None,
) -> CoreIdentity:
    """Adapt a Workstream A profile/identity record without importing it.

    ``PersistentCoreIdentity`` and ``CoreDescriptor`` both expose a stable
    ``core_id``; only ``generation`` or ``platform_id`` may need to be supplied
    by the owning composition.  Display text is never used as identity.  A
    richer ``CoreProfile`` wrapper is unwrapped through its descriptor.
    """
    descriptor = _profile_value(record, "descriptor")
    if descriptor is not None:
        record = descriptor
    core = _profile_value(record, "core_id")
    if core is None:
        raise ValueError("profile record has no independent core_id")
    if isinstance(core, str):
        core = UUID(core)
    if not isinstance(core, UUID):
        raise TypeError("profile core_id must be a UUID")
    resolved_generation = (
        generation
        if generation is not None
        else _profile_value(record, "generation")
    )
    if type(resolved_generation) is not int or resolved_generation < 1:
        raise ValueError("profile adaptation requires a positive generation")
    name = display_name
    if name is None:
        value = _profile_value(
            record, "display_name", "full_name", "nickname", "name"
        )
        name = value if isinstance(value, str) else None
    if name is None or not name.strip():
        raise ValueError("profile adaptation requires a display name")
    return CoreIdentity(
        core_id=core,
        platform_id=platform_id,
        generation=resolved_generation,
        display_name=name,
    )


@dataclass(frozen=True, slots=True)
class CoreResponse:
    """Inert text proposed by a Core's own responder."""

    body: str
    reply_to: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.body, str) or not self.body.strip():
            raise ValueError("response body must be nonempty text")
        if len(self.body.encode("utf-8")) > 64 * 1024:
            raise ValueError("response body exceeds the bounded maximum")
        if self.reply_to is not None:
            _identifier(self.reply_to, "reply_to")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        if len(self.metadata) > _RESPONSE_METADATA_LIMIT:
            raise ValueError("metadata has too many entries")
        forbidden = _AUTHORITY_KEYS.intersection(self.metadata)
        if forbidden:
            raise PermissionError(
                "responder metadata may not carry identity or authority: "
                + ", ".join(sorted(forbidden))
            )
        for key in self.metadata:
            if not isinstance(key, str):
                raise TypeError("metadata keys must be text")
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata))
        )

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


def coerce_core_response(result: object) -> CoreResponse | None:
    """Normalize responder output without accepting impersonation or authority."""
    if result is None:
        return None
    if isinstance(result, CoreResponse):
        return result
    if isinstance(result, str):
        return CoreResponse(result)
    if isinstance(result, Mapping):
        keys = set(result)
        forbidden = keys.intersection(_AUTHORITY_KEYS)
        if forbidden:
            raise PermissionError(
                "responder output may not carry identity or authority: "
                + ", ".join(sorted(str(item) for item in forbidden))
            )
        unknown = keys - _RESPONSE_KEYS
        if unknown:
            raise ValueError(
                "responder output has unsupported fields: "
                + ", ".join(sorted(str(item) for item in unknown))
            )
        body = result.get("body")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("responder output requires a nonempty body")
        metadata = result.get("metadata", {})
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, Mapping):
            raise TypeError("responder metadata must be a mapping")
        return CoreResponse(
            body=body,
            reply_to=result.get("reply_to"),
            metadata=metadata,
        )
    raise TypeError("responder output must be text, CoreResponse or None")


@runtime_checkable
class CoreResponder(Protocol):
    """Injected cognition seam; later inference hosts implement this shape."""

    def respond(self, request: "ConversationTurn") -> object:
        ...


@runtime_checkable
class RelevanceSource(Protocol):
    """Optional Workstream A/LIFE relevance seam; never a hardcoded script."""

    def relevance(
        self,
        *,
        core_id: str,
        trigger: ChatMessage,
        channel: "ConversationChannel",
    ) -> float:
        ...


@dataclass(frozen=True, slots=True)
class ConversationChannel:
    room_id: str
    kind: ChannelKind
    room: Room

    def __post_init__(self) -> None:
        _identifier(self.room_id, "room_id")
        if not isinstance(self.kind, ChannelKind):
            raise TypeError("kind must be a ChannelKind")
        if not isinstance(self.room, Room):
            raise TypeError("room must be a Room")

    @property
    def is_general(self) -> bool:
        return self.kind is ChannelKind.GENERAL


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    """Read-only projection supplied to one injected Core responder."""

    core_id: str
    channel: ConversationChannel
    trigger: ChatMessage
    history: tuple[ChatMessage, ...]
    mentioned: bool
    chain_id: str

    def __post_init__(self) -> None:
        _identifier(self.core_id, "core_id")
        if not isinstance(self.channel, ConversationChannel):
            raise TypeError("channel must be a ConversationChannel")
        if not isinstance(self.trigger, ChatMessage):
            raise TypeError("trigger must be a ChatMessage")
        if not isinstance(self.history, tuple):
            raise TypeError("history must be a tuple")
        if type(self.mentioned) is not bool:
            raise TypeError("mentioned must be bool")
        _identifier(self.chain_id, "chain_id")

    @property
    def trigger_is_untrusted(self) -> bool:
        return self.trigger.is_untrusted

    def _message_data(self, message: ChatMessage) -> Mapping[str, object]:
        if message.is_untrusted:
            return message.as_untrusted_data()
        return {
            "message_id": message.message_id,
            "room_id": message.room_id,
            "sender_core_id": message.sender_core_id,
            "body": message.body,
            "trust": "DATA",
            "is_instruction": False,
            "grants_authority": False,
        }

    def as_data(self) -> Mapping[str, object]:
        return {
            "schema": "aegis.core.multicore.conversation.turn.v1",
            "core_id": self.core_id,
            "channel": {
                "room_id": self.channel.room_id,
                "kind": self.channel.kind.value,
            },
            "trigger": self._message_data(self.trigger),
            "history": tuple(self._message_data(item) for item in self.history),
            "mentioned": self.mentioned,
            "chain_id": self.chain_id,
            "is_instruction": False,
            "grants_authority": False,
        }


@dataclass(frozen=True, slots=True)
class CoreParticipant:
    identity: CoreIdentity
    responder: CoreResponder | object | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, CoreIdentity):
            raise TypeError("identity must be a CoreIdentity")
        if self.responder is not None and not callable(self.responder) and not hasattr(
            self.responder, "respond"
        ):
            raise TypeError("responder must be callable or expose respond()")

    @property
    def core_id(self) -> str:
        return self.identity.core_id_text


@dataclass(frozen=True, slots=True)
class AuthorView:
    actor_id: str
    kind: ActorKind
    display_name: str
    origin: MessageOrigin
    source_platform_id: str
    source_generation: int | None
    transport_verified: bool
    untrusted_content: bool

    @property
    def is_owner(self) -> bool:
        return self.kind is ActorKind.OWNER


@dataclass(frozen=True, slots=True)
class ConversationResult:
    message: ChatMessage
    decisions: tuple[ParticipationDecision, ...]
    replies: tuple[ChatMessage, ...]

    @property
    def responded_core_ids(self) -> tuple[str, ...]:
        return tuple(message.sender_core_id for message in self.replies)


class MultiCoreConversation:
    """Composition over the canonical Platform chat engine."""

    def __init__(
        self,
        engine: ChatEngine,
        *,
        router: ParticipationRouter | None = None,
        clock=None,
        relevance_source: RelevanceSource | None = None,
    ) -> None:
        if not isinstance(engine, ChatEngine):
            raise TypeError("engine must be a ChatEngine")
        if router is not None and not isinstance(router, ParticipationRouter):
            raise TypeError("router must be a ParticipationRouter")
        self._engine = engine
        if router is None:
            router = ParticipationRouter(
                clock=clock,
                limits=RoutingLimits(),
            )
        self._router = router
        if relevance_source is not None and not isinstance(
            relevance_source, RelevanceSource
        ):
            raise TypeError("relevance_source must implement relevance()")
        self._relevance_source = relevance_source
        self._participants: dict[str, CoreParticipant] = {}
        self._selected: dict[str, str] = {}
        self._chain_by_message: OrderedDict[str, str] = OrderedDict()
        self._chain_limit = 4096

    @property
    def engine(self) -> ChatEngine:
        return self._engine

    @property
    def router(self) -> ParticipationRouter:
        return self._router

    @property
    def owner_id(self) -> str:
        return self._engine.owner_id

    def owner_actor(self) -> ChatActor:
        return self._engine.owner_actor()

    # ------------------------------------------------------------------
    # Identity registration and profile adaptation
    # ------------------------------------------------------------------
    def register_core(
        self,
        identity: CoreIdentity | object,
        *,
        responder: CoreResponder | object | None = None,
        authorize: bool = True,
        platform_id: str | None = None,
        generation: int | None = None,
        display_name: str | None = None,
    ) -> CoreIdentity:
        if isinstance(identity, CoreIdentity):
            resolved = identity
        else:
            if platform_id is None:
                raise ValueError(
                    "profile registration requires the owning platform_id"
                )
            resolved = chat_identity_from_profile(
                identity,
                platform_id=platform_id,
                generation=generation,
                display_name=display_name,
            )
        if type(authorize) is not bool:
            raise TypeError("authorize must be bool")
        self._engine.register_core(resolved, authorize=authorize)
        self._participants[resolved.core_id_text] = CoreParticipant(
            resolved, responder
        )
        return resolved

    def register_profile(
        self,
        profile: object,
        *,
        platform_id: str,
        responder: CoreResponder | object | None = None,
        generation: int | None = None,
        display_name: str | None = None,
        authorize: bool = True,
    ) -> CoreIdentity:
        return self.register_core(
            profile,
            responder=responder,
            authorize=authorize,
            platform_id=platform_id,
            generation=generation,
            display_name=display_name,
        )

    def participant(self, core_id: str) -> CoreParticipant:
        _identifier(core_id, "core_id")
        participant = self._participants.get(core_id)
        if participant is None:
            raise LookupError("Core is not registered in this conversation")
        return participant

    def participants(self) -> tuple[CoreParticipant, ...]:
        return tuple(
            self._participants[core_id] for core_id in sorted(self._participants)
        )

    def actor(self, core_id: str) -> ChatActor:
        return ChatActor.core(self.participant(core_id).identity)

    def core_identity(self, core_id: str) -> CoreIdentity | None:
        return self._engine.core_identity(core_id)

    def revoke_core(self, core_id: str) -> None:
        self._engine.revoke_core(
            self.owner_actor(), _identifier(core_id, "core_id"), reason="owner revoke"
        )
        self._participants.pop(core_id, None)
        self._selected.pop(core_id, None)

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------
    def _channel_kind(self, room: Room) -> ChannelKind:
        if room.kind is RoomKind.GENERAL:
            return ChannelKind.GENERAL
        if room.kind is RoomKind.PRIVATE_GROUP:
            return ChannelKind.GROUP
        if room.kind is RoomKind.DIRECT:
            return (
                ChannelKind.DIRECT
                if room.created_by == self._engine.owner_id
                else ChannelKind.CORE_TO_CORE
            )
        raise ValueError("unsupported room kind")

    def channel(self, actor: ChatActor, room_id: str) -> ConversationChannel:
        room = self._engine.room(actor, room_id)
        return ConversationChannel(room_id, self._channel_kind(room), room)

    def channels(self, actor: ChatActor) -> tuple[ConversationChannel, ...]:
        return tuple(
            ConversationChannel(room.room_id, self._channel_kind(room), room)
            for room in self._engine.rooms(actor)
        )

    def general(self) -> ConversationChannel:
        return self.channel(self.owner_actor(), "general")

    def open_owner_direct(self, core_id: str) -> ConversationChannel:
        self.participant(core_id)
        room = self._engine.open_direct(self.owner_actor(), core_id)
        return ConversationChannel(room.room_id, ChannelKind.DIRECT, room)

    def open_core_direct(
        self, initiator_id: str, other_id: str
    ) -> ConversationChannel:
        if initiator_id == other_id:
            raise ValueError("a Core cannot open a direct channel with itself")
        actor = self.actor(initiator_id)
        self.participant(other_id)
        room = self._engine.open_direct(actor, other_id)
        return ConversationChannel(room.room_id, ChannelKind.CORE_TO_CORE, room)

    def create_group(
        self,
        creator: ChatActor,
        name: str,
        *,
        topic: str = "",
        member_ids: Iterable[str] = (),
        history_policy: RoomHistoryPolicy = RoomHistoryPolicy.NO_PRE_JOIN,
        retention_seconds: int | None = None,
    ) -> ConversationChannel:
        identifiers = tuple(dict.fromkeys(member_ids))
        for member_id in identifiers:
            self.participant(member_id)
        room = self._engine.create_group(
            creator,
            name,
            topic=topic,
            member_ids=identifiers,
            history_policy=history_policy,
            retention_seconds=retention_seconds,
        )
        return ConversationChannel(room.room_id, ChannelKind.GROUP, room)

    def accept_channel(self, core_id: str, room_id: str) -> RoomMembership:
        return self._engine.join_room(self.actor(core_id), room_id)

    def invite_core(
        self,
        actor: ChatActor,
        room_id: str,
        target_core_id: str,
        *,
        history_from_sequence: int | None = None,
        expires_at: datetime | None = None,
    ) -> RoomInvitation:
        self.participant(target_core_id)
        return self._engine.invite(
            actor,
            room_id,
            target_core_id,
            history_from_sequence=history_from_sequence,
            expires_at=expires_at,
        )

    def accept_invitation(self, actor: ChatActor, invite_id: str) -> RoomMembership:
        return self._engine.accept_invitation(actor, invite_id)

    def decline_invitation(
        self, actor: ChatActor, invite_id: str
    ) -> RoomInvitation:
        return self._engine.decline_invitation(actor, invite_id)

    def pending_invitations(
        self, actor: ChatActor, *, room_id: str | None = None
    ) -> tuple[RoomInvitation, ...]:
        return self._engine.pending_invitations(actor, room_id=room_id)

    def leave_channel(self, core_id: str, room_id: str) -> None:
        self._engine.leave_room(self.actor(core_id), room_id)

    # ------------------------------------------------------------------
    # Owner channel switching
    # ------------------------------------------------------------------
    def switch_channel(self, actor: ChatActor, room_id: str) -> ConversationChannel:
        channel = self.channel(actor, room_id)
        self._selected[actor.actor_id] = room_id
        return channel

    def active_channel(self, actor: ChatActor) -> ConversationChannel | None:
        room_id = self._selected.get(actor.actor_id)
        if room_id is None:
            return None
        try:
            return self.channel(actor, room_id)
        except (PermissionError, LookupError):
            self._selected.pop(actor.actor_id, None)
            return None

    def clear_active_channel(self, actor: ChatActor) -> None:
        self._selected.pop(actor.actor_id, None)

    # ------------------------------------------------------------------
    # Persistence, attribution and history
    # ------------------------------------------------------------------
    def post(
        self,
        actor: ChatActor,
        room_id: str,
        body: str,
        *,
        reply_to: str | None = None,
        created_at: datetime | None = None,
        idempotency_key: str | None = None,
        message_id: str | None = None,
    ) -> ChatMessage:
        message = self._engine.send(
            actor,
            room_id,
            body,
            reply_to=reply_to,
            created_at=created_at,
            idempotency_key=idempotency_key,
            message_id=message_id,
        )
        self._remember_chain(message)
        return message

    def post_as(
        self,
        core_id: str,
        room_id: str,
        body: str,
        **kwargs,
    ) -> ChatMessage:
        return self.post(self.actor(core_id), room_id, body, **kwargs)

    def history(
        self,
        actor: ChatActor,
        room_id: str,
        *,
        after_sequence: int | None = None,
        before_sequence: int | None = None,
        limit: int = 50,
    ):
        return self._engine.history(
            actor,
            room_id,
            after_sequence=after_sequence,
            before_sequence=before_sequence,
            limit=limit,
        )

    def author(self, message: ChatMessage) -> AuthorView:
        if not isinstance(message, ChatMessage):
            raise TypeError("message must be a ChatMessage")
        if message.origin is MessageOrigin.OWNER:
            kind = ActorKind.OWNER
            name = "owner"
        else:
            kind = ActorKind.CORE
            identity = self._engine.core_identity(message.sender_core_id)
            name = identity.display_name if identity is not None else "unknown"
        return AuthorView(
            actor_id=message.sender_core_id,
            kind=kind,
            display_name=name,
            origin=message.origin,
            source_platform_id=message.provenance.source_platform_id,
            source_generation=message.provenance.source_generation,
            transport_verified=message.provenance.transport_verified,
            untrusted_content=message.provenance.untrusted_content,
        )

    def _remember_chain(self, message: ChatMessage) -> str:
        if message.reply_to is not None:
            chain_id = self._chain_by_message.get(
                message.reply_to, message.reply_to
            )
        else:
            chain_id = message.message_id
        self._chain_by_message[message.message_id] = chain_id
        while len(self._chain_by_message) > self._chain_limit:
            self._chain_by_message.popitem(last=False)
        return chain_id

    def _extract_mentions(
        self, body: str, candidates: Iterable[str]
    ) -> tuple[str, ...]:
        candidate_set = set(candidates)
        found: list[str] = []
        for raw in _MENTION.findall(body):
            token = raw.casefold()
            for core_id in candidate_set:
                identity = self._participants[core_id].identity
                slug = _SLUG.sub("-", identity.display_name.casefold()).strip("-")
                if token in {
                    core_id.casefold(),
                    identity.display_name.casefold(),
                    slug,
                }:
                    found.append(core_id)
                    break
        return tuple(dict.fromkeys(found))

    def _active_core_ids(
        self, viewer: ChatActor, room_id: str
    ) -> tuple[str, ...]:
        active: list[str] = []
        for core_id in sorted(self._participants):
            if core_id == viewer.actor_id:
                continue
            try:
                membership = self._engine.membership(viewer, room_id, core_id)
            except (PermissionError, LookupError):
                continue
            if membership is not None and membership.is_active:
                active.append(core_id)
        return tuple(active)

    def _relevance_map(
        self,
        trigger: ChatMessage,
        channel: ConversationChannel,
        candidates: Iterable[str],
        mentions: Iterable[str],
        relevance: Mapping[str, float] | None,
    ) -> dict[str, float]:
        mentioned = set(mentions)
        direct = channel.kind in {
            ChannelKind.DIRECT,
            ChannelKind.CORE_TO_CORE,
        }
        values: dict[str, float] = {}
        for core_id in candidates:
            if relevance is not None and core_id in relevance:
                value = float(relevance[core_id])
            elif self._relevance_source is not None:
                value = float(
                    self._relevance_source.relevance(
                        core_id=core_id,
                        trigger=trigger,
                        channel=channel,
                    )
                )
            else:
                value = 1.0 if (direct or core_id in mentioned) else 0.0
            values[core_id] = min(1.0, max(0.0, value))
        return values

    # ------------------------------------------------------------------
    # Routing and responder invocation
    # ------------------------------------------------------------------
    def route(
        self,
        trigger: ChatMessage,
        *,
        viewer: ChatActor,
        mentions: Iterable[str] = (),
        relevance: Mapping[str, float] | None = None,
        topics: Iterable[str] = (),
        chain_id: str | None = None,
    ) -> ConversationResult:
        if not isinstance(trigger, ChatMessage):
            raise TypeError("trigger must be a ChatMessage")
        if not isinstance(viewer, ChatActor):
            raise TypeError("viewer must be a ChatActor")
        channel = self.channel(viewer, trigger.room_id)
        candidates = self._active_core_ids(viewer, trigger.room_id)
        explicit = tuple(
            dict.fromkeys(_identifier(item, "mention") for item in mentions)
        )
        detected = self._extract_mentions(trigger.body, candidates)
        effective_mentions = tuple(dict.fromkeys(explicit + detected))
        relevance_values = self._relevance_map(
            trigger, channel, candidates, effective_mentions, relevance
        )
        responder_available = {
            core_id: self._participants[core_id].responder is not None
            for core_id in candidates
        }
        chain = chain_id or self._chain_by_message.get(
            trigger.message_id, trigger.message_id
        )
        decisions = self._router.evaluate(
            trigger=trigger,
            candidates=candidates,
            mentions=effective_mentions,
            relevance=relevance_values,
            chain_id=chain,
            topics=topics,
            responders_available=responder_available,
        )
        if not decisions:
            return ConversationResult(trigger, (), ())
        try:
            prior = self._engine.history(
                viewer,
                trigger.room_id,
                before_sequence=trigger.sequence,
                limit=20,
            ).messages
        except (PermissionError, LookupError):
            prior = ()
        history = prior + (trigger,)
        mentioned_set = set(effective_mentions)
        replies: list[ChatMessage] = []
        final: list[ParticipationDecision] = []
        ordered = sorted(
            decisions,
            key=lambda item: (
                item.rank if item.rank is not None else 1_000_000,
                item.core_id,
            ),
        )
        for decision in ordered:
            if not decision.should_respond:
                final.append(decision)
                continue
            participant = self._participants.get(decision.core_id)
            if participant is None or participant.responder is None:
                final.append(
                    replace(
                        decision,
                        action=ParticipationAction.SILENCE,
                        reason="no responder is registered for this Core",
                    )
                )
                continue
            request = ConversationTurn(
                core_id=decision.core_id,
                channel=channel,
                trigger=trigger,
                history=history,
                mentioned=decision.core_id in mentioned_set,
                chain_id=chain,
            )
            try:
                responder = participant.responder
                if hasattr(responder, "respond"):
                    raw = responder.respond(request)
                else:
                    raw = responder(request)
                response = coerce_core_response(raw)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as error:
                final.append(
                    replace(
                        decision,
                        action=ParticipationAction.SILENCE,
                        reason=f"responder failed: {type(error).__name__}",
                    )
                )
                continue
            if response is None:
                final.append(
                    replace(
                        decision,
                        action=ParticipationAction.SILENCE,
                        reason="responder produced no message",
                    )
                )
                continue
            if self._router.content_is_duplicate(
                decision.core_id,
                response.body,
                room_id=trigger.room_id,
            ):
                final.append(
                    replace(
                        decision,
                        action=decision.action.SUPPRESSED_DUPLICATE,
                        reason="duplicate Core response was suppressed",
                    )
                )
                continue
            reply_to = response.reply_to or trigger.message_id
            if not self._reply_target_is_visible(
                participant.identity, trigger.room_id, reply_to
            ):
                final.append(
                    replace(
                        decision,
                        action=ParticipationAction.SILENCE,
                        reason="responder reply target is not authorized here",
                    )
                )
                continue
            idempotency = "response:" + sha256(
                "|".join(
                    (trigger.message_id, decision.core_id, response.body)
                ).encode("utf-8")
            ).hexdigest()[:40]
            try:
                reply = self._engine.send(
                    ChatActor.core(participant.identity),
                    trigger.room_id,
                    response.body,
                    reply_to=reply_to,
                    idempotency_key=idempotency,
                )
            except (PermissionError, LookupError, ValueError) as error:
                final.append(
                    replace(
                        decision,
                        action=ParticipationAction.SILENCE,
                        reason=f"reply was not persisted: {type(error).__name__}",
                    )
                )
                continue
            self._remember_chain(reply)
            self._router.record_response(
                decision.core_id,
                chain_id=chain,
                body=response.body,
                room_id=trigger.room_id,
            )
            replies.append(reply)
            final.append(decision)
        final.sort(
            key=lambda item: (
                item.rank if item.rank is not None else 1_000_000,
                item.core_id,
            )
        )
        return ConversationResult(trigger, tuple(final), tuple(replies))

    def _reply_target_is_visible(
        self, identity: CoreIdentity, room_id: str, message_id: str
    ) -> bool:
        try:
            target = self._engine.message(ChatActor.core(identity), message_id)
        except (PermissionError, LookupError):
            return False
        return target.room_id == room_id

    def post_and_route(
        self,
        actor: ChatActor,
        room_id: str,
        body: str,
        *,
        reply_to: str | None = None,
        created_at: datetime | None = None,
        idempotency_key: str | None = None,
        message_id: str | None = None,
        mentions: Iterable[str] = (),
        relevance: Mapping[str, float] | None = None,
        topics: Iterable[str] = (),
        chain_id: str | None = None,
    ) -> ConversationResult:
        message = self.post(
            actor,
            room_id,
            body,
            reply_to=reply_to,
            created_at=created_at,
            idempotency_key=idempotency_key,
            message_id=message_id,
        )
        return self.route(
            message,
            viewer=actor,
            mentions=mentions,
            relevance=relevance,
            topics=topics,
            chain_id=chain_id,
        )

    # ------------------------------------------------------------------
    # Owner participation controls (delegated to the bounded router)
    # ------------------------------------------------------------------
    def set_participation(
        self, core_id: str, enabled: bool, *, notify: bool | None = None
    ) -> None:
        self._router.set_participation(core_id, enabled, notify=notify)

    def set_notification(self, core_id: str, enabled: bool) -> None:
        self._router.set_notification(core_id, enabled)

    def set_availability(self, core_id: str, available: bool) -> None:
        self._router.set_availability(core_id, available)

    def set_preference(
        self,
        core_id: str,
        *,
        weight: float | None = None,
        muted: bool | None = None,
    ) -> None:
        self._router.set_preference(core_id, weight=weight, muted=muted)

    def set_commitment(
        self, core_id: str, topic: str, *, active: bool = True
    ) -> None:
        self._router.set_commitment(core_id, topic, active=active)

    def set_budget(self, core_id: str, remaining: int) -> None:
        self._router.set_budget(core_id, remaining)

    def cancel_chain(self, chain_id: str) -> None:
        self._router.cancel_chain(chain_id)

    def terminate_core(self, core_id: str) -> None:
        self._router.terminate(core_id)

    def resume_core(self, core_id: str) -> None:
        self._router.resume(core_id)

    def terminate_all(self) -> None:
        self._router.terminate_all()

    def resume_all(self) -> None:
        self._router.resume_all()

    def participation_status(self, core_id: str):
        return self._router.status(core_id)


__all__ = [
    "AuthorView",
    "ConversationChannel",
    "ConversationResult",
    "ConversationTurn",
    "CoreParticipant",
    "CoreResponse",
    "CoreResponder",
    "MultiCoreConversation",
    "RelevanceSource",
    "chat_identity_from_profile",
    "coerce_core_response",
]
