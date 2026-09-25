"""Offline conversation bridge tests. No Discord network operations occur."""

from dataclasses import dataclass

import pytest

from sofia.discord.access import DiscordInboundFacts, SingleUserDiscordConfig
from sofia.discord.binding import DiscordBindingStore
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
    def __init__(
        self,
        *,
        content: str = "Sofía reply",
        fail: bool = False,
        on_respond=None,
    ) -> None:
        self.session_id = "discord-session-1"
        self.content = content
        self.fail = fail
        self.on_respond = on_respond
        self.calls = 0

    def respond(self, content: str) -> FakeResponse:
        self.calls += 1
        if self.on_respond is not None:
            self.on_respond()
        if self.fail:
            raise RuntimeError("simulated model failure")
        assert content == "Hello from Discord"
        return FakeResponse(self.content)


def setup_channel(tmp_path):
    path = tmp_path / "state.sqlite3"
    store = DiscordInboxStore(path)
    bindings = DiscordBindingStore(path)
    bindings.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="discord-session-1",
    )
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
    return store, bindings


def test_bridge_stages_response_once_with_binding_snapshot(tmp_path) -> None:
    store, bindings = setup_channel(tmp_path)
    conversation = FakeConversation()
    bridge = DiscordConversationBridge(
        store=store,
        bindings=bindings,
        conversation=conversation,
    )

    result = bridge.process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )
    assert result.disposition is BridgeDisposition.PREPARED
    assert result.outbox is not None
    assert result.outbox.content == "Sofía reply"
    assert conversation.calls == 1

    authority = bindings.outbox_binding(result.outbox.response_id)
    assert authority is not None
    assert authority.owner_user_id == OWNER
    assert authority.binding_generation == 1

    second = bridge.process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )
    assert second.disposition is BridgeDisposition.ALREADY_PREPARED
    assert conversation.calls == 1


def test_paused_binding_blocks_generation(tmp_path) -> None:
    store, bindings = setup_channel(tmp_path)
    bindings.pause(bot_user_id=BOT, channel_id=CHANNEL)
    conversation = FakeConversation()
    bridge = DiscordConversationBridge(
        store=store,
        bindings=bindings,
        conversation=conversation,
    )
    result = bridge.process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )
    assert result.disposition is BridgeDisposition.PAUSED
    assert conversation.calls == 0


def test_binding_change_during_generation_blocks_outbound_authority(tmp_path) -> None:
    store, bindings = setup_channel(tmp_path)
    conversation = FakeConversation(
        on_respond=lambda: bindings.pause(
            bot_user_id=BOT,
            channel_id=CHANNEL,
        )
    )
    bridge = DiscordConversationBridge(
        store=store,
        bindings=bindings,
        conversation=conversation,
    )
    result = bridge.process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )
    assert result.disposition is BridgeDisposition.BLOCKED
    assert result.outbox is not None
    assert bindings.outbox_binding(result.outbox.response_id) is None
    assert conversation.calls == 1


def test_ambiguous_generation_failure_blocks_automatic_retry(tmp_path) -> None:
    store, bindings = setup_channel(tmp_path)
    conversation = FakeConversation(fail=True)
    bridge = DiscordConversationBridge(
        store=store,
        bindings=bindings,
        conversation=conversation,
    )

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
    store, bindings = setup_channel(tmp_path)
    assert store.claim_for_processing(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
        processing_token="worker-a",
    ) is InboxClaimResult.CLAIMED

    conversation = FakeConversation()
    bridge = DiscordConversationBridge(
        store=store,
        bindings=bindings,
        conversation=conversation,
    )
    result = bridge.process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )

    assert result.disposition is BridgeDisposition.IN_PROGRESS
    assert conversation.calls == 0
