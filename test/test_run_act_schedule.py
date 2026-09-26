from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from sofia.act import (
    ActOutbox,
    DeliveryOutcome,
    Policy,
    SendResult,
)
from sofia.interaction.goal_journal import GoalJournal
from sofia.run.act_schedule import (
    ActSchedulePolicy,
    ScheduledActRunner,
)


NOW = datetime(2026, 9, 26, 18, 0, tzinfo=timezone.utc)


def prepared(tmp_path: Path, *, bound: bool = True):
    state = tmp_path / "sofia.db"
    with sqlite3.connect(state) as db:
        db.execute(
            """
            CREATE TABLE conversation_messages (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL
            )
            """
        )
        db.execute(
            "INSERT INTO conversation_messages (id, role) VALUES (?, ?)",
            ("source-1", "user"),
        )

    journal = GoalJournal(state)
    journal.create_goal(
        goal_id="goal-1",
        source_id="source-1",
        title="Follow up",
        kind="question",
        priority=3,
        at=NOW - timedelta(minutes=5),
    )
    journal.transition(
        goal_id="goal-1",
        transition_id="transition-1",
        source_id="source-1",
        expected_status="proposed",
        next_status="active",
        at=NOW - timedelta(minutes=4),
    )
    queued = journal.queue_message(
        message_id="message-1",
        goal_id="goal-1",
        evidence_id="source-1",
        content="A reviewed follow-up.",
        at=NOW - timedelta(minutes=3),
        opted_in=True,
        presence="away",
        mode="queue_only",
    )
    assert queued is not None

    outbox = ActOutbox(state)
    if bound:
        outbox.bind(
            message_id="message-1",
            recipient_id="sparks",
            channel="test",
            destination="private",
            expires_at=NOW + timedelta(hours=1),
            at=NOW - timedelta(minutes=2),
        )
    return journal, outbox


def policy(bound):
    return Policy(
        recipient_id=bound.recipient_id,
        enabled=True,
        quiet_start_utc=22,
        quiet_end_utc=8,
        min_interval=timedelta(0),
        max_daily=5,
    )


def test_schedule_is_disabled_by_default_and_never_calls_sender(tmp_path: Path):
    journal, outbox = prepared(tmp_path)
    sent = []
    runner = ScheduledActRunner(
        journal=journal,
        outbox=outbox,
        sender=lambda payload: sent.append(payload),
        policy_for=policy,
        attempt_id_for=lambda bound: "attempt-1",
    )

    result = runner.tick(now=NOW)

    assert result.status == "disabled"
    assert result.results == ()
    assert sent == []


def test_enabled_schedule_delivers_one_bound_policy_eligible_message(tmp_path: Path):
    journal, outbox = prepared(tmp_path)
    sent = []

    def sender(payload):
        sent.append(payload)
        return SendResult(DeliveryOutcome.DELIVERED, receipt_id="receipt-1")

    runner = ScheduledActRunner(
        journal=journal,
        outbox=outbox,
        sender=sender,
        policy_for=policy,
        attempt_id_for=lambda bound: "attempt-1",
        schedule=ActSchedulePolicy(enabled=True),
    )

    result = runner.tick(now=NOW)

    assert result.status == "processed"
    assert result.examined == 1
    assert len(result.results) == 1
    assert result.results[0].send_result is not None
    assert result.results[0].send_result.outcome is DeliveryOutcome.DELIVERED
    assert [payload.message_id for payload in sent] == ["message-1"]
    assert journal.pending() == ()


def test_enabled_schedule_ignores_unbound_messages(tmp_path: Path):
    journal, outbox = prepared(tmp_path, bound=False)
    sent = []
    runner = ScheduledActRunner(
        journal=journal,
        outbox=outbox,
        sender=lambda payload: sent.append(payload),
        policy_for=policy,
        attempt_id_for=lambda bound: "attempt-1",
        schedule=ActSchedulePolicy(enabled=True),
    )

    result = runner.tick(now=NOW)

    assert result.status == "idle"
    assert result.examined == 1
    assert result.results == ()
    assert sent == []
    assert len(journal.pending()) == 1


def test_policy_provider_can_decline_delivery_without_sender_call(tmp_path: Path):
    journal, outbox = prepared(tmp_path)
    sent = []
    runner = ScheduledActRunner(
        journal=journal,
        outbox=outbox,
        sender=lambda payload: sent.append(payload),
        policy_for=lambda bound: None,
        attempt_id_for=lambda bound: "attempt-1",
        schedule=ActSchedulePolicy(enabled=True),
    )

    result = runner.tick(now=NOW)

    assert result.status == "idle"
    assert result.results == ()
    assert sent == []


def test_busy_state_is_forwarded_to_act_policy_gate(tmp_path: Path):
    journal, outbox = prepared(tmp_path)
    sent = []
    runner = ScheduledActRunner(
        journal=journal,
        outbox=outbox,
        sender=lambda payload: sent.append(payload),
        policy_for=policy,
        attempt_id_for=lambda bound: "attempt-1",
        schedule=ActSchedulePolicy(enabled=True),
    )

    result = runner.tick(now=NOW, busy=True)

    assert result.status == "processed"
    assert len(result.results) == 1
    assert result.results[0].claim_result.status == "policy_blocked"
    assert sent == []
