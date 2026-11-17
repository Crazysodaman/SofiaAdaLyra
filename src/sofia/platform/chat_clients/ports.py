"""Ports a remote chat client depends on.

The canonical/federation implementation supplies these methods behind an
authenticated transport. Client code never opens a canonical database, starts
Core cognition, or treats a cached identity as authenticated.
"""
from __future__ import annotations

from typing import Protocol, Sequence

from sofia.platform.chat_clients.contracts import (
    ChatEvent,
    ChatRoom,
    ConnectionState,
    CoreIdentity,
    MessagePage,
    RoomMembership,
    SendReceipt,
)


class CoreRosterPort(Protocol):
    def list_cores(self) -> Sequence[CoreIdentity]: ...


class ChatBackendPort(Protocol):
    def list_cores(self) -> Sequence[CoreIdentity]: ...

    def connection_state(self, core_id: str) -> ConnectionState: ...

    def list_rooms(self, core_id: str) -> Sequence[ChatRoom]: ...

    def memberships(
        self, core_id: str, room_id: str
    ) -> Sequence[RoomMembership]: ...

    def history_page(
        self,
        core_id: str,
        room_id: str,
        *,
        before_sequence: int | None = None,
        limit: int = 50,
    ) -> MessagePage: ...

    def send_message(
        self,
        core_id: str,
        room_id: str,
        body: str,
        *,
        client_message_id: str,
        reply_to: str | None = None,
        audience: str | None = None,
    ) -> SendReceipt: ...

    def create_private_group(
        self,
        core_id: str,
        *,
        title: str,
        member_core_ids: Sequence[str],
    ) -> ChatRoom: ...

    def invite_to_group(
        self, core_id: str, room_id: str, invited_core_id: str
    ) -> RoomMembership: ...

    def respond_to_invite(
        self, core_id: str, room_id: str, *, accept: bool
    ) -> RoomMembership: ...

    def leave_room(self, core_id: str, room_id: str) -> RoomMembership: ...

    def events(
        self, *, after_revision: int, core_id: str | None = None
    ) -> Sequence[ChatEvent]: ...


class DraftPersistencePort(Protocol):
    def load_draft(self, *, client_id: str, core_id: str, room_id: str) -> str | None:
        ...

    def save_draft(
        self, *, client_id: str, core_id: str, room_id: str, content: str
    ) -> None: ...

    def clear_draft(self, *, client_id: str, core_id: str, room_id: str) -> None:
        ...


class ClockPort(Protocol):
    def __call__(self): ...
