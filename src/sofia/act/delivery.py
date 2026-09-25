"""Durable ACT outbox binding, delivery claims, and acknowledged receipts.

INTERACT owns goals and queue creation. ACT binds an explicit recipient/channel
envelope to an existing queued message, applies outreach policy, and records
one delivery attempt at a time. A sender is injected by the host; this module
opens no network connection and starts no scheduler.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
import re
import sqlite3
from typing import Callable

from .outreach import Candidate, Decision, History, Policy, evaluate

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


class DeliveryOutcome(str, Enum):
    DELIVERED = "delivered"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


@dataclass(frozen=True)
class DeliveryLimits:
    max_attempts_per_message: int = 3
    retry_delay: timedelta = timedelta(minutes=10)

    def __post_init__(self) -> None:
        if type(self.max_attempts_per_message) is not int or not 1 <= self.max_attempts_per_message <= 20:
            raise ValueError("max_attempts_per_message must be in 1..20")
        if not isinstance(self.retry_delay, timedelta) or not timedelta(0) <= self.retry_delay <= timedelta(days=1):
            raise ValueError("retry_delay must be between zero and one day")


@dataclass(frozen=True)
class BoundMessage:
    message_id: str
    goal_id: str
    evidence_id: str
    content: str
    created_at: datetime
    recipient_id: str
    channel: str
    destination: str
    expires_at: datetime


@dataclass(frozen=True)
class DeliveryClaim:
    attempt_id: str
    message_id: str
    recipient_id: str
    channel: str
    destination: str
    claimed_at: datetime


@dataclass(frozen=True)
class DeliveryPayload:
    attempt_id: str
    message_id: str
    recipient_id: str
    channel: str
    destination: str
    evidence_id: str
    content: str


@dataclass(frozen=True)
class SendResult:
    outcome: DeliveryOutcome
    receipt_id: str | None = None
    error_type: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, DeliveryOutcome):
            raise TypeError("outcome must be a DeliveryOutcome")
        if self.outcome is DeliveryOutcome.DELIVERED:
            _id(self.receipt_id, "receipt_id")
            if self.error_type is not None:
                raise ValueError("delivered result cannot include error_type")
        else:
            if self.receipt_id is not None:
                raise ValueError("only delivered results may include a receipt")
            if self.error_type is not None:
                _id(self.error_type, "error_type")


@dataclass(frozen=True)
class ClaimResult:
    status: str
    outreach_decision: Decision | None = None
    claim: DeliveryClaim | None = None


@dataclass(frozen=True)
class DeliveryRunResult:
    claim_result: ClaimResult
    send_result: SendResult | None = None


class ActOutbox:
    """Durable bridge from INTERACT's queue to an authorized delivery adapter."""

    def __init__(self, state_path: str | Path) -> None:
        if not isinstance(state_path, (str, Path)) or not str(state_path).strip():
            raise ValueError("state_path is required")
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        with closing(self._connect()) as db:
            table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='interact_queued_messages'"
            ).fetchone()
            if table is None:
                raise ValueError("INTERACT queued-message table is required before ACT delivery")
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS act_outbox_envelopes (
                        message_id TEXT PRIMARY KEY,
                        recipient_id TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        destination TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        bound_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS act_delivery_attempts (
                        attempt_id TEXT PRIMARY KEY,
                        message_id TEXT NOT NULL,
                        recipient_id TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        destination TEXT NOT NULL,
                        claimed_at TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN
                            ('claimed','delivered','failed','outcome_unknown')),
                        finished_at TEXT,
                        receipt_id TEXT,
                        error_type TEXT,
                        next_retry_at TEXT
                    );
                    CREATE UNIQUE INDEX IF NOT EXISTS
                        act_delivery_receipt_unique
                        ON act_delivery_attempts(receipt_id)
                        WHERE receipt_id IS NOT NULL;
                    CREATE INDEX IF NOT EXISTS
                        act_delivery_message_status
                        ON act_delivery_attempts(message_id, status);
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _message_from_row(row: tuple) -> BoundMessage:
        return BoundMessage(
            message_id=row[0],
            goal_id=row[1],
            evidence_id=row[2],
            content=row[3],
            created_at=datetime.fromisoformat(row[4]).astimezone(timezone.utc),
            recipient_id=row[6],
            channel=row[7],
            destination=row[8],
            expires_at=datetime.fromisoformat(row[9]).astimezone(timezone.utc),
        )

    @staticmethod
    def _joined_message(db: sqlite3.Connection, message_id: str) -> tuple | None:
        return db.execute(
            """
            SELECT q.id, q.goal_id, q.evidence_id, q.content, q.created_at, q.status,
                   e.recipient_id, e.channel, e.destination, e.expires_at
            FROM interact_queued_messages AS q
            LEFT JOIN act_outbox_envelopes AS e ON e.message_id=q.id
            WHERE q.id=?
            """,
            (message_id,),
        ).fetchone()

    def bind(
        self,
        *,
        message_id: str,
        recipient_id: str,
        channel: str,
        destination: str,
        expires_at: datetime,
        at: datetime,
    ) -> BoundMessage:
        """Bind an immutable explicit delivery envelope to an existing queue item."""

        for label, value in (
            ("message_id", message_id),
            ("recipient_id", recipient_id),
            ("channel", channel),
            ("destination", destination),
        ):
            _id(value, label)
        expiry = _utc(expires_at)
        bound_at = _utc(at)

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = self._joined_message(db, message_id)
                if row is None:
                    raise ValueError("queued message does not exist")
                if row[5] != "queued":
                    raise ValueError("only a queued message can be bound for delivery")
                created = datetime.fromisoformat(row[4]).astimezone(timezone.utc)
                if bound_at < created:
                    raise ValueError("cannot bind a message before it was queued")
                if expiry <= bound_at or expiry <= created:
                    raise ValueError("delivery envelope must expire after binding and queue creation")

                desired = (
                    message_id,
                    recipient_id,
                    channel,
                    destination,
                    expiry.isoformat(),
                    bound_at.isoformat(),
                )
                old = db.execute(
                    "SELECT message_id, recipient_id, channel, destination, expires_at, bound_at "
                    "FROM act_outbox_envelopes WHERE message_id=?",
                    (message_id,),
                ).fetchone()
                if old is not None and old != desired:
                    raise ValueError("message already has a different immutable delivery envelope")
                if old is None:
                    db.execute(
                        "INSERT INTO act_outbox_envelopes VALUES (?,?,?,?,?,?)",
                        desired,
                    )
                row = self._joined_message(db, message_id)
        return self._message_from_row(row)

    def bound(self, message_id: str) -> BoundMessage | None:
        _id(message_id, "message_id")
        with closing(self._connect()) as db:
            row = self._joined_message(db, message_id)
        if row is None or row[6] is None:
            return None
        return self._message_from_row(row)

    @staticmethod
    def _history_from_db(
        db: sqlite3.Connection,
        *,
        recipient_id: str,
        channel: str,
        destination: str,
        now: datetime,
    ) -> History:
        delivered = db.execute(
            """
            SELECT message_id, finished_at
            FROM act_delivery_attempts
            WHERE recipient_id=? AND channel=? AND destination=? AND status='delivered'
            ORDER BY finished_at, attempt_id
            """,
            (recipient_id, channel, destination),
        ).fetchall()
        ids = frozenset(row[0] for row in delivered)
        times = [datetime.fromisoformat(row[1]).astimezone(timezone.utc) for row in delivered]
        day = now.date().isoformat()
        today_count = sum(1 for value in times if value.date().isoformat() == day)
        return History(
            delivered_candidate_ids=ids,
            last_delivered_at=times[-1] if times else None,
            delivered_today=today_count,
            delivered_day_utc=day if today_count else None,
        )

    def history(
        self,
        *,
        recipient_id: str,
        channel: str,
        destination: str,
        now: datetime,
    ) -> History:
        for label, value in (
            ("recipient_id", recipient_id),
            ("channel", channel),
            ("destination", destination),
        ):
            _id(value, label)
        moment = _utc(now)
        with closing(self._connect()) as db:
            return self._history_from_db(
                db,
                recipient_id=recipient_id,
                channel=channel,
                destination=destination,
                now=moment,
            )

    def claim(
        self,
        *,
        message_id: str,
        attempt_id: str,
        policy: Policy,
        limits: DeliveryLimits,
        now: datetime,
        busy: bool = False,
    ) -> ClaimResult:
        """Atomically claim one policy-eligible queue item for one send attempt."""

        _id(message_id, "message_id")
        _id(attempt_id, "attempt_id")
        if not isinstance(policy, Policy):
            raise TypeError("Policy required")
        if not isinstance(limits, DeliveryLimits):
            raise TypeError("DeliveryLimits required")
        if not isinstance(busy, bool):
            raise TypeError("busy must be boolean")
        moment = _utc(now)

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                existing_attempt = db.execute(
                    """
                    SELECT message_id, recipient_id, channel, destination, claimed_at, status
                    FROM act_delivery_attempts WHERE attempt_id=?
                    """,
                    (attempt_id,),
                ).fetchone()
                if existing_attempt is not None:
                    if existing_attempt[0] != message_id:
                        raise ValueError("attempt ID reused for another message")
                    if existing_attempt[5] == "claimed":
                        return ClaimResult(
                            "claimed",
                            Decision.ELIGIBLE_FOR_AUTHORIZATION,
                            DeliveryClaim(
                                attempt_id,
                                existing_attempt[0],
                                existing_attempt[1],
                                existing_attempt[2],
                                existing_attempt[3],
                                datetime.fromisoformat(existing_attempt[4]).astimezone(timezone.utc),
                            ),
                        )
                    return ClaimResult("attempt_finished")

                row = self._joined_message(db, message_id)
                if row is None:
                    return ClaimResult("not_queued")
                if row[6] is None:
                    return ClaimResult("not_bound")
                if row[5] != "queued":
                    return ClaimResult("not_queued")

                bound = self._message_from_row(row)
                active = db.execute(
                    "SELECT 1 FROM act_delivery_attempts WHERE message_id=? AND status='claimed'",
                    (message_id,),
                ).fetchone()
                if active is not None:
                    return ClaimResult("in_flight")
                uncertain = db.execute(
                    "SELECT 1 FROM act_delivery_attempts WHERE message_id=? AND status='outcome_unknown'",
                    (message_id,),
                ).fetchone()
                if uncertain is not None:
                    return ClaimResult("outcome_unknown")

                attempts = db.execute(
                    "SELECT COUNT(*) FROM act_delivery_attempts WHERE message_id=?",
                    (message_id,),
                ).fetchone()[0]
                if attempts >= limits.max_attempts_per_message:
                    return ClaimResult("attempt_limit")

                retry = db.execute(
                    """
                    SELECT next_retry_at FROM act_delivery_attempts
                    WHERE message_id=? AND status='failed'
                    ORDER BY claimed_at DESC LIMIT 1
                    """,
                    (message_id,),
                ).fetchone()
                if retry is not None and retry[0] is not None:
                    if moment < datetime.fromisoformat(retry[0]).astimezone(timezone.utc):
                        return ClaimResult("retry_wait")

                history = self._history_from_db(
                    db,
                    recipient_id=bound.recipient_id,
                    channel=bound.channel,
                    destination=bound.destination,
                    now=moment,
                )
                candidate = Candidate(
                    candidate_id=bound.message_id,
                    recipient_id=bound.recipient_id,
                    evidence_ids=(bound.evidence_id,),
                    created_at=bound.created_at,
                    expires_at=bound.expires_at,
                )
                decision = evaluate(candidate, policy, history, moment, busy=busy)
                if decision is not Decision.ELIGIBLE_FOR_AUTHORIZATION:
                    return ClaimResult("policy_blocked", decision)

                claim = DeliveryClaim(
                    attempt_id=attempt_id,
                    message_id=message_id,
                    recipient_id=bound.recipient_id,
                    channel=bound.channel,
                    destination=bound.destination,
                    claimed_at=moment,
                )
                db.execute(
                    """
                    INSERT INTO act_delivery_attempts
                    (attempt_id, message_id, recipient_id, channel, destination,
                     claimed_at, status, finished_at, receipt_id, error_type, next_retry_at)
                    VALUES (?,?,?,?,?,?,'claimed',NULL,NULL,NULL,NULL)
                    """,
                    (
                        claim.attempt_id,
                        claim.message_id,
                        claim.recipient_id,
                        claim.channel,
                        claim.destination,
                        claim.claimed_at.isoformat(),
                    ),
                )
        return ClaimResult("claimed", Decision.ELIGIBLE_FOR_AUTHORIZATION, claim)

    def payload(self, claim: DeliveryClaim) -> DeliveryPayload:
        if not isinstance(claim, DeliveryClaim):
            raise TypeError("DeliveryClaim required")
        with closing(self._connect()) as db:
            attempt = db.execute(
                "SELECT status FROM act_delivery_attempts WHERE attempt_id=? AND message_id=?",
                (claim.attempt_id, claim.message_id),
            ).fetchone()
            if attempt is None or attempt[0] != "claimed":
                raise ValueError("delivery attempt is not currently claimed")
            row = self._joined_message(db, claim.message_id)
            if row is None or row[5] != "queued" or row[6] is None:
                raise ValueError("claimed message is no longer safely queued")
            bound = self._message_from_row(row)
        if (
            bound.recipient_id != claim.recipient_id
            or bound.channel != claim.channel
            or bound.destination != claim.destination
        ):
            raise ValueError("delivery envelope changed after claim")
        return DeliveryPayload(
            attempt_id=claim.attempt_id,
            message_id=claim.message_id,
            recipient_id=bound.recipient_id,
            channel=bound.channel,
            destination=bound.destination,
            evidence_id=bound.evidence_id,
            content=bound.content,
        )

    def finish(
        self,
        claim: DeliveryClaim,
        result: SendResult,
        *,
        at: datetime,
        retry_delay: timedelta = timedelta(minutes=10),
    ) -> SendResult:
        if not isinstance(claim, DeliveryClaim):
            raise TypeError("DeliveryClaim required")
        if not isinstance(result, SendResult):
            raise TypeError("SendResult required")
        when = _utc(at)
        if when < claim.claimed_at:
            raise ValueError("delivery cannot finish before it was claimed")
        if not isinstance(retry_delay, timedelta) or retry_delay < timedelta(0):
            raise ValueError("retry_delay must be nonnegative")

        next_retry = (
            (when + retry_delay).isoformat()
            if result.outcome is DeliveryOutcome.FAILED
            else None
        )
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """
                    SELECT message_id, status, receipt_id, error_type
                    FROM act_delivery_attempts WHERE attempt_id=?
                    """,
                    (claim.attempt_id,),
                ).fetchone()
                if row is None or row[0] != claim.message_id:
                    raise ValueError("unknown delivery claim")
                if row[1] != "claimed":
                    if (
                        row[1] == result.outcome.value
                        and row[2] == result.receipt_id
                        and row[3] == result.error_type
                    ):
                        return result
                    raise ValueError("finished delivery attempt cannot be rewritten")

                if result.outcome is DeliveryOutcome.DELIVERED:
                    changed = db.execute(
                        "UPDATE interact_queued_messages SET status='delivered' "
                        "WHERE id=? AND status='queued'",
                        (claim.message_id,),
                    )
                    if changed.rowcount != 1:
                        raise ValueError("message is no longer safely queued")
                elif result.outcome is DeliveryOutcome.OUTCOME_UNKNOWN:
                    changed = db.execute(
                        "UPDATE interact_queued_messages SET status='outcome_unknown' "
                        "WHERE id=? AND status='queued'",
                        (claim.message_id,),
                    )
                    if changed.rowcount != 1:
                        raise ValueError("message is no longer safely queued")

                db.execute(
                    """
                    UPDATE act_delivery_attempts
                    SET status=?, finished_at=?, receipt_id=?, error_type=?, next_retry_at=?
                    WHERE attempt_id=? AND status='claimed'
                    """,
                    (
                        result.outcome.value,
                        when.isoformat(),
                        result.receipt_id,
                        result.error_type,
                        next_retry,
                        claim.attempt_id,
                    ),
                )
        return result


