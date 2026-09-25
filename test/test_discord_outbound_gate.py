"""Final Discord outbound authorization tests."""

from dataclasses import replace

from sofia.discord.access import DiscordInboundFacts, SingleUserDiscordConfig
from sofia.discord.binding import DiscordBindingStore
from sofia.discord.bridge import DiscordConversationBridge
from sofia.discord.inbound import DiscordTextEvent, screen_text_dm
from sofia.discord.outbound import (
    DiscordOutboundGate,
    OutboundDenial,
)
from sofia.discord.store import DiscordInboxStore

OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 2002
MESSAGE = 1001


class Response:
    content = "Ready to send"


class Conversation:
    session_id = "session-a"

    def respond(self, content: str) -> Response:
        return Response()


def prepared(tmp_path):
    path = tmp_path / "state.sqlite3"
    store = DiscordInboxStore(path)
    bindings = DiscordBindingStore(path)
    bindings.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-a",
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
        content="hello",
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
    store.accept(screen_text_dm(config, event))
    result = DiscordConversationBridge(
        store=store,
        bindings=bindings,
        conversation=Conversation(),
    ).process(
        bot_user_id=BOT,
        channel_id=CHANNEL,
        message_id=MESSAGE,
    )
    assert result.outbox is not None
    return result.outbox, bindings, config


def test_prepared_reply_is_authorized_while_binding_is_unchanged(tmp_path) -> None:
    outbox, bindings, config = prepared(tmp_path)
    decision = DiscordOutboundGate(
        config=config,
        bindings=bindings,
    ).authorize(outbox)
    assert decision.allowed is True
    assert decision.reason is None


def test_pause_blocks_prepared_reply(tmp_path) -> None:
    outbox, bindings, config = prepared(tmp_path)
    bindings.pause(bot_user_id=BOT, channel_id=CHANNEL)
    decision = DiscordOutboundGate(
        config=config,
        bindings=bindings,
    ).authorize(outbox)
    assert decision.reason is OutboundDenial.PAUSED


def test_pause_then_resume_keeps_old_reply_stale(tmp_path) -> None:
    outbox, bindings, config = prepared(tmp_path)
    bindings.pause(bot_user_id=BOT, channel_id=CHANNEL)
    bindings.resume(bot_user_id=BOT, channel_id=CHANNEL)
    decision = DiscordOutboundGate(
        config=config,
        bindings=bindings,
    ).authorize(outbox)
    assert decision.reason is OutboundDenial.STALE_BINDING


def test_revoke_blocks_prepared_reply(tmp_path) -> None:
    outbox, bindings, config = prepared(tmp_path)
    bindings.revoke(bot_user_id=BOT, channel_id=CHANNEL)
    decision = DiscordOutboundGate(
        config=config,
        bindings=bindings,
    ).authorize(outbox)
    assert decision.reason is OutboundDenial.REVOKED


def test_disabled_or_unpinned_configuration_blocks_send(tmp_path) -> None:
    outbox, bindings, config = prepared(tmp_path)

    disabled = replace(config, enabled=False)
    assert DiscordOutboundGate(
        config=disabled,
        bindings=bindings,
    ).authorize(outbox).reason is OutboundDenial.DISABLED

    unpinned = replace(config, dm_channel_id=None)
    assert DiscordOutboundGate(
        config=unpinned,
        bindings=bindings,
    ).authorize(outbox).reason is OutboundDenial.CHANNEL_NOT_PINNED
