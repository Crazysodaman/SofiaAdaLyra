"""Choose a local or explicitly authenticated remote desktop application."""
from __future__ import annotations

import os
import re
from pathlib import Path
import sqlite3

from sofia.config import SofiaConfiguration
from sofia.ui.control_center import (
    DesktopControlSettingsStore,
    RemoteChatMode,
)
from sofia.ui.drafts import UIDraftStore
from sofia.ui.remote_transport import (
    PinnedRemoteConversation,
    RemoteChatClientConfig,
)
from sofia.ui.text import UITextClient
from sofia.ui.runtime_authority import RuntimeAuthorityState, RuntimeChatAuthorityStore
from sofia.state.sqlite_plane import SQLiteStatePlane


class RemoteDesktopApplication:
    """UITextClient host over an already-running remote Sofía conversation."""

    def __init__(
        self,
        *,
        configuration: SofiaConfiguration,
        conversation: PinnedRemoteConversation,
    ) -> None:
        self._configuration = configuration
        self._conversation = conversation
        self._drafts = UIDraftStore(configuration.state_path)
        self._text_ui = UITextClient(
            conversation=conversation,
            drafts=self._drafts,
            client_id="desktop-remote",
        )
        self._started = False

    @property
    def text_ui(self) -> UITextClient:
        return self._text_ui

    @property
    def conversation(self) -> PinnedRemoteConversation:
        return self._conversation

    def start(self, session_id: str | None = None):
        remote_session = self._conversation.session_id
        if session_id is not None and session_id != remote_session:
            raise ValueError("requested session does not match remote authoritative session")
        self._started = True
        return None

    def shutdown(self) -> None:
        if not self._started:
            return
        self._drafts.close()
        self._started = False


def _ensure_state(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with sqlite3.connect(path):
            pass


def _required_path(name: str) -> Path:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for remote desktop chat")
    return Path(value)


def create_desktop_application(configuration: SofiaConfiguration):
    """Return local SofiaApplication unless remote desktop chat is configured."""

    _ensure_state(configuration.state_path)
    settings = DesktopControlSettingsStore(configuration.state_path).load()

    endpoint = None
    pin = ""
    if settings.remote_chat_mode is RemoteChatMode.PINNED_ENDPOINT:
        endpoint = settings.pinned_chat_endpoint
        pin = os.environ.get("SOFIA_REMOTE_CHAT_SERVER_PIN", "").strip()
    elif settings.remote_chat_mode is RemoteChatMode.FLEET_AUTO:
        authority = RuntimeChatAuthorityStore(
            SQLiteStatePlane(configuration.state_path)
        ).current()
        if (
            authority is not None
            and authority.state is RuntimeAuthorityState.READY
        ):
            endpoint = authority.endpoint
            pin = authority.server_public_key_sha256

    if endpoint is None:
        from sofia.application import SofiaApplication
        return SofiaApplication(configuration)

    if re.fullmatch(r"[0-9a-f]{64}", pin) is None:
        raise RuntimeError(
            "SOFIA_REMOTE_CHAT_SERVER_PIN must be a lowercase SHA-256 digest"
        )

    remote = PinnedRemoteConversation(
        RemoteChatClientConfig.from_endpoint(
            endpoint,
            ca_file=_required_path("SOFIA_REMOTE_CHAT_CA_FILE"),
            client_certificate=_required_path("SOFIA_REMOTE_CHAT_CLIENT_CERT"),
            client_private_key=_required_path("SOFIA_REMOTE_CHAT_CLIENT_KEY"),
            expected_server_public_key_sha256=pin,
        )
    )
    return RemoteDesktopApplication(
        configuration=configuration,
        conversation=remote,
    )