class ActDeliveryRunner:
    """Host-invoked one-shot delivery boundary. It never schedules itself."""

    def __init__(
        self,
        outbox: ActOutbox,
        sender: Callable[[DeliveryPayload], SendResult],
        *,
        limits: DeliveryLimits = DeliveryLimits(),
    ) -> None:
        if not isinstance(outbox, ActOutbox):
            raise TypeError("ActOutbox required")
        if not callable(sender):
            raise TypeError("sender must be callable")
        if not isinstance(limits, DeliveryLimits):
            raise TypeError("DeliveryLimits required")
        self.outbox = outbox
        self.sender = sender
        self.limits = limits

    def deliver(
        self,
        *,
        message_id: str,
        attempt_id: str,
        policy: Policy,
        now: datetime,
        busy: bool = False,
    ) -> DeliveryRunResult:
        claimed = self.outbox.claim(
            message_id=message_id,
            attempt_id=attempt_id,
            policy=policy,
            limits=self.limits,
            now=now,
            busy=busy,
        )
        if claimed.claim is None:
            return DeliveryRunResult(claimed, None)

        payload = self.outbox.payload(claimed.claim)
        try:
            result = self.sender(payload)
            if not isinstance(result, SendResult):
                raise TypeError("sender must return SendResult")
        except Exception as exc:
            self.outbox.finish(
                claimed.claim,
                SendResult(
                    DeliveryOutcome.OUTCOME_UNKNOWN,
                    error_type=type(exc).__name__,
                ),
                at=now,
                retry_delay=self.limits.retry_delay,
            )
            raise

        self.outbox.finish(
            claimed.claim,
            result,
            at=now,
            retry_delay=self.limits.retry_delay,
        )
        return DeliveryRunResult(claimed, result)
