"""Crash-aware Discord delivery tests without Discord network access."""

import asyncio
from dataclasses import dataclass

from sofia.discord.access import DiscordInboundFacts, SingleUserDiscordConfig
from sofia.discord.binding import DiscordBindingStore
from sofia.discord.bridge import DiscordConversationBridge
from sofia.discord.delivery import (
    DeliveryDisposition,
    DeliveryState,
    DiscordDeliveryStore,
    DiscordSafeSender,
    chunk_discord_text,
)
from sofia.discord.inbound import DiscordTextEvent, screen_text_dm
from sofia.discord.outbound import DiscordOutboundGate, OutboundDenial
from sofia.discord.store import DiscordInboxStore

OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 2002
MESSAGE = 1001


@dataclass
class Response:
    content: str


class Conversation:
    session_id = "session-a"

    def __init__(self, content: str) -> None:
        self.content = content

    def respond(self, content: str) -> Response:
        return Response(self.content)


def prepared(tmp_path, content: str):
    path = tmp_path / "state.sqlite3"
    inbox = DiscordInboxStore(path)
    bindings = DiscordBindingStore(path)
    bindings.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-a",
    )
    config = SingleUserDiscordConfig(OWNER, BOT, True, dm_channel_id=CHANNEL)
    event = DiscordTextEvent(
        message_id=MESSAGE,
        channel_id=CHANNEL,
        content="hello",
        facts=DiscordInboundFacts(OWNER, BOT, "dm", None, False, None, True),
    )
    inbox.accept(screen_text_dm(config, event))
    result = DiscordConversationBridge(
        store=inbox,
        bindings=bindings,
        conversation=Conversation(content),
    ).process(bot_user_id=BOT, channel_id=CHANNEL, message_id=MESSAGE)
    assert result.outbox is not None
    gate = DiscordOutboundGate(config=config, bindings=bindings)
    deliveries = DiscordDeliveryStore(path)
    return result.outbox, bindings, DiscordSafeSender(
        gate=gate,
        deliveries=deliveries,
    ), deliveries


def test_chunking_preserves_exact_content() -> None:
    content = ("alpha " * 450) + "\n" + ("β" * 2300)
    chunks = chunk_discord_text(content)
    assert all(1 <= len(chunk) <= 2000 for chunk in chunks)
    assert "".join(chunks) == content


def test_sender_records_all_chunks_and_completes_outbox(tmp_path) -> None:
    outbox, _bindings, sender, deliveries = prepared(tmp_path, "x" * 4500)
    sent: list[str] = []

    async def send_chunk(content: str) -> int:
        sent.append(content)
        return 5000 + len(sent)

    result = asyncio.run(sender.send(outbox, send_chunk=send_chunk))
    assert result.disposition is DeliveryDisposition.SENT
    records = deliveries.list(outbox.response_id)
    assert len(records) == 3
    assert all(record.state is DeliveryState.SENT for record in records)
    assert sent == [record.content for record in records]


def test_sender_does_not_repeat_acknowledged_chunks(tmp_path) -> None:
    outbox, _bindings, sender, deliveries = prepared(tmp_path, "y" * 2500)
    calls = 0

    async def send_chunk(content: str) -> int:
        nonlocal calls
        calls += 1
        return 6000 + calls

    first = asyncio.run(sender.send(outbox, send_chunk=send_chunk))
    assert first.disposition is DeliveryDisposition.SENT
    second = asyncio.run(sender.send(outbox, send_chunk=send_chunk))
    assert second.disposition is DeliveryDisposition.ALREADY_SENT
    assert calls == 2
    assert all(
        record.state is DeliveryState.SENT
        for record in deliveries.list(outbox.response_id)
    )


def test_pause_between_chunks_blocks_remainder(tmp_path) -> None:
    outbox, bindings, sender, deliveries = prepared(tmp_path, "z" * 2500)
    calls = 0

    async def send_chunk(content: str) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            bindings.pause(bot_user_id=BOT, channel_id=CHANNEL)
        return 7000 + calls

    result = asyncio.run(sender.send(outbox, send_chunk=send_chunk))
    assert result.disposition is DeliveryDisposition.BLOCKED
    assert result.denial is OutboundDenial.PAUSED
    records = deliveries.list(outbox.response_id)
    assert records[0].state is DeliveryState.SENT
    assert records[1].state is DeliveryState.PREPARED
    assert calls == 1


def test_ambiguous_send_failure_is_not_automatically_retried(tmp_path) -> None:
    outbox, _bindings, sender, deliveries = prepared(tmp_path, "reply")
    calls = 0

    async def send_chunk(content: str) -> int:
        nonlocal calls
        calls += 1
        raise TimeoutError("provider outcome unknown")

    first = asyncio.run(sender.send(outbox, send_chunk=send_chunk))
    second = asyncio.run(sender.send(outbox, send_chunk=send_chunk))
    assert first.disposition is DeliveryDisposition.OUTCOME_UNKNOWN
    assert second.disposition is DeliveryDisposition.OUTCOME_UNKNOWN
    assert calls == 1
    assert deliveries.list(outbox.response_id)[0].state is DeliveryState.OUTCOME_UNKNOWN
