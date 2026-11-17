"""Android remote chat client with no on-device Core cognition or canonical DB."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sofia.platform.chat_clients.controller import (
    ChatClientController,
    ClientIdentityResult,
    ClientSnapshot,
    NotificationMode,
)
from sofia.platform.chat_clients.contracts import SendReceipt, SendStatus
from sofia.platform.chat_clients.drafts import ClientDraftStore
from sofia.platform.chat_clients.ports import ChatBackendPort

_MAX_RECEIPTS = 64
_MAX_ANDROID_DRAFTS = 32


@dataclass(frozen=True, slots=True)
class AndroidCapabilities:
    client_kind: str
    remote_transport: bool
    local_core_cognition: bool
    canonical_database: bool
    offline_private_state_share: bool


@dataclass(frozen=True, slots=True)
class MobileDeliveredReceipt:
    client_message_id: str
    room_id: str
    delivered: bool
    status: SendStatus
    observed_at: datetime


class AndroidRemoteChatSession:
    def __init__(
        self,
        *,
        backend: ChatBackendPort,
        client_id: str,
        drafts: ClientDraftStore | None = None,
        battery_percent: int = 100,
        metered: bool = False,
        foreground: bool = True,
        canonical_database_path: str | None = None,
        core_workspace_path: str | None = None,
        max_receipts: int = _MAX_RECEIPTS,
    ) -> None:
        if canonical_database_path is not None:
            raise ValueError(
                "Android client must not open a canonical database"
            )
        if core_workspace_path is not None:
            raise ValueError(
                "Android client must not load Core cognition or private state"
            )
        if type(battery_percent) is not int or not 0 <= battery_percent <= 100:
            raise ValueError("battery_percent must be 0..100")
        if type(metered) is not bool or type(foreground) is not bool:
            raise TypeError("metered and foreground must be bool")
        if type(max_receipts) is not int or not 1 <= max_receipts <= _MAX_RECEIPTS:
            raise ValueError("max_receipts must be 1..64")
        if drafts is not None and not isinstance(drafts, ClientDraftStore):
            raise TypeError("drafts must be a ClientDraftStore or None")
        if drafts is None:
            drafts = ClientDraftStore(
                client_id=client_id, max_entries=_MAX_ANDROID_DRAFTS,
            )
        elif drafts.client_id != client_id:
            raise ValueError("draft store belongs to another client id")
        self._controller = ChatClientController(
            backend=backend, client_id=client_id, drafts=drafts,
        )
        self._battery = battery_percent
        self._metered = metered
        self._foreground = foreground
        self._max_receipts = max_receipts
        self._receipts: dict[str, MobileDeliveredReceipt] = {}

    @property
    def controller(self) -> ChatClientController:
        return self._controller

    def capabilities(self) -> AndroidCapabilities:
        return AndroidCapabilities(
            client_kind="android",
            remote_transport=True,
            local_core_cognition=False,
            canonical_database=False,
            offline_private_state_share=False,
        )

    def update_environment(
        self, *, battery_percent: int | None = None, metered: bool | None = None,
        foreground: bool | None = None,
    ) -> None:
        if battery_percent is not None:
            if type(battery_percent) is not int or not 0 <= battery_percent <= 100:
                raise ValueError("battery_percent must be 0..100")
            self._battery = battery_percent
        if metered is not None:
            if type(metered) is not bool:
                raise TypeError("metered must be bool")
            self._metered = metered
        if foreground is not None:
            if type(foreground) is not bool:
                raise TypeError("foreground must be bool")
            self._foreground = foreground

    def poll_interval_seconds(self, *, connection_state: str = "connected") -> int:
        if connection_state == "offline":
            return 300
        if not self._foreground:
            return 180 if self._metered else 90
        if self._battery <= 10:
            return 120
        if self._battery <= 20:
            return 60
        if self._metered:
            return 30
        return 15

    def should_poll(self, *, now: datetime, last_poll: datetime | None) -> bool:
        if (
            not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError("now must be timezone-aware")
        if last_poll is None:
            return True
        if last_poll.tzinfo is None or last_poll.utcoffset() is None:
            raise ValueError("last_poll must be timezone-aware")
        elapsed = (now - last_poll).total_seconds()
        state = self._controller.connection.value
        return elapsed >= self.poll_interval_seconds(connection_state=state)

    def select_core(self, core) -> ClientIdentityResult:
        return self._controller.select_core(core)

    def snapshot(self) -> ClientSnapshot:
        return self._controller.snapshot()

    def open_room(self, room_id: str):
        return self._controller.open_room(room_id)

    def save_draft(self, content: str):
        return self._controller.save_draft(content)

    def send(self, body: str | None = None, *, reply_to: str | None = None) -> SendReceipt:
        receipt = self._controller.send(body, reply_to=reply_to)
        self._remember(receipt)
        return receipt

    def _remember(self, receipt: SendReceipt) -> None:
        delivered = receipt.status is SendStatus.SENT_CONFIRMED
        self._receipts[receipt.client_message_id] = MobileDeliveredReceipt(
            client_message_id=receipt.client_message_id,
            room_id=receipt.room_id,
            delivered=delivered,
            status=receipt.status,
            observed_at=datetime.now().astimezone(),
        )
        while len(self._receipts) > self._max_receipts:
            self._receipts.pop(next(iter(self._receipts)), None)

    def receipts(self) -> tuple[MobileDeliveredReceipt, ...]:
        return tuple(self._receipts.values())

    def catch_up(self) -> ClientIdentityResult:
        result = self._controller.reconnect()
        self._controller.drain_live_events()
        return result

    def set_notification(self, room_id: str, mode: NotificationMode) -> NotificationMode:
        return self._controller.set_notification(room_id, mode)
