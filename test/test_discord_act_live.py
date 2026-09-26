"""Live ACT-to-discord.py handoff tests with no real Discord network."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.act.delivery import DeliveryOutcome, DeliveryPayload
from sofia.discord.act_live import DiscordActTransportBridge
from sofia.discord.discordpy import create_discordpy_client
from sofia.discord.live import compose_live_discord
from sofia.discord.provisioning import DiscordProvisioning


OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 223456789012345678


class FakeIntents:
    def __init__(self) -> None:
        self.dm_messages = False

    @classmethod
    def none(cls):
        return cls()


class FakeAllowedMentions:
    @classmethod
    def none(cls):
        return cls()


class FakeDMChannel:
    def __init__(self, channel_id: int) -> None:
        self.id = channel_id
        self.sent: list[str] = []

    async def send(self, content: str, *, allowed_mentions) -> object:
        self.sent.append(content)
        return SimpleNamespace(id=7000 + len(self.sent))


class FakeGroupChannel:
    pass


class FakeOwner:
    def __init__(self, channel: FakeDMChannel) -> None:
        self.channel = channel

    async def create_dm(self) -> FakeDMChannel:
        return self.channel


class FakeClient:
    channel = FakeDMChannel(CHANNEL)

    def __init__(self, **kwargs) -> None:
        self.user = SimpleNamespace(id=BOT)
        self.closed = False

    async def fetch_user(self, owner_user_id: int) -> FakeOwner:
        assert owner_user_id == OWNER
        return FakeOwner(type(self).channel)

    async def close(self) -> None:
        self.closed = True


FAKE_DISCORD = SimpleNamespace(
    Client=FakeClient,
    Intents=FakeIntents,
    AllowedMentions=FakeAllowedMentions,
    DMChannel=FakeDMChannel,
    GroupChannel=FakeGroupChannel,
)


class FakeConversation:
    def __init__(self) -> None:
        self.session_id = None

    def respond(self, content: str):
        return SimpleNamespace(content="reply")


class FakeApplication:
    def __init__(self, configuration) -> None:
        self.configuration = configuration
        self.conversation = FakeConversation()

    def start(self, session_id=None):
        self.conversation.session_id = session_id or "session-live-act"

    def shutdown(self) -> None:
        pass


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


def test_transport_bridge_refuses_unbound_send() -> None:
    bridge = DiscordActTransportBridge(expected_channel_id=CHANNEL)
    with pytest.raises(RuntimeError, match="not ready"):
        bridge.send_chunk("hello")


def test_live_client_binds_verified_event_loop_and_delivers_from_worker(tmp_path) -> None:
    FakeClient.channel = FakeDMChannel(CHANNEL)
    composed = compose_live_discord(
        provisioning(),
        configuration=Configuration(tmp_path / "state.sqlite3"),
        application_factory=FakeApplication,
        act_recipient_id="sparks",
    )
    client = create_discordpy_client(
        composed.runtime,
        discord_module=FAKE_DISCORD,
    )
    payload = DeliveryPayload(
        attempt_id="attempt-live-1",
        message_id="message-live-1",
        recipient_id="sparks",
        channel="discord_dm",
        destination=str(CHANNEL),
        evidence_id="evidence-live-1",
        content="proactive hello",
    )

    async def scenario():
        await client.on_ready()
        assert composed.runtime.act_transport.connected is True
        assert composed.runtime.act_sender is not None

        result = await asyncio.to_thread(composed.runtime.act_sender, payload)

        assert result.outcome is DeliveryOutcome.DELIVERED
        assert result.receipt_id is not None
        assert FakeClient.channel.sent == ["proactive hello"]

        await client.on_disconnect()
        assert composed.runtime.act_transport.connected is False

    asyncio.run(scenario())
    composed.shutdown()


def test_transport_bridge_refuses_same_event_loop_thread() -> None:
    bridge = DiscordActTransportBridge(expected_channel_id=CHANNEL)

    async def scenario():
        async def send_async(content: str) -> int:
            return 9001

        bridge.bind(
            loop=asyncio.get_running_loop(),
            channel_id=CHANNEL,
            send_chunk_async=send_async,
        )
        with pytest.raises(RuntimeError, match="event-loop thread"):
            bridge.send_chunk("hello")
        bridge.unbind()

    asyncio.run(scenario())
