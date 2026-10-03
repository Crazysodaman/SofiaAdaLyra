from datetime import datetime, timedelta, timezone
import sqlite3
from threading import Event, Thread

import pytest

from sofia.act.delivery import DeliveryOutcome, SendResult
from sofia.act.outreach import Importance, OutreachCategory, Policy
from sofia.act.system_notice import SystemNoticeQueue


NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    path.touch()
    return path


def policy() -> Policy:
    return Policy(
        recipient_id="sparks",
        enabled=True,
        min_interval=timedelta(0),
        max_daily=10,
        social_min_interval=timedelta(0),
        operational_min_interval=timedelta(0),
        social_max_daily=10,
        operational_max_daily=10,
    )


def enqueue(
    queue: SystemNoticeQueue,
    notice_id: str = "notice-1",
    *,
    created_at: datetime | None = None,
    category: OutreachCategory = OutreachCategory.OPERATIONAL,
    importance: Importance = Importance.ROUTINE,
    salience: float = 0.5,
):
    created = created_at or (NOW - timedelta(minutes=1))
    return queue.enqueue(
        notice_id=notice_id,
        recipient_id="sparks",
        channel="home_assistant",
        destination="mobile_app_sparks",
        evidence_id=f"evidence:{notice_id}",
        content=f"content for {notice_id}",
        created_at=created,
        expires_at=NOW + timedelta(hours=1),
        category=category,
        importance=importance,
        salience=salience,
    )


def row_for(path, notice_id):
    with sqlite3.connect(path) as db:
        return db.execute(
            """
            SELECT status,attempt_count,receipt_id,error_type,finished_at
            FROM act_system_notice
            WHERE notice_id=?
            """,
            (notice_id,),
        ).fetchone()


def test_sender_exception_is_outcome_unknown_and_never_blind_retried(state):
    queue = SystemNoticeQueue(state)
    enqueue(queue)

    calls = []

    def uncertain(payload):
        calls.append(payload.message_id)
        raise TimeoutError("connection dropped after handoff")

    with pytest.raises(TimeoutError):
        queue.deliver_one(
            sender=uncertain,
            policy=policy(),
            now=NOW,
        )

    stored = row_for(state, "notice-1")
    assert stored[:4] == ("outcome_unknown", 1, None, "TimeoutError")

    retry = queue.deliver_one(
        sender=lambda payload: calls.append("retried"),
        policy=policy(),
        now=NOW + timedelta(minutes=5),
    )
    assert retry is None
    assert calls == ["notice-1"]


def test_invalid_sender_result_is_outcome_unknown(state):
    queue = SystemNoticeQueue(state)
    enqueue(queue)

    with pytest.raises(TypeError, match="SendResult"):
        queue.deliver_one(
            sender=lambda payload: "sent maybe",
            policy=policy(),
            now=NOW,
        )

    stored = row_for(state, "notice-1")
    assert stored[:4] == ("outcome_unknown", 1, None, "TypeError")


def test_blocked_oldest_notice_does_not_hide_later_eligible_notice(state):
    queue = SystemNoticeQueue(state)
    enqueue(
        queue,
        "social-low",
        created_at=NOW - timedelta(minutes=2),
        category=OutreachCategory.SOCIAL,
        importance=Importance.TRIVIAL,
        salience=0.1,
    )
    enqueue(
        queue,
        "operational-next",
        created_at=NOW - timedelta(minutes=1),
        category=OutreachCategory.OPERATIONAL,
    )

    seen = []

    result = queue.deliver_one(
        sender=lambda payload: (
            seen.append(payload.message_id)
            or SendResult(
                DeliveryOutcome.DELIVERED,
                receipt_id="receipt-operational",
            )
        ),
        policy=policy(),
        now=NOW,
    )

    assert result is not None
    assert result.outcome is DeliveryOutcome.DELIVERED
    assert seen == ["operational-next"]
    assert row_for(state, "social-low")[0] == "queued"
    assert row_for(state, "operational-next")[0] == "delivered"


def test_in_flight_notice_cannot_be_claimed_twice(state):
    queue = SystemNoticeQueue(state)
    enqueue(queue)

    entered = Event()
    release = Event()
    results = []
    errors = []

    def first_sender(payload):
        entered.set()
        if not release.wait(timeout=5):
            raise TimeoutError("test sender release timed out")
        return SendResult(
            DeliveryOutcome.DELIVERED,
            receipt_id="receipt-first",
        )

    def worker():
        try:
            results.append(
                queue.deliver_one(
                    sender=first_sender,
                    policy=policy(),
                    now=NOW,
                )
            )
        except Exception as exc:
            errors.append(exc)

    thread = Thread(target=worker)
    thread.start()
    assert entered.wait(timeout=5)

    second = queue.deliver_one(
        sender=lambda payload: SendResult(
            DeliveryOutcome.DELIVERED,
            receipt_id="receipt-second",
        ),
        policy=policy(),
        now=NOW,
    )

    assert second is None
    assert row_for(state, "notice-1")[0] == "outcome_unknown"

    release.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert errors == []
    assert len(results) == 1
    assert results[0].outcome is DeliveryOutcome.DELIVERED
    assert row_for(state, "notice-1")[0] == "delivered"


def test_idempotent_enqueue_reports_existing_durable_status(state):
    queue = SystemNoticeQueue(state)
    first = enqueue(queue)
    assert first.status == "queued"

    queue.deliver_one(
        sender=lambda payload: SendResult(
            DeliveryOutcome.DELIVERED,
            receipt_id="receipt-1",
        ),
        policy=policy(),
        now=NOW,
    )

    replay = enqueue(queue)
    assert replay.status == "delivered"


def test_enqueue_rejects_identifier_that_delivery_cannot_evaluate(state):
    queue = SystemNoticeQueue(state)

    with pytest.raises(ValueError, match="candidate_id"):
        enqueue(queue, "bad notice id")
