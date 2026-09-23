"""Offline conversation bridge tests. No Discord network operations occur."""

from dataclasses import dataclass

import pytest

from sofia.discord.access import DiscordInboundFacts, SingleUserDiscordConfig
from sofia.discord.bridge import (
    BridgeDisposition,
    DiscordBridgeError,
    DiscordConversationBridge,
)
from sofia.discord.inbound import DiscordTextEvent, screen_text_dm
from sofia.discord.store import DiscordInboxStore, InboxAcceptResult, InboxClaimResult

OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 2002
MESSAGE = 1001


@dataclass
class FakeResponse:
    content: str


class FakeConversation:
    def __init__(self, *, content: str = "Sofía reply", fail: bool = False) -> None:
        self.session_id = "discord-session-1"
        self.content = content
        self.fail = fail
        self.calls = 0

    def respond(self, content: str) -> FakeResponse:
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated model failure")
        assert content == "Hello from Discord"
        return FakeResponse(self.content)


def seed(store: DiscordInboxStore) -> None:
    config = SingleUserDiscordConfig(
        OWNER,
        BOT,
        True,
        dm_channel_id=CHANNEL,
    )
    event = DiscordTextEvent(
        message_id=MESSAGE,
        channel_id=CHANNEL,
        content="Hello from Discord",
        facts=DiscordInboundFacts(
            OWNER,
            BOT,
            "dm",
            None,
            False,
            None,
            True,
        ),
    )
    assert store.accept(screen_text_dm(config, event)) is InboxAcceptResult.INSERTED


def test_bridge_stages_response_once(tmp_path) -> None:
    store = DiscordInboxStore(tmp_path / "state.sqlite3")
    seed(store)
    conversation = FakeConversation()
    bridge = DiscordConversationBridge(store=store, conversation=conversation)

    result = bridge.process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )
    assert result.disposition is BridgeDisposition.PREPARED
    assert result.outbox is not None
    assert result.outbox.content == "Sofía reply"
    assert result.outbox.session_id == "discord-session-1"
    assert conversation.calls == 1
    assert store.get(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    ).state == "response_prepared"

    second = bridge.process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )
    assert second.disposition is BridgeDisposition.ALREADY_PREPARED
    assert second.outbox is not None
    assert second.outbox.response_id == result.outbox.response_id
    assert conversation.calls == 1


def test_ambiguous_generation_failure_blocks_automatic_retry(tmp_path) -> None:
    store = DiscordInboxStore(tmp_path / "state.sqlite3")
    seed(store)
    conversation = FakeConversation(fail=True)
    bridge = DiscordConversationBridge(store=store, conversation=conversation)

    with pytest.raises(DiscordBridgeError):
        bridge.process(
            bot_user_id=BOT,
            channel_id=CHANNEL,
            message_id=MESSAGE,
        )

    assert conversation.calls == 1
    assert store.get(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    ).state == "outcome_unknown"

    result = bridge.process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )
    assert result.disposition is BridgeDisposition.OUTCOME_UNKNOWN
    assert conversation.calls == 1


def test_foreign_processing_claim_prevents_second_generator(tmp_path) -> None:
    store = DiscordInboxStore(tmp_path / "state.sqlite3")
    seed(store)
    assert store.claim_for_processing(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
        processing_token="worker-a",
    ) is InboxClaimResult.CLAIMED

    conversation = FakeConversation()
    bridge = DiscordConversationBridge(store=store, conversation=conversation)
    result = bridge.process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )

    assert result.disposition is BridgeDisposition.IN_PROGRESS
    assert conversation.calls == 0


def test_bridge_requires_active_conversation_session(tmp_path) -> None:
    store = DiscordInboxStore(tmp_path / "state.sqlite3")
    seed(store)
    conversation = FakeConversation()
    conversation.session_id = None
    bridge = DiscordConversationBridge(store=store, conversation=conversation)

    with pytest.raises(RuntimeError):
        bridge.process(
            bot_user_id=BOT,
            channel_id=CHANNEL,
            message_id=MESSAGE,
        )

    assert store.get(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    ).state == "received"
