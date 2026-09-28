"""Foreground live Discord composition tests without Discord network access."""

import asyncio
from pathlib import Path
from threading import Event

import pytest

from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.discord.discordpy import ensure_verified_binding
from sofia.discord.live import (
    DiscordBackgroundService,
    compose_live_discord,
    compose_live_discord_for_conversation,
    discord_bound_session_id,
    run_live_discord,
)
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


def test_first_live_composition_defers_binding_until_discord_verification(tmp_path) -> None:
    FakeApplication.starts.clear()
    config = Configuration(tmp_path / "state.sqlite3")
    composed = compose_live_discord(
        provisioning(),
        configuration=config,
        application_factory=FakeApplication,
    )
    assert composed.bindings.get(bot_user_id=BOT, channel_id=CHANNEL) is None
    assert FakeApplication.starts == [None]

    binding = ensure_verified_binding(composed.runtime)
    assert binding.session_id == "new-discord-session"
    assert binding.state is BindingState.ACTIVE
    assert binding.generation == 1

    same = ensure_verified_binding(composed.runtime)
    assert same.generation == 1
    composed.shutdown()


def test_restart_resumes_bound_conversation_session(tmp_path) -> None:
    FakeApplication.starts.clear()
    config = Configuration(tmp_path / "state.sqlite3")
    first = compose_live_discord(
        provisioning(),
        configuration=config,
        application_factory=FakeApplication,
    )
    ensure_verified_binding(first.runtime)
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
    ensure_verified_binding(first.runtime)
    first.shutdown()
    store = DiscordBindingStore(config.state_path)
    store.revoke(bot_user_id=BOT, channel_id=CHANNEL)

    with pytest.raises(RuntimeError, match="revoked"):
        compose_live_discord(
            provisioning(),
            configuration=config,
            application_factory=FakeApplication,
        )


def test_foreground_runner_always_shuts_application_down(tmp_path) -> None:
    FakeApplication.starts.clear()
    config = Configuration(tmp_path / "state.sqlite3")
    applications = []

    def factory(configuration):
        app = FakeApplication(configuration)
        applications.append(app)
        return app

    def failing_runner(token, runtime):
        assert token == "secret"
        raise RuntimeError("simulated Discord transport failure")

    with pytest.raises(RuntimeError, match="simulated Discord transport failure"):
        run_live_discord(
            provisioning(),
            configuration=config,
            application_factory=factory,
            runner=failing_runner,
        )

    assert len(applications) == 1
    assert applications[0].shutdown_called is True


def test_existing_application_channel_reuses_active_conversation(tmp_path) -> None:
    config = Configuration(tmp_path / "state.sqlite3")
    conversation = FakeConversation()
    conversation.session_id = "desktop-session"

    channel = compose_live_discord_for_conversation(
        provisioning(),
        conversation=conversation,
        configuration=config,
    )

    assert channel.runtime.session_id == "desktop-session"
    binding = ensure_verified_binding(channel.runtime)
    assert binding.session_id == "desktop-session"
    assert (
        discord_bound_session_id(
            provisioning(),
            configuration=config,
        )
        == "desktop-session"
    )


def test_existing_application_channel_rejects_different_bound_session(
    tmp_path,
) -> None:
    config = Configuration(tmp_path / "state.sqlite3")
    first = FakeConversation()
    first.session_id = "bound-session"
    channel = compose_live_discord_for_conversation(
        provisioning(),
        conversation=first,
        configuration=config,
    )
    ensure_verified_binding(channel.runtime)

    second = FakeConversation()
    second.session_id = "different-session"
    with pytest.raises(RuntimeError, match="does not match Discord binding"):
        compose_live_discord_for_conversation(
            provisioning(),
            conversation=second,
            configuration=config,
        )


def test_background_service_starts_and_stops_without_owning_application(
    tmp_path,
) -> None:
    config = Configuration(tmp_path / "state.sqlite3")
    conversation = FakeConversation()
    conversation.session_id = "desktop-session"
    channel = compose_live_discord_for_conversation(
        provisioning(),
        conversation=conversation,
        configuration=config,
    )

    created = []
    started = Event()

    class FakeAsyncClient:
        def __init__(self) -> None:
            self.closed = False
            self._sofia_ready = False
            self._sofia_startup_error = None
            self.token = None

        async def start(self, token):
            self.token = token
            self._sofia_ready = True
            started.set()
            while not self.closed:
                await asyncio.sleep(0.01)

        async def close(self):
            self.closed = True

    def factory(runtime):
        assert runtime is channel.runtime
        client = FakeAsyncClient()
        created.append(client)
        return client

    service = DiscordBackgroundService(
        provisioning(),
        channel,
        client_factory=factory,
    )
    service.start()

    assert started.wait(timeout=2)
    assert service.running
    assert created[0].token == "secret"

    service.stop()

    assert not service.running
    assert created[0].closed is True
    assert service.error is None
