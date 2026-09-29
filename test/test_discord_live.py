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
AUTO_CHANNEL = 323456789012345678
STALE_CHANNEL = 423456789012345678


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


def unpinned_provisioning() -> DiscordProvisioning:
    return DiscordProvisioning(
        enabled=True,
        owner_user_id=OWNER,
        bot_user_id=BOT,
        dm_channel_id=None,
        token="secret",
    )


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



def test_unpinned_live_runtime_accepts_authenticated_channel(tmp_path) -> None:
    config = Configuration(tmp_path / "state.sqlite3")
    conversation = FakeConversation()
    conversation.session_id = "desktop-session"

    channel = compose_live_discord_for_conversation(
        unpinned_provisioning(),
        conversation=conversation,
        configuration=config,
    )

    assert channel.runtime.config.dm_channel_id is None
    channel.runtime.pin_verified_channel(AUTO_CHANNEL)
    assert channel.runtime.config.dm_channel_id == AUTO_CHANNEL

    binding = ensure_verified_binding(channel.runtime)
    assert binding.channel_id == AUTO_CHANNEL
    assert binding.owner_user_id == OWNER
    assert binding.session_id == "desktop-session"


def test_verified_channel_replaces_and_revokes_stale_manual_pin(
    tmp_path,
) -> None:
    config = Configuration(tmp_path / "state.sqlite3")
    conversation = FakeConversation()
    conversation.session_id = "desktop-session"
    stale = DiscordProvisioning(
        enabled=True,
        owner_user_id=OWNER,
        bot_user_id=BOT,
        dm_channel_id=STALE_CHANNEL,
        token="secret",
    )

    channel = compose_live_discord_for_conversation(
        stale,
        conversation=conversation,
        configuration=config,
    )
    old_binding = ensure_verified_binding(channel.runtime)
    assert old_binding.channel_id == STALE_CHANNEL

    channel.runtime.pin_verified_channel(AUTO_CHANNEL)
    new_binding = ensure_verified_binding(channel.runtime)

    stale_after = channel.bindings.get(
        bot_user_id=BOT,
        channel_id=STALE_CHANNEL,
    )
    assert stale_after is not None
    assert stale_after.state is BindingState.REVOKED
    assert new_binding.channel_id == AUTO_CHANNEL
    assert channel.runtime.config.dm_channel_id == AUTO_CHANNEL


def test_unpinned_restart_recovers_unique_owner_binding(tmp_path) -> None:
    config = Configuration(tmp_path / "state.sqlite3")
    store = DiscordBindingStore(config.state_path)
    store.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=AUTO_CHANNEL,
        session_id="remembered-session",
    )

    assert (
        discord_bound_session_id(
            unpinned_provisioning(),
            configuration=config,
        )
        == "remembered-session"
    )
