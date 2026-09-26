from __future__ import annotations

from pathlib import Path

from sofia.act.delivery import DeliveryOutcome, DeliveryPayload
from sofia.discord.access import SingleUserDiscordConfig
from sofia.discord.act_sender import (
    DiscordActChunkState,
    DiscordActDeliveryStore,
    DiscordActSafeSender,
)
from sofia.discord.binding import DiscordBindingStore


OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 222222222222222222
SESSION = "session-a"


def payload(*, content: str = "hello", recipient: str = "sparks") -> DeliveryPayload:
    return DeliveryPayload(
        attempt_id="attempt-1",
        message_id="message-1",
        recipient_id=recipient,
        channel="discord_dm",
        destination=str(CHANNEL),
        evidence_id="evidence-1",
        content=content,
    )


def sender(tmp_path: Path, send_chunk):
    path = tmp_path / "state.sqlite3"
    bindings = DiscordBindingStore(path)
    bindings.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id=SESSION,
    )
    deliveries = DiscordActDeliveryStore(path)
    config = SingleUserDiscordConfig(
        owner_user_id=OWNER,
        bot_user_id=BOT,
        enabled=True,
        dm_channel_id=CHANNEL,
    )
    return (
        DiscordActSafeSender(
            config=config,
            bindings=bindings,
            deliveries=deliveries,
            session_id=SESSION,
            recipient_id="sparks",
            send_chunk=send_chunk,
        ),
        bindings,
        deliveries,
    )


def test_authorized_sender_chunks_and_returns_durable_receipt(tmp_path: Path):
    sent = []

    def send_chunk(content: str) -> int:
        sent.append(content)
        return 5000 + len(sent)

    adapter, _bindings, deliveries = sender(tmp_path, send_chunk)
    message = payload(content="x" * 2500)

    first = adapter(message)
    second = adapter(message)

    assert first.outcome is DeliveryOutcome.DELIVERED
    assert first.receipt_id is not None
    assert second == first
    assert len(sent) == 2
    chunks = deliveries.chunks("attempt-1")
    assert all(chunk.state is DiscordActChunkState.SENT for chunk in chunks)


def test_wrong_act_recipient_fails_before_transport(tmp_path: Path):
    sent = []
    adapter, _bindings, deliveries = sender(
        tmp_path,
        lambda content: sent.append(content) or 5001,
    )

    result = adapter(payload(recipient="someone-else"))

    assert result.outcome is DeliveryOutcome.FAILED
    assert result.error_type == "discord_wrong_recipient"
    assert sent == []
    assert deliveries.attempt("attempt-1") is None


def test_pause_after_first_chunk_quarantines_partial_delivery(tmp_path: Path):
    calls = 0
    adapter = None
    bindings = None

    def send_chunk(content: str) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            assert bindings is not None
            bindings.pause(bot_user_id=BOT, channel_id=CHANNEL)
        return 6000 + calls

    adapter, bindings, deliveries = sender(tmp_path, send_chunk)
    message = payload(content="z" * 2500)

    first = adapter(message)
    second = adapter(message)

    assert first.outcome is DeliveryOutcome.OUTCOME_UNKNOWN
    assert first.error_type == "discord_paused"
    assert second.outcome is DeliveryOutcome.OUTCOME_UNKNOWN
    assert calls == 1
    attempt = deliveries.attempt("attempt-1")
    assert attempt is not None
    assert attempt.state == "outcome_unknown"


def test_transport_exception_is_outcome_unknown_and_not_retried(tmp_path: Path):
    calls = 0

    def send_chunk(content: str) -> int:
        nonlocal calls
        calls += 1
        raise TimeoutError("provider outcome unknown")

    adapter, _bindings, deliveries = sender(tmp_path, send_chunk)
    message = payload()

    first = adapter(message)
    second = adapter(message)

    assert first.outcome is DeliveryOutcome.OUTCOME_UNKNOWN
    assert first.error_type == "TimeoutError"
    assert second.outcome is DeliveryOutcome.OUTCOME_UNKNOWN
    assert calls == 1
    assert deliveries.chunks("attempt-1")[0].state is DiscordActChunkState.OUTCOME_UNKNOWN


def test_binding_generation_change_before_transport_fails_closed(tmp_path: Path):
    sent = []
    adapter, bindings, deliveries = sender(
        tmp_path,
        lambda content: sent.append(content) or 7001,
    )
    message = payload()
    current = bindings.get(bot_user_id=BOT, channel_id=CHANNEL)
    assert current is not None
    deliveries.prepare(message, binding=current)

    bindings.pause(bot_user_id=BOT, channel_id=CHANNEL)
    bindings.resume(bot_user_id=BOT, channel_id=CHANNEL)

    result = adapter(message)

    assert result.outcome is DeliveryOutcome.FAILED
    assert result.error_type == "discord_stale_binding"
    assert sent == []


def test_recover_interrupted_claim_marks_attempt_unknown(tmp_path: Path):
    adapter, bindings, deliveries = sender(tmp_path, lambda content: 8001)
    message = payload()
    current = bindings.get(bot_user_id=BOT, channel_id=CHANNEL)
    assert current is not None
    deliveries.prepare(message, binding=current)
    assert deliveries.claim_chunk(
        attempt_id="attempt-1",
        chunk_index=0,
        send_token="token-1",
    )

    recovered = deliveries.recover_interrupted()

    assert recovered == 1
    attempt = deliveries.attempt("attempt-1")
    assert attempt is not None
    assert attempt.state == "outcome_unknown"
    assert deliveries.chunks("attempt-1")[0].state is DiscordActChunkState.OUTCOME_UNKNOWN



def test_recover_partial_send_marks_attempt_unknown_without_rewriting_sent_chunk(tmp_path: Path):
    adapter, bindings, deliveries = sender(tmp_path, lambda content: 8101)
    message = payload(content="x" * 2500)
    current = bindings.get(bot_user_id=BOT, channel_id=CHANNEL)
    assert current is not None
    deliveries.prepare(message, binding=current)
    assert deliveries.claim_chunk(
        attempt_id="attempt-1",
        chunk_index=0,
        send_token="token-1",
    )
    deliveries.mark_sent(
        attempt_id="attempt-1",
        chunk_index=0,
        platform_message_id=8101,
        send_token="token-1",
    )

    recovered = deliveries.recover_interrupted()

    assert recovered == 1
    attempt = deliveries.attempt("attempt-1")
    assert attempt is not None
    assert attempt.state == "outcome_unknown"
    chunks = deliveries.chunks("attempt-1")
    assert chunks[0].state is DiscordActChunkState.SENT
    assert chunks[1].state is DiscordActChunkState.PREPARED
