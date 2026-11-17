"""One remote chat client view over an authenticated social transport.

The controller never writes canonical state. It projects rooms, history,
memberships, delivery receipts and live events for exactly one explicitly
selected Core identity at a time. Switching Cores switches every scoped cache
and never merges histories.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Sequence
from uuid import uuid4

from sofia.platform.chat_clients.contracts import (
    ChatEvent,
    ChatMessage,
    ChatOffline,
    ChatPermissionDenied,
    ChatRoom,
    ConnectionState,
    CoreIdentity,
    MembershipStatus,
    MessageOrigin,
    MessagePage,
    RoomKind,
    RoomMembership,
    SendReceipt,
    SendStatus,
    normalize_core_id,
)
from sofia.platform.chat_clients.drafts import ClientDraft, ClientDraftStore
from sofia.platform.chat_clients.ports import ChatBackendPort

_MAX_PAGE = 200
_MAX_PENDING = 64


class NotificationMode(str, Enum):
    ALL = "all"
    MENTIONS = "mentions"
    MUTED = "muted"


class NoticeSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DENIED = "denied"
    OFFLINE = "offline"


class PendingSendStatus(str, Enum):
    PENDING = "pending"
    UNCERTAIN = "uncertain"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class ClientNotice:
    code: str
    message: str
    severity: NoticeSeverity


@dataclass(frozen=True, slots=True)
class PendingSend:
    client_message_id: str
    room_id: str
    body: str
    reply_to: str | None
    status: PendingSendStatus
    created_at: datetime


@dataclass(slots=True)
class _ChannelState:
    room: ChatRoom
    membership: RoomMembership | None
    unread: int = 0
    mentions: int = 0
    notification: NotificationMode = NotificationMode.ALL
    last_sequence: int = 0


@dataclass(frozen=True, slots=True)
class ChannelView:
    room_id: str
    kind: RoomKind
    title: str
    unread: int
    mentions: int
    notification: NotificationMode
    membership_status: MembershipStatus | None
    last_sequence: int
    active: bool


@dataclass(frozen=True, slots=True)
class MemberView:
    core_id: str
    display_name: str
    status: MembershipStatus
    epoch: int
    history_from_sequence: int
    is_selected_core: bool


@dataclass(frozen=True, slots=True)
class RenderedMessage:
    message_id: str
    sequence: int
    speaker_kind: MessageOrigin
    speaker_label: str
    body: str
    created_at: datetime
    reply_to: str | None


@dataclass(frozen=True, slots=True)
class ClientSnapshot:
    client_id: str
    selected_core: CoreIdentity | None
    connection: ConnectionState
    channels: tuple[ChannelView, ...]
    active_room_id: str | None
    messages: tuple[RenderedMessage, ...]
    draft: ClientDraft | None
    pending: tuple[PendingSend, ...]
    notices: tuple[ClientNotice, ...]
    has_older: bool


@dataclass(slots=True)
class _ScopedState:
    core: CoreIdentity
    channels: dict[str, _ChannelState] = field(default_factory=dict)
    messages: dict[str, list[ChatMessage]] = field(default_factory=dict)
    has_older: dict[str, bool] = field(default_factory=dict)
    event_cursor: int = 0
    active_room_id: str | None = None
    pending: dict[str, PendingSend] = field(default_factory=dict)
    notifications: list[ClientNotice] = field(default_factory=list)
    connection: ConnectionState = ConnectionState.OFFLINE


class ChatClientController:
    def __init__(
        self,
        *,
        backend: ChatBackendPort,
        client_id: str,
        drafts: ClientDraftStore | None = None,
        clock=None,
    ) -> None:
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("client_id must be nonempty")
        for method in (
            "list_cores", "connection_state", "list_rooms", "memberships",
            "history_page", "send_message", "events",
        ):
            if not callable(getattr(backend, method, None)):
                raise TypeError(f"backend must expose {method}()")
        if drafts is not None and not isinstance(drafts, ClientDraftStore):
            raise TypeError("drafts must be a ClientDraftStore or None")
        self._backend = backend
        self._client_id = client_id.strip()
        self._drafts = drafts
        self._clock = clock if clock is not None else (
            lambda: datetime.now(timezone.utc)
        )
        self._roster: dict[str, CoreIdentity] = {}
        self._selected: CoreIdentity | None = None
        self._state: _ScopedState | None = None
        self._global_notices: list[ClientNotice] = []

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def selected_core(self) -> CoreIdentity | None:
        return self._selected

    @property
    def connection(self) -> ConnectionState:
        if self._state is None:
            return ConnectionState.OFFLINE
        return self._state.connection

    def roster(self) -> tuple[CoreIdentity, ...]:
        rows = tuple(self._backend.list_cores())
        for row in rows:
            if not isinstance(row, CoreIdentity):
                raise TypeError("backend returned a non-CoreIdentity roster row")
        if len({row.normalized_core_id for row in rows}) != len(rows):
            raise ValueError("backend roster contains duplicate Core identities")
        self._roster = {row.normalized_core_id: row for row in rows}
        return rows

    def select_core(self, core: CoreIdentity | str) -> ClientIdentityResult:
        roster = {row.normalized_core_id: row for row in self.roster()}
        if isinstance(core, CoreIdentity):
            candidate = roster.get(core.normalized_core_id)
            if candidate is None:
                raise ChatPermissionDenied(
                    "CORE_NOT_ENROLLED", "selected Core is not in the enrolled roster"
                )
            if (
                candidate.generation != core.generation
                or candidate.platform_id != core.platform_id
            ):
                raise ChatPermissionDenied(
                    "STALE_GENERATION", "selected Core generation is not current"
                )
            selected = candidate
        elif isinstance(core, str):
            selected = roster.get(normalize_core_id(core))
            if selected is None:
                raise ChatPermissionDenied(
                    "CORE_NOT_ENROLLED", "selected Core is not in the enrolled roster"
                )
        else:
            raise TypeError("core must be CoreIdentity or core id text")

        previous = self._state
        self._selected = selected
        self._state = _ScopedState(
            core=selected,
            connection=self._backend.connection_state(selected.normalized_core_id),
        )
        if previous is not None and previous.core.core_id == selected.core_id:
            self._state.channels = previous.channels
            self._state.messages = previous.messages
            self._state.has_older = previous.has_older
            self._state.event_cursor = previous.event_cursor
            self._state.active_room_id = previous.active_room_id
            self._state.pending = previous.pending
            self._state.notifications = previous.notifications
        self._global_notices.clear()
        self._baseline_event_cursor(self._state)
        self.refresh_sidebar()
        return ClientIdentityResult(core=selected, connection=self._state.connection)

    def _baseline_event_cursor(self, state: _ScopedState) -> None:
        latest = 0
        try:
            events = self._backend.events(
                after_revision=0, core_id=state.core.normalized_core_id
            )
        except ChatOffline:
            state.connection = ConnectionState.OFFLINE
            return
        for event in events:
            if not isinstance(event, ChatEvent):
                raise TypeError("backend returned a non-ChatEvent")
            latest = max(latest, event.revision)
        state.event_cursor = latest

    def _require(self) -> _ScopedState:
        if self._selected is None or self._state is None:
            raise RuntimeError("select a Core before using the chat client")
        return self._state

    def _notice(
        self, code: str, message: str, severity: NoticeSeverity
    ) -> None:
        state = self._require()
        state.notifications.append(
            ClientNotice(code=code, message=message, severity=severity)
        )
        del state.notifications[:-20]

    def refresh_sidebar(self) -> tuple[ChannelView, ...]:
        state = self._require()
        if state.connection is ConnectionState.OFFLINE:
            return self._sidebar_views(state)
        try:
            rooms = tuple(self._backend.list_rooms(state.core.normalized_core_id))
        except ChatOffline:
            state.connection = ConnectionState.OFFLINE
            self._notice("OFFLINE", "connection lost; showing cached channels",
                         NoticeSeverity.OFFLINE)
            return self._sidebar_views(state)
        if any(not isinstance(room, ChatRoom) for room in rooms):
            raise TypeError("backend returned a non-ChatRoom row")
        rebuilt: dict[str, _ChannelState] = {}
        for room in rooms:
            membership = self._membership_for(state, room.room_id)
            if room.room_id in state.channels:
                existing = state.channels[room.room_id]
                existing.room = room
                existing.membership = membership
                rebuilt[room.room_id] = existing
            else:
                rebuilt[room.room_id] = _ChannelState(
                    room=room, membership=membership,
                )
        state.channels = rebuilt
        if (
            state.active_room_id is not None
            and state.active_room_id not in rebuilt
        ):
            state.active_room_id = None
        if state.active_room_id is None and rebuilt:
            first = next(iter(rebuilt.values()))
            state.active_room_id = first.room.room_id
            self._load_newest(state, first.room.room_id)
        return self._sidebar_views(state)

    def _membership_for(
        self, state: _ScopedState, room_id: str
    ) -> RoomMembership | None:
        try:
            rows = self._backend.memberships(
                state.core.normalized_core_id, room_id
            )
        except ChatOffline:
            state.connection = ConnectionState.OFFLINE
            return None
        for row in rows:
            if not isinstance(row, RoomMembership):
                raise TypeError("backend returned a non-RoomMembership row")
            if row.core_id.lower() == state.core.normalized_core_id:
                return row
        return None

    def _sidebar_views(self, state: _ScopedState) -> tuple[ChannelView, ...]:
        ordered = sorted(
            state.channels.values(),
            key=lambda item: (
                0 if item.room.kind is RoomKind.GENERAL else
                1 if item.room.kind is RoomKind.DIRECT else 2,
                item.room.title.casefold(),
                item.room.room_id,
            ),
        )
        return tuple(
            ChannelView(
                room_id=item.room.room_id,
                kind=item.room.kind,
                title=item.room.title,
                unread=item.unread,
                mentions=item.mentions,
                notification=item.notification,
                membership_status=(
                    item.membership.status if item.membership is not None else None
                ),
                last_sequence=item.last_sequence,
                active=item.room.room_id == state.active_room_id,
            )
            for item in ordered
        )

    def sidebar(self) -> tuple[ChannelView, ...]:
        state = self._require()
        self.refresh_sidebar()
        return self._sidebar_views(state)

    def _load_newest(self, state: _ScopedState, room_id: str, *, limit: int = 50) -> None:
        page = self._backend.history_page(
            state.core.normalized_core_id, room_id, limit=limit
        )
        if not isinstance(page, MessagePage):
            raise TypeError("backend returned a non-MessagePage")
        state.messages[room_id] = list(page.messages)
        state.has_older[room_id] = page.has_more
        channel = state.channels.get(room_id)
        if channel is not None:
            channel.last_sequence = page.newest_sequence or channel.last_sequence
            channel.unread = 0
            channel.mentions = 0

    def open_room(self, room_id: str) -> tuple[RenderedMessage, ...]:
        state = self._require()
        channel = state.channels.get(room_id)
        if channel is None:
            self.refresh_sidebar()
            channel = state.channels.get(room_id)
        if channel is None:
            raise ChatPermissionDenied(
                "ROOM_NOT_VISIBLE", "room is not visible to the selected Core"
            )
        if channel.membership is not None and channel.membership.status not in {
            MembershipStatus.ACTIVE,
        }:
            raise ChatPermissionDenied(
                "MEMBERSHIP_INACTIVE", "selected Core is not an active member"
            )
        if state.connection is ConnectionState.OFFLINE:
            self._notice("OFFLINE", "cannot refresh history while offline",
                         NoticeSeverity.OFFLINE)
            return self._render(state, room_id)
        state.active_room_id = room_id
        self._load_newest(state, room_id)
        return self._render(state, room_id)

    def load_older(self, *, limit: int = 50) -> tuple[RenderedMessage, ...]:
        state = self._require()
        if type(limit) is not int or not 1 <= limit <= _MAX_PAGE:
            raise ValueError("history limit must be 1..200")
        room_id = state.active_room_id
        if room_id is None:
            raise RuntimeError("open a room before loading older history")
        if not state.has_older.get(room_id, False):
            return self._render(state, room_id)
        existing = state.messages.get(room_id, [])
        before = existing[0].sequence if existing else None
        page = self._backend.history_page(
            state.core.normalized_core_id, room_id, before_sequence=before,
            limit=limit,
        )
        state.has_older[room_id] = page.has_more
        merged = list(page.messages) + existing
        state.messages[room_id] = self._dedupe(merged)
        return self._render(state, room_id)

    @staticmethod
    def _dedupe(messages: Sequence[ChatMessage]) -> list[ChatMessage]:
        seen: set[str] = set()
        result: list[ChatMessage] = []
        for message in messages:
            if message.message_id in seen:
                continue
            seen.add(message.message_id)
            result.append(message)
        return sorted(result, key=lambda item: item.sequence)

    def members(self, room_id: str) -> tuple[MemberView, ...]:
        state = self._require()
        rows = self._backend.memberships(
            state.core.normalized_core_id, room_id
        )
        names = {
            row.normalized_core_id: row.display_name for row in self.roster()
        }
        result = []
        for row in rows:
            if not isinstance(row, RoomMembership):
                raise TypeError("backend returned a non-RoomMembership row")
            result.append(MemberView(
                core_id=row.core_id.lower(),
                display_name=names.get(
                    row.core_id.lower(), f"Core {row.core_id[:8]}"
                ),
                status=row.status,
                epoch=row.epoch,
                history_from_sequence=row.history_from_sequence,
                is_selected_core=(
                    row.core_id.lower() == state.core.normalized_core_id
                ),
            ))
        return tuple(result)

    def set_notification(
        self, room_id: str, mode: NotificationMode
    ) -> NotificationMode:
        state = self._require()
        if not isinstance(mode, NotificationMode):
            raise TypeError("mode must be a NotificationMode")
        channel = state.channels.get(room_id)
        if channel is None:
            raise ChatPermissionDenied(
                "ROOM_NOT_VISIBLE", "room is not visible to the selected Core"
            )
        channel.notification = mode
        return mode

    def save_draft(self, content: str) -> ClientDraft | None:
        state = self._require()
        room_id = state.active_room_id
        if room_id is None:
            raise RuntimeError("open a room before saving a draft")
        if self._drafts is None:
            raise RuntimeError("client has no draft store")
        return self._drafts.save(
            core_id=state.core.normalized_core_id,
            room_id=room_id, content=content,
        )

    def draft(self) -> ClientDraft | None:
        state = self._require()
        room_id = state.active_room_id
        if room_id is None or self._drafts is None:
            return None
        return self._drafts.load(
            core_id=state.core.normalized_core_id, room_id=room_id
        )

    def send(self, body: str | None = None, *, reply_to: str | None = None) -> SendReceipt:
        state = self._require()
        room_id = state.active_room_id
        if room_id is None:
            raise RuntimeError("open a room before sending")
        if body is None:
            draft = self.draft()
            if draft is None:
                raise ValueError("there is no saved draft to send")
            body = draft.content
        if not isinstance(body, str):
            raise TypeError("body must be text")
        if not body.strip():
            raise ValueError("body must not be blank")
        if state.connection is ConnectionState.OFFLINE:
            self._notice(
                "OFFLINE", "message not sent; draft preserved",
                NoticeSeverity.OFFLINE,
            )
            raise ChatOffline("message not sent while offline")
        client_message_id = uuid4().hex
        try:
            receipt = self._backend.send_message(
                state.core.normalized_core_id, room_id, body,
                client_message_id=client_message_id, reply_to=reply_to,
            )
        except ChatPermissionDenied as error:
            self._notice(error.code, error.detail, NoticeSeverity.DENIED)
            return SendReceipt(
                client_message_id=client_message_id, room_id=room_id,
                status=SendStatus.DENIED, denial_code=error.code,
                detail=error.detail,
            )
        except ChatOffline:
            state.connection = ConnectionState.OFFLINE
            self._notice(
                "OFFLINE", "message outcome unknown; draft preserved",
                NoticeSeverity.OFFLINE,
            )
            raise
        self._record_receipt(state, receipt, body, reply_to)
        if receipt.status in {
            SendStatus.SENT_CONFIRMED, SendStatus.SENT_UNCONFIRMED,
            SendStatus.PENDING,
        } and self._drafts is not None:
            self._drafts.clear(
                core_id=state.core.normalized_core_id, room_id=room_id
            )
        return receipt

    def _record_receipt(
        self,
        state: _ScopedState,
        receipt: SendReceipt,
        body: str,
        reply_to: str | None,
    ) -> None:
        if receipt.status in {
            SendStatus.PENDING, SendStatus.SENT_UNCONFIRMED,
            SendStatus.OUTCOME_UNKNOWN,
        }:
            status = (
                PendingSendStatus.PENDING
                if receipt.status is SendStatus.PENDING
                else PendingSendStatus.UNCERTAIN
            )
            state.pending[receipt.client_message_id] = PendingSend(
                client_message_id=receipt.client_message_id,
                room_id=receipt.room_id, body=body, reply_to=reply_to,
                status=status, created_at=self._clock(),
            )
            if len(state.pending) > _MAX_PENDING:
                state.pending.pop(next(iter(state.pending)), None)
            return
        if receipt.status is SendStatus.DENIED:
            self._notice(
                receipt.denial_code or "DENIED",
                receipt.detail or "send denied", NoticeSeverity.DENIED,
            )
            return
        if receipt.message is not None:
            self._merge_message(state, receipt.message)
        state.pending.pop(receipt.client_message_id, None)

    def _merge_message(self, state: _ScopedState, message: ChatMessage) -> None:
        channel = state.channels.get(message.room_id)
        if channel is None:
            return
        cursor = state.messages.setdefault(message.room_id, [])
        if any(item.message_id == message.message_id for item in cursor):
            return
        cursor.append(message)
        cursor.sort(key=lambda item: item.sequence)
        channel.last_sequence = max(channel.last_sequence, message.sequence)
        if message.room_id == state.active_room_id:
            channel.unread = 0
            channel.mentions = 0

    def drain_live_events(self) -> tuple[ChannelView, ...]:
        state = self._require()
        selected = state.core.normalized_core_id
        events = tuple(self._backend.events(
            after_revision=state.event_cursor, core_id=selected,
        ))
        for event in events:
            if not isinstance(event, ChatEvent):
                raise TypeError("backend returned a non-ChatEvent")
            state.event_cursor = max(state.event_cursor, event.revision)
            if event.core_id.lower() != selected:
                continue
            channel = state.channels.get(event.room_id)
            if channel is None:
                continue
            if event.message is not None:
                message = event.message
                if message.room_id != event.room_id:
                    raise ValueError("event room and message room disagree")
                already = any(
                    item.message_id == message.message_id
                    for item in state.messages.get(message.room_id, [])
                )
                is_active = message.room_id == state.active_room_id
                is_own = (
                    message.sender_core_id is not None
                    and message.sender_core_id.lower() == selected
                )
                if not already:
                    self._merge_message(state, message)
                if not already and not is_own and not is_active:
                    channel.unread += 1
                    if selected in {
                        item.lower() for item in event.mentioned_core_ids
                    }:
                        channel.mentions += 1
                    if channel.notification is not NotificationMode.MUTED:
                        self._notice(
                            "NEW_MESSAGE",
                            f"{channel.room.title}: new message",
                            NoticeSeverity.INFO,
                        )
                elif not already and is_active and (
                    selected in {item.lower() for item in event.mentioned_core_ids}
                ):
                    channel.mentions = 0
            elif event.kind == "membership":
                try:
                    membership = self._membership_for(state, event.room_id)
                except ChatPermissionDenied:
                    membership = None
                channel.membership = membership
        return self._sidebar_views(state)

    def create_private_group(
        self, title: str, member_core_ids: Sequence[str]
    ) -> ChatRoom:
        state = self._require()
        room = self._backend.create_private_group(
            state.core.normalized_core_id, title=title,
            member_core_ids=tuple(member_core_ids),
        )
        if not isinstance(room, ChatRoom) or room.kind is not RoomKind.PRIVATE_GROUP:
            raise TypeError("backend did not return a private group")
        self.refresh_sidebar()
        return room

    def invite_to_group(self, room_id: str, invited_core_id: str) -> RoomMembership:
        state = self._require()
        return self._backend.invite_to_group(
            state.core.normalized_core_id, room_id, invited_core_id
        )

    def respond_to_invite(self, room_id: str, *, accept: bool) -> RoomMembership:
        state = self._require()
        result = self._backend.respond_to_invite(
            state.core.normalized_core_id, room_id, accept=accept
        )
        self.refresh_sidebar()
        return result

    def leave_room(self, room_id: str) -> RoomMembership:
        state = self._require()
        result = self._backend.leave_room(state.core.normalized_core_id, room_id)
        self.refresh_sidebar()
        return result

    def reconnect(self) -> ClientIdentityResult:
        state = self._require()
        state.connection = self._backend.connection_state(
            state.core.normalized_core_id
        )
        if state.connection is ConnectionState.CONNECTED:
            self._notice("RECONNECTED", "connection restored", NoticeSeverity.INFO)
            self.refresh_sidebar()
            self.drain_live_events()
        return ClientIdentityResult(
            core=state.core, connection=state.connection
        )

    def pending_sends(self) -> tuple[PendingSend, ...]:
        state = self._require()
        return tuple(state.pending.values())

    def notices(self) -> tuple[ClientNotice, ...]:
        state = self._require()
        return tuple(state.notifications)

    def _render(
        self, state: _ScopedState, room_id: str
    ) -> tuple[RenderedMessage, ...]:
        names = {
            row.normalized_core_id: row.display_name for row in self._roster.values()
        }
        rendered = []
        for message in state.messages.get(room_id, []):
            if message.origin is MessageOrigin.CORE:
                label = names.get(
                    (message.sender_core_id or "").lower(),
                    f"Core {(message.sender_core_id or 'unknown')[:8]}",
                )
            elif message.origin is MessageOrigin.OWNER:
                label = "Owner"
            else:
                label = "System"
            rendered.append(RenderedMessage(
                message_id=message.message_id,
                sequence=message.sequence,
                speaker_kind=message.origin,
                speaker_label=label,
                body=message.body,
                created_at=message.created_at,
                reply_to=message.reply_to,
            ))
        return tuple(rendered)

    def snapshot(self) -> ClientSnapshot:
        state = self._require()
        room_id = state.active_room_id
        channels = tuple(self._sidebar_views(state))
        return ClientSnapshot(
            client_id=self._client_id,
            selected_core=state.core,
            connection=state.connection,
            channels=channels,
            active_room_id=room_id,
            messages=self._render(state, room_id) if room_id else (),
            draft=self.draft(),
            pending=self.pending_sends(),
            notices=tuple(state.notifications),
            has_older=state.has_older.get(room_id, False) if room_id else False,
        )


@dataclass(frozen=True, slots=True)
class ClientIdentityResult:
    core: CoreIdentity
    connection: ConnectionState
