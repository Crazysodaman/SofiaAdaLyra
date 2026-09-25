"""Durable Discord channel/session binding tests."""

import pytest

from sofia.discord.binding import BindingState, DiscordBindingStore

OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 2002


def test_binding_persists_and_rebind_increments_generation(tmp_path) -> None:
    path = tmp_path / "state.sqlite3"
    store = DiscordBindingStore(path)
    first = store.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-a",
    )
    assert first.state is BindingState.ACTIVE
    assert first.generation == 1

    reopened = DiscordBindingStore(path)
    loaded = reopened.get(bot_user_id=BOT, channel_id=CHANNEL)
    assert loaded == first

    second = reopened.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-b",
    )
    assert second.session_id == "session-b"
    assert second.generation == 2


def test_pause_resume_and_revoke_advance_generation(tmp_path) -> None:
    store = DiscordBindingStore(tmp_path / "state.sqlite3")
    bound = store.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-a",
    )
    paused = store.pause(bot_user_id=BOT, channel_id=CHANNEL)
    resumed = store.resume(bot_user_id=BOT, channel_id=CHANNEL)
    revoked = store.revoke(bot_user_id=BOT, channel_id=CHANNEL)

    assert bound.generation == 1
    assert paused.state is BindingState.PAUSED and paused.generation == 2
    assert resumed.state is BindingState.ACTIVE and resumed.generation == 3
    assert revoked.state is BindingState.REVOKED and revoked.generation == 4


def test_idempotent_same_state_control_does_not_bump_generation(tmp_path) -> None:
    store = DiscordBindingStore(tmp_path / "state.sqlite3")
    store.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-a",
    )
    first = store.pause(bot_user_id=BOT, channel_id=CHANNEL)
    second = store.pause(bot_user_id=BOT, channel_id=CHANNEL)
    assert second.generation == first.generation

    revoked = store.revoke(bot_user_id=BOT, channel_id=CHANNEL)
    again = store.revoke(bot_user_id=BOT, channel_id=CHANNEL)
    assert again.generation == revoked.generation


def test_revoked_binding_requires_supervised_rebind(tmp_path) -> None:
    store = DiscordBindingStore(tmp_path / "state.sqlite3")
    store.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-a",
    )
    store.revoke(bot_user_id=BOT, channel_id=CHANNEL)

    with pytest.raises(RuntimeError):
        store.resume(bot_user_id=BOT, channel_id=CHANNEL)

    rebound = store.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-b",
    )
    assert rebound.state is BindingState.ACTIVE
    assert rebound.session_id == "session-b"


def test_channel_cannot_silently_change_owner(tmp_path) -> None:
    store = DiscordBindingStore(tmp_path / "state.sqlite3")
    store.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-a",
    )
    with pytest.raises(ValueError):
        store.bind(
            bot_user_id=BOT,
            owner_user_id=111111111111111111,
            channel_id=CHANNEL,
            session_id="session-a",
        )
