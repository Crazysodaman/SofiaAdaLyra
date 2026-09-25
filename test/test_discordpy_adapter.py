"""discord.py adapter contract tests with no real library or network."""

from types import SimpleNamespace

import pytest

import sofia.discord.discordpy as discordpy
from sofia.discord.discordpy import (
    DiscordPyMessageAdapter,
    build_dm_intents,
)


class FakeIntents:
    def __init__(self) -> None:
        self.dm_messages = False
        self.guild_messages = False
        self.message_content = False
        self.members = False
        self.presences = False

    @classmethod
    def none(cls):
        return cls()


class DMChannel:
    def __init__(self, channel_id: int) -> None:
        self.id = channel_id


class GroupChannel:
    def __init__(self, channel_id: int) -> None:
        self.id = channel_id


DISCORD = SimpleNamespace(
    Intents=FakeIntents,
    DMChannel=DMChannel,
    GroupChannel=GroupChannel,
)


def test_intents_request_only_direct_messages() -> None:
    intents = build_dm_intents(DISCORD)
    assert intents.dm_messages is True
    assert intents.guild_messages is False
    assert intents.message_content is False
    assert intents.members is False
    assert intents.presences is False


def test_authenticated_dm_conversion_uses_numeric_identity() -> None:
    message = SimpleNamespace(
        id=1001,
        channel=DMChannel(2002),
        content="hello",
        author=SimpleNamespace(id=3003, bot=False),
        guild=None,
        webhook_id=None,
        attachments=[],
    )
    event = DiscordPyMessageAdapter(DISCORD).to_event(
        message,
        bot_user_id=4004,
    )
    assert event.message_id == 1001
    assert event.channel_id == 2002
    assert event.content == "hello"
    assert event.facts.author_user_id == 3003
    assert event.facts.recipient_user_id == 4004
    assert event.facts.channel_kind == "dm"
    assert event.facts.authenticated_source is True


def test_group_dm_is_not_mislabeled_private_dm() -> None:
    message = SimpleNamespace(
        id=1001,
        channel=GroupChannel(2002),
        content="hello",
        author=SimpleNamespace(id=3003, bot=False),
        guild=None,
        webhook_id=None,
        attachments=[],
    )
    event = DiscordPyMessageAdapter(DISCORD).to_event(
        message,
        bot_user_id=4004,
    )
    assert event.facts.channel_kind == "group"


class FakeRunClient:
    def __init__(self, *, ready: bool, startup_error=None) -> None:
        self._sofia_ready = ready
        self._sofia_startup_error = startup_error
        self.tokens = []

    def run(self, token: str) -> None:
        self.tokens.append(token)


def test_runner_surfaces_on_ready_startup_failure(monkeypatch) -> None:
    client = FakeRunClient(
        ready=False,
        startup_error=RuntimeError("configured DM channel mismatch"),
    )
    monkeypatch.setattr(discordpy, "create_discordpy_client", lambda runtime: client)

    with pytest.raises(RuntimeError, match="configured DM channel mismatch"):
        discordpy.run_discordpy_client("secret-token", object())

    assert client.tokens == ["secret-token"]


def test_runner_rejects_clean_exit_before_authenticated_readiness(monkeypatch) -> None:
    client = FakeRunClient(ready=False)
    monkeypatch.setattr(discordpy, "create_discordpy_client", lambda runtime: client)

    with pytest.raises(RuntimeError, match="before authenticated readiness"):
        discordpy.run_discordpy_client("secret-token", object())
