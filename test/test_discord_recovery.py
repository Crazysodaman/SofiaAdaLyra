"""Restart recovery tests for generation and outbound delivery ambiguity."""

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
from sofia.discord.outbound import DiscordOutboundGate
from sofia.discord.store import DiscordInboxStore, InboxAcceptResult, InboxClaimResult

OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 223456789012345678
MESSAGE = 323456789012345678


@dataclass
class Response:
    content: str


class Conversation:
    session_id = "discord-session"

    def respond(self, content: str) -> Response:
        return Response("reply")


def accepted_inbox(path):
    inbox = DiscordInboxStore(path)
    config = SingleUserDiscordConfig(OWNER, BOT, True, dm_channel_id=CHANNEL)
    event = DiscordTextEvent(
        message_id=MESSAGE,
        channel_id=CHANNEL,
        content="hello",
        facts=DiscordInboundFacts(OWNER, BOT, "dm", None, False, None, True),
    )
    assert inbox.accept(screen_text_dm(config, event)) is InboxAcceptResult.INSERTED
    return inbox, config


def test_interrupted_generation_becomes_outcome_unknown_on_restart(tmp_path) -> None:
    path = tmp_path / "state.sqlite3"
    inbox, _config = accepted_inbox(path)
    assert inbox.claim_for_processing(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
        processing_token="worker-before-crash",
    ) is InboxClaimResult.CLAIMED

    reopened = DiscordInboxStore(path)
    assert reopened.recover_interrupted_processing() == 1
    record = reopened.get(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )
    assert record is not None
    assert record.state == "outcome_unknown"
    assert reopened.recover_interrupted_processing() == 0


def test_interrupted_network_send_is_never_automatically_retried(tmp_path) -> None:
    path = tmp_path / "state.sqlite3"
    inbox, config = accepted_inbox(path)
    bindings = DiscordBindingStore(path)
    bindings.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="discord-session",
    )
    outbox = DiscordConversationBridge(
        store=inbox,
        bindings=bindings,
        conversation=Conversation(),
    ).process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    ).outbox
    assert outbox is not None

    deliveries = DiscordDeliveryStore(path)
    records = deliveries.prepare(outbox, chunk_discord_text(outbox.content))
    assert len(records) == 1
    assert deliveries.claim_send(
        response_id=outbox.response_id,
        chunk_index=0,
        send_token="sender-before-crash",
    )

    reopened = DiscordDeliveryStore(path)
    assert reopened.recover_interrupted() == 1
    recovered = reopened.list(outbox.response_id)
    assert recovered[0].state is DeliveryState.OUTCOME_UNKNOWN
    assert recovered[0].send_in_progress is False

    calls = 0

    async def should_not_send(content: str) -> int:
        nonlocal calls
        calls += 1
        return 999999999999999999

    sender = DiscordSafeSender(
        gate=DiscordOutboundGate(config=config, bindings=bindings),
        deliveries=reopened,
    )
    result = asyncio.run(sender.send(outbox, send_chunk=should_not_send))
    assert result.disposition is DeliveryDisposition.OUTCOME_UNKNOWN
    assert calls == 0


def test_prepared_outbox_is_discoverable_for_safe_restart_delivery(tmp_path) -> None:
    path = tmp_path / "state.sqlite3"
    inbox, _config = accepted_inbox(path)
    bindings = DiscordBindingStore(path)
    bindings.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="discord-session",
    )
    outbox = DiscordConversationBridge(
        store=inbox,
        bindings=bindings,
        conversation=Conversation(),
    ).process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    ).outbox
    assert outbox is not None

    pending = inbox.list_outbox(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        states=("prepared",),
    )
    assert pending == (outbox,)
