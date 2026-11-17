"""Remote-only desktop chat adapter.

The existing desktop/workbench clients are preserved. This adapter gives a
future desktop surface one authenticated remote boundary and refuses to carry a
local Core or a private canonical database.
"""
from __future__ import annotations

from dataclasses import dataclass

from sofia.platform.chat_clients.controller import (
    ChatClientController,
    ClientIdentityResult,
    ClientSnapshot,
    NotificationMode,
)
from sofia.platform.chat_clients.contracts import ChatOffline, SendReceipt
from sofia.platform.chat_clients.drafts import ClientDraftStore
from sofia.platform.chat_clients.ports import ChatBackendPort
from sofia.platform.chat_clients.render import render_chat_screen


@dataclass(frozen=True, slots=True)
class DesktopClientCapabilities:
    client_kind: str
    remote_transport: bool
    local_core_cognition: bool
    canonical_database: bool
    private_core_state: bool


class RemoteDesktopChatClient:
    def __init__(
        self,
        *,
        backend: ChatBackendPort,
        client_id: str,
        drafts: ClientDraftStore | None = None,
        transport_kind: str = "remote",
        canonical_database_path: str | None = None,
        core_workspace_path: str | None = None,
    ) -> None:
        if transport_kind != "remote":
            raise ValueError("desktop chat client is remote-only")
        if canonical_database_path is not None:
            raise ValueError(
                "desktop chat client must not open a canonical database"
            )
        if core_workspace_path is not None:
            raise ValueError(
                "desktop chat client must not load a private Core workspace"
            )
        self._controller = ChatClientController(
            backend=backend, client_id=client_id, drafts=drafts,
        )

    @property
    def controller(self) -> ChatClientController:
        return self._controller

    def capabilities(self) -> DesktopClientCapabilities:
        return DesktopClientCapabilities(
            client_kind="desktop",
            remote_transport=True,
            local_core_cognition=False,
            canonical_database=False,
            private_core_state=False,
        )

    def select_core(self, core) -> ClientIdentityResult:
        return self._controller.select_core(core)

    def snapshot(self) -> ClientSnapshot:
        return self._controller.snapshot()

    def send(self, body: str | None = None, *, reply_to: str | None = None) -> SendReceipt:
        return self._controller.send(body, reply_to=reply_to)

    def open_room(self, room_id: str):
        return self._controller.open_room(room_id)

    def set_notification(self, room_id: str, mode: NotificationMode) -> NotificationMode:
        return self._controller.set_notification(room_id, mode)

    def render(self, width: int = 100) -> str:
        return render_chat_screen(self.snapshot(), width=width)

    def reconnect(self) -> ClientIdentityResult:
        return self._controller.reconnect()

    @staticmethod
    def offline_error() -> str:
        return str(ChatOffline("desktop client is offline"))
