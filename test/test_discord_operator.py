"""Local Discord operator controls never require a bot token or network."""

from pathlib import Path

import pytest

from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.discord.operator import control_discord, inspect_discord_state
from sofia.discord.provisioning import DiscordIdentity


OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 223456789012345678


class Configuration:
    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path


def identity() -> DiscordIdentity:
    return DiscordIdentity(
        owner_user_id=OWNER,
        bot_user_id=BOT,
        dm_channel_id=CHANNEL,
    )


def enrolled(tmp_path):
    config = Configuration(tmp_path / "state.sqlite3")
    store = DiscordBindingStore(config.state_path)
    store.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="discord-session",
    )
    return config


def test_status_reports_local_binding_without_token(tmp_path) -> None:
    config = enrolled(tmp_path)
    status = inspect_discord_state(identity(), configuration=config)
    assert status.state is BindingState.ACTIVE
    assert status.session_id == "discord-session"
    assert status.generation == 1
    assert status.pending_outbox == 0
    assert status.unknown_generation_outcomes == 0
    assert status.unknown_delivery_outcomes == 0


def test_pause_and_resume_are_supervised_local_controls(tmp_path) -> None:
    config = enrolled(tmp_path)
    paused = control_discord("pause", identity(), configuration=config)
    assert paused.state is BindingState.PAUSED
    assert paused.generation == 2

    resumed = control_discord("resume", identity(), configuration=config)
    assert resumed.state is BindingState.ACTIVE
    assert resumed.generation == 3


def test_revoke_is_persistent_and_not_resumable(tmp_path) -> None:
    config = enrolled(tmp_path)
    revoked = control_discord("revoke", identity(), configuration=config)
    assert revoked.state is BindingState.REVOKED

    with pytest.raises(RuntimeError):
        control_discord("resume", identity(), configuration=config)


def test_wrong_owner_cannot_operate_binding(tmp_path) -> None:
    config = enrolled(tmp_path)
    wrong = DiscordIdentity(
        owner_user_id=111111111111111111,
        bot_user_id=BOT,
        dm_channel_id=CHANNEL,
    )
    with pytest.raises(RuntimeError, match="owner"):
        control_discord("pause", wrong, configuration=config)
