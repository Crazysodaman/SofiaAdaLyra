"""Foreground live Discord composition tests without Discord network access."""

from pathlib import Path

import pytest

from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.discord.live import compose_live_discord
from sofia.discord.provisioning import DiscordProvisioning


OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 223456789012345678


class FakeConversation:
    def __init__(self) -> None:
        self.session_id = None

    def respond(self, content: str):
        return type("Response", (), {"content": "reply"})()


class FakeApplication:
    starts: list[str | None] = []

    def __init__(self, configuration) -> None:
        self.configuration = configuration
        self.conversation = FakeConversation()
        self.shutdown_called = False

    def start(self, session_id=None):
        type(self).starts.append(session_id)
        self.conversation.session_id = session_id or "new-discord-session"

    def shutdown(self) -> None:
        self.shutdown_called = True


class Configuration:
    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path


def provisioning() -> DiscordProvisioning:
    return DiscordProvisioning(
        enabled=True,
        owner_user_id=OWNER,
        bot_user_id=BOT,
        dm_channel_id=CHANNEL,
        token="secret",
    )


def test_first_live_composition_creates_durable_session_binding(tmp_path) -> None:
    FakeApplication.starts.clear()
    config = Configuration(tmp_path / "state.sqlite3")
    composed = compose_live_discord(
        provisioning(),
        configuration=config,
        application_factory=FakeApplication,
    )
    binding = composed.bindings.get(bot_user_id=BOT, channel_id=CHANNEL)
    assert binding is not None
    assert binding.session_id == "new-discord-session"
    assert binding.state is BindingState.ACTIVE
    assert FakeApplication.starts == [None]
    composed.shutdown()


def test_restart_resumes_bound_conversation_session(tmp_path) -> None:
    FakeApplication.starts.clear()
    config = Configuration(tmp_path / "state.sqlite3")
    first = compose_live_discord(
        provisioning(),
        configuration=config,
        application_factory=FakeApplication,
    )
    first.shutdown()

    second = compose_live_discord(
        provisioning(),
        configuration=config,
        application_factory=FakeApplication,
    )
    assert FakeApplication.starts == [None, "new-discord-session"]
    second.shutdown()


def test_revoked_binding_refuses_live_restart(tmp_path) -> None:
    FakeApplication.starts.clear()
    config = Configuration(tmp_path / "state.sqlite3")
    first = compose_live_discord(
        provisioning(),
        configuration=config,
        application_factory=FakeApplication,
    )
    first.shutdown()
    store = DiscordBindingStore(config.state_path)
    store.revoke(bot_user_id=BOT, channel_id=CHANNEL)

    with pytest.raises(RuntimeError, match="revoked"):
        compose_live_discord(
            provisioning(),
            configuration=config,
            application_factory=FakeApplication,
        )
