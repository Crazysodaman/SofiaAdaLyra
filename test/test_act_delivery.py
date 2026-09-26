from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.act import (
    ActDeliveryRunner,
    ActOutbox,
    DeliveryLimits,
    DeliveryOutcome,
    Policy,
    SendResult,
)

T0 = datetime(2026, 9, 25, 14, tzinfo=timezone.utc)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path) as db:
        db.execute(
            """
            CREATE TABLE interact_queued_messages (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        for message_id, evidence_id, minute in (
            ("m1", "e1", 0),
            ("m2", "e2", 1),
            ("m3", "e3", 2),
        ):
            db.execute(
                "INSERT INTO interact_queued_messages VALUES (?,?,?,?,?,?)",
                (
                    message_id,
                    "goal-1",
                    evidence_id,
                    f"message {message_id}",
                    (T0 - timedelta(hours=1) + timedelta(minutes=minute)).isoformat(),
                    "queued",
                ),
            )
    return path


def enabled_policy(**changes):
    values = dict(
        recipient_id="sparks",
        enabled=True,
        min_interval=timedelta(0),
        max_daily=10,
    )
    values.update(changes)
    return Policy(**values)


def bind(outbox, message_id="m1", recipient="sparks"):
    return outbox.bind(
        message_id=message_id,
        recipient_id=recipient,
        channel="discord_dm",
        destination="dm-123",
        expires_at=T0 + timedelta(hours=3),
        at=T0,
    )


def queue_status(path, message_id):
    with sqlite3.connect(path) as db:
        return db.execute(
            "SELECT status FROM interact_queued_messages WHERE id=?",
            (message_id,),
        ).fetchone()[0]


def test_requires_existing_interact_queue(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    with pytest.raises(ValueError, match="queued-message"):
        ActOutbox(path)


def test_bind_is_immutable_and_idempotent(state):
    outbox = ActOutbox(state)
    first = bind(outbox)
    again = bind(outbox)
    assert first == again
    assert first.recipient_id == "sparks"
    with pytest.raises(ValueError, match="different immutable"):
        outbox.bind(
            message_id="m1",
            recipient_id="sparks",
            channel="discord_dm",
            destination="dm-other",
            expires_at=T0 + timedelta(hours=3),
            at=T0,
        )


def test_wrong_recipient_is_policy_blocked_before_send(state):
    outbox = ActOutbox(state)
    bind(outbox, recipient="other")
    result = outbox.claim(
        message_id="m1",
        attempt_id="a1",
        policy=enabled_policy(),
        limits=DeliveryLimits(),
        now=T0,
    )
    assert result.status == "policy_blocked"
    assert result.outreach_decision.value == "wrong_recipient"
    assert result.claim is None


@pytest.mark.parametrize(
    "policy_change,busy,expected",
    [
        ({"stop": True}, False, "stopped"),
        ({"mute": True}, False, "muted"),
        ({"enabled": False}, False, "disabled"),
        ({}, True, "busy"),
    ],
)
def test_stop_mute_disabled_and_busy_block_claim(
    state, policy_change, busy, expected
):
    outbox = ActOutbox(state)
    bind(outbox)
    result = outbox.claim(
        message_id="m1",
        attempt_id="a1",
        policy=enabled_policy(**policy_change),
        limits=DeliveryLimits(),
        now=T0,
        busy=busy,
    )
    assert result.status == "policy_blocked"
    assert result.outreach_decision.value == expected


def test_success_requires_receipt_and_marks_queue_delivered(state):
    outbox = ActOutbox(state)
    bind(outbox)
    seen = []

    def sender(payload):
        seen.append(payload)
        return SendResult(DeliveryOutcome.DELIVERED, receipt_id="receipt-1")

    result = ActDeliveryRunner(outbox, sender).deliver(
        message_id="m1",
        attempt_id="a1",
        policy=enabled_policy(),
        now=T0,
    )
    assert result.send_result.outcome is DeliveryOutcome.DELIVERED
    assert seen[0].recipient_id == "sparks"
    assert seen[0].destination == "dm-123"
    assert seen[0].evidence_id == "e1"
    assert queue_status(state, "m1") == "delivered"

    history = outbox.history(
        recipient_id="sparks",
        channel="discord_dm",
        destination="dm-123",
        now=T0,
    )
    assert history.delivered_candidate_ids == frozenset({"m1"})
    assert history.delivered_today == 1


def test_known_failure_remains_queued_and_retries_after_delay(state):
    outbox = ActOutbox(state)
    bind(outbox)
    runner = ActDeliveryRunner(
        outbox,
        lambda payload: SendResult(
            DeliveryOutcome.FAILED,
            error_type="RateLimited",
        ),
        limits=DeliveryLimits(retry_delay=timedelta(minutes=10)),
    )
    first = runner.deliver(
        message_id="m1",
        attempt_id="a1",
        policy=enabled_policy(),
        now=T0,
    )
    assert first.send_result.outcome is DeliveryOutcome.FAILED
    assert queue_status(state, "m1") == "queued"

    early = outbox.claim(
        message_id="m1",
        attempt_id="a2",
        policy=enabled_policy(),
        limits=DeliveryLimits(retry_delay=timedelta(minutes=10)),
        now=T0 + timedelta(minutes=9),
    )
    assert early.status == "retry_wait"

    due = outbox.claim(
        message_id="m1",
        attempt_id="a3",
        policy=enabled_policy(),
        limits=DeliveryLimits(retry_delay=timedelta(minutes=10)),
        now=T0 + timedelta(minutes=10),
    )
    assert due.status == "claimed"


def test_sender_exception_becomes_outcome_unknown_and_never_blind_retries(state):
    outbox = ActOutbox(state)
    bind(outbox)

    def uncertain(payload):
        raise TimeoutError("connection dropped after handoff")

    with pytest.raises(TimeoutError):
        ActDeliveryRunner(outbox, uncertain).deliver(
            message_id="m1",
            attempt_id="a1",
            policy=enabled_policy(),
            now=T0,
        )

    assert queue_status(state, "m1") == "outcome_unknown"
    retry = outbox.claim(
        message_id="m1",
        attempt_id="a2",
        policy=enabled_policy(),
        limits=DeliveryLimits(),
        now=T0 + timedelta(hours=1),
    )
    assert retry.status == "not_queued"


def test_non_sendresult_is_also_outcome_unknown(state):
    outbox = ActOutbox(state)
    bind(outbox)
    with pytest.raises(TypeError, match="SendResult"):
        ActDeliveryRunner(outbox, lambda payload: "ok").deliver(
            message_id="m1",
            attempt_id="a1",
            policy=enabled_policy(),
            now=T0,
        )
    assert queue_status(state, "m1") == "outcome_unknown"


def test_in_flight_claim_blocks_competing_attempt(state):
    outbox = ActOutbox(state)
    bind(outbox)
    first = outbox.claim(
        message_id="m1",
        attempt_id="a1",
        policy=enabled_policy(),
        limits=DeliveryLimits(),
        now=T0,
    )
    assert first.status == "claimed"
    second = outbox.claim(
        message_id="m1",
        attempt_id="a2",
        policy=enabled_policy(),
        limits=DeliveryLimits(),
        now=T0,
    )
    assert second.status == "in_flight"


def test_attempt_id_replay_is_idempotent_but_cannot_move_messages(state):
    outbox = ActOutbox(state)
    bind(outbox, "m1")
    bind(outbox, "m2")
    first = outbox.claim(
        message_id="m1",
        attempt_id="a1",
        policy=enabled_policy(),
        limits=DeliveryLimits(),
        now=T0,
    )
    again = outbox.claim(
        message_id="m1",
        attempt_id="a1",
        policy=enabled_policy(),
        limits=DeliveryLimits(),
        now=T0,
    )
    assert first == again
    with pytest.raises(ValueError, match="another message"):
        outbox.claim(
            message_id="m2",
            attempt_id="a1",
            policy=enabled_policy(),
            limits=DeliveryLimits(),
            now=T0,
        )


def test_daily_cap_is_based_on_acknowledged_receipts(state):
    outbox = ActOutbox(state)
    bind(outbox, "m1")
    bind(outbox, "m2")
    sender = lambda payload: SendResult(
        DeliveryOutcome.DELIVERED,
        receipt_id=f"receipt-{payload.message_id}",
    )
    ActDeliveryRunner(outbox, sender).deliver(
        message_id="m1",
        attempt_id="a1",
        policy=enabled_policy(max_daily=1),
        now=T0,
    )
    second = outbox.claim(
        message_id="m2",
        attempt_id="a2",
        policy=enabled_policy(max_daily=1),
        limits=DeliveryLimits(),
        now=T0 + timedelta(minutes=1),
    )
    assert second.status == "policy_blocked"
    assert second.outreach_decision.value == "daily_limit"


def test_attempt_limit_prevents_unbounded_known_failure_loop(state):
    outbox = ActOutbox(state)
    bind(outbox)
    limits = DeliveryLimits(
        max_attempts_per_message=2,
        retry_delay=timedelta(0),
    )
    for attempt in ("a1", "a2"):
        claim = outbox.claim(
            message_id="m1",
            attempt_id=attempt,
            policy=enabled_policy(),
            limits=limits,
            now=T0,
        )
        assert claim.status == "claimed"
        outbox.finish(
            claim.claim,
            SendResult(DeliveryOutcome.FAILED, error_type="NoRoute"),
            at=T0,
            retry_delay=timedelta(0),
        )
    blocked = outbox.claim(
        message_id="m1",
        attempt_id="a3",
        policy=enabled_policy(),
        limits=limits,
        now=T0,
    )
    assert blocked.status == "attempt_limit"


def test_delivery_result_validation():
    with pytest.raises(ValueError):
        SendResult(DeliveryOutcome.DELIVERED)
    with pytest.raises(ValueError):
        SendResult(DeliveryOutcome.FAILED, receipt_id="receipt")
    with pytest.raises(ValueError):
        DeliveryLimits(max_attempts_per_message=0)



def test_recover_interrupted_claim_quarantines_attempt_and_queue(state):
    outbox = ActOutbox(state)
    bind(outbox)
    first = outbox.claim(
        message_id="m1",
        attempt_id="a1",
        policy=enabled_policy(),
        limits=DeliveryLimits(),
        now=T0,
    )
    assert first.status == "claimed"

    recovered = outbox.recover_interrupted()

    assert recovered == 1
    assert queue_status(state, "m1") == "outcome_unknown"
    with sqlite3.connect(state) as db:
        row = db.execute(
            """
            SELECT status, error_type, next_retry_at
            FROM act_delivery_attempts
            WHERE attempt_id='a1'
            """
        ).fetchone()
    assert row == ("outcome_unknown", "ProcessRestartDuringSend", None)


def test_recover_interrupted_is_idempotent(state):
    outbox = ActOutbox(state)
    bind(outbox)
    outbox.claim(
        message_id="m1",
        attempt_id="a1",
        policy=enabled_policy(),
        limits=DeliveryLimits(),
        now=T0,
    )

    assert outbox.recover_interrupted() == 1
    assert outbox.recover_interrupted() == 0
