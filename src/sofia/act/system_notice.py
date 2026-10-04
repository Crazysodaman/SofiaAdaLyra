from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from sofia.act.history import delivery_history
from sofia.act.delivery import DeliveryOutcome, DeliveryPayload, SendResult
from sofia.act.outreach import (
    Candidate,
    Decision,
    Importance,
    OutreachCategory,
    Policy,
    evaluate,
)


@dataclass(frozen=True, slots=True)
class SystemNotice:
    notice_id: str
    recipient_id: str
    channel: str
    destination: str
    evidence_id: str
    content: str
    created_at: datetime
    expires_at: datetime
    status: str
    category: OutreachCategory = OutreachCategory.OPERATIONAL
    importance: Importance = Importance.ROUTINE
    salience: float = 0.5


class SystemNoticeQueue:
    """Durable ACT queue for operational evidence that is not conversation-derived."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS act_system_notice (
                        notice_id TEXT PRIMARY KEY,
                        recipient_id TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        destination TEXT NOT NULL,
                        evidence_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(
                            status IN ('queued','delivered','failed','outcome_unknown')
                        ),
                        attempt_count INTEGER NOT NULL DEFAULT 0,
                        receipt_id TEXT,
                        error_type TEXT,
                        finished_at TEXT,
                        category TEXT NOT NULL DEFAULT 'operational',
                        importance TEXT NOT NULL DEFAULT 'routine',
                        salience REAL NOT NULL DEFAULT 0.5
                    );
                    CREATE INDEX IF NOT EXISTS act_system_notice_pending
                        ON act_system_notice(status, created_at);
                    CREATE INDEX IF NOT EXISTS act_system_notice_category_time
                        ON act_system_notice(category, finished_at);
                    """
                )
                columns = {
                    row[1]
                    for row in db.execute(
                        "PRAGMA table_info(act_system_notice)"
                    )
                }
                for name, declaration in (
                    ("category", "TEXT NOT NULL DEFAULT 'operational'"),
                    ("importance", "TEXT NOT NULL DEFAULT 'routine'"),
                    ("salience", "REAL NOT NULL DEFAULT 0.5"),
                ):
                    if name not in columns:
                        db.execute(
                            f"ALTER TABLE act_system_notice "
                            f"ADD COLUMN {name} {declaration}"
                        )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _time(value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError("timestamp must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    def enqueue(
        self,
        *,
        notice_id: str,
        recipient_id: str,
        channel: str,
        destination: str,
        evidence_id: str,
        content: str,
        created_at: datetime,
        expires_at: datetime,
        category: OutreachCategory = OutreachCategory.OPERATIONAL,
        importance: Importance = Importance.ROUTINE,
        salience: float = 0.5,
    ) -> SystemNotice:
        for name, value in (
            ("notice_id", notice_id),
            ("recipient_id", recipient_id),
            ("channel", channel),
            ("destination", destination),
            ("evidence_id", evidence_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if not isinstance(content, str) or not content.strip() or len(content) > 640:
            raise ValueError("content must be bounded nonempty text")
        if not isinstance(category, OutreachCategory):
            raise TypeError("category must be OutreachCategory")
        if not isinstance(importance, Importance):
            raise TypeError("importance must be Importance")
        if not isinstance(salience, (int, float)) or isinstance(salience, bool):
            raise TypeError("salience must be numeric")
        if not 0.0 <= salience <= 1.0:
            raise ValueError("salience must be in [0,1]")
        created = self._time(created_at)
        expires = self._time(expires_at)
        if expires <= created:
            raise ValueError("notice must expire after creation")

        # Build the same Candidate that delivery will later evaluate so invalid
        # ACT identifiers fail at enqueue time instead of poisoning the queue.
        Candidate(
            candidate_id=notice_id,
            recipient_id=recipient_id,
            evidence_ids=(evidence_id,),
            created_at=created,
            expires_at=expires,
            category=category,
            importance=importance,
            salience=float(salience),
        )

        desired = (
            notice_id,
            recipient_id,
            channel,
            destination,
            evidence_id,
            content.strip(),
            created.isoformat(),
            expires.isoformat(),
            category.value,
            importance.value,
            float(salience),
        )
        durable_status = "queued"
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                old = db.execute(
                    """
                    SELECT notice_id,recipient_id,channel,destination,evidence_id,
                           content,created_at,expires_at,category,importance,salience,
                           status
                    FROM act_system_notice
                    WHERE notice_id=?
                    """,
                    (notice_id,),
                ).fetchone()
                if old is not None:
                    if tuple(old[:-1]) != desired:
                        raise ValueError("notice_id reused for different evidence")
                    durable_status = str(old["status"])
                else:
                    db.execute(
                        """
                        INSERT INTO act_system_notice(
                            notice_id,recipient_id,channel,destination,evidence_id,
                            content,created_at,expires_at,status,attempt_count,
                            category,importance,salience
                        )
                        VALUES(?,?,?,?,?,?,?,?,'queued',0,?,?,?)
                        """,
                        desired,
                    )
        return SystemNotice(
            notice_id,
            recipient_id,
            channel,
            destination,
            evidence_id,
            content.strip(),
            created,
            expires,
            durable_status,
            category,
            importance,
            float(salience),
        )

    def _finish_delivery(
        self,
        *,
        payload: DeliveryPayload,
        result: SendResult,
        at: datetime,
        max_attempts: int,
    ) -> None:
        status = {
            DeliveryOutcome.DELIVERED: "delivered",
            DeliveryOutcome.FAILED: "failed",
            DeliveryOutcome.OUTCOME_UNKNOWN: "outcome_unknown",
        }[result.outcome]

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """
                    SELECT status,attempt_count
                    FROM act_system_notice
                    WHERE notice_id=?
                    """,
                    (payload.message_id,),
                ).fetchone()
                if row is None:
                    raise RuntimeError("claimed system notice disappeared")
                if row["status"] != "outcome_unknown":
                    raise RuntimeError(
                        "system notice is no longer in its claimed state"
                    )

                if status == "failed":
                    final_status = (
                        "failed"
                        if int(row["attempt_count"]) >= max_attempts
                        else "queued"
                    )
                else:
                    final_status = status

                changed = db.execute(
                    """
                    UPDATE act_system_notice
                    SET status=?,receipt_id=?,error_type=?,finished_at=?
                    WHERE notice_id=? AND status='outcome_unknown'
                    """,
                    (
                        final_status,
                        result.receipt_id,
                        result.error_type,
                        at.isoformat(),
                        payload.message_id,
                    ),
                )
                if changed.rowcount != 1:
                    raise RuntimeError(
                        "system notice delivery claim was lost"
                    )

    def deliver_one(
        self,
        *,
        sender,
        policy: Policy,
        now: datetime,
        busy: bool = False,
        max_attempts: int = 3,
    ) -> SendResult | None:
        if not callable(sender):
            raise TypeError("sender must be callable")
        if not isinstance(policy, Policy):
            raise TypeError("policy must be a Policy")
        if not isinstance(busy, bool):
            raise TypeError("busy must be boolean")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be in 1..10")
        moment = self._time(now)

        payload = None
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                rows = db.execute(
                    """
                    SELECT *
                    FROM act_system_notice
                    WHERE status='queued'
                      AND attempt_count < ?
                    ORDER BY created_at,notice_id
                    """,
                    (max_attempts,),
                ).fetchall()
                for row in rows:
                    created = datetime.fromisoformat(
                        row["created_at"]
                    ).astimezone(timezone.utc)
                    expires = datetime.fromisoformat(
                        row["expires_at"]
                    ).astimezone(timezone.utc)
                    if moment >= expires:
                        db.execute(
                            """
                            UPDATE act_system_notice
                            SET status='failed',error_type='Expired',finished_at=?
                            WHERE notice_id=? AND status='queued'
                            """,
                            (moment.isoformat(), row["notice_id"]),
                        )
                        continue

                    candidate = Candidate(
                        candidate_id=row["notice_id"],
                        recipient_id=row["recipient_id"],
                        evidence_ids=(row["evidence_id"],),
                        created_at=created,
                        expires_at=expires,
                        category=OutreachCategory(row["category"]),
                        importance=Importance(row["importance"]),
                        salience=float(row["salience"]),
                    )
                    history = delivery_history(
                        db,
                        recipient_id=row["recipient_id"],
                        channel=row["channel"],
                        destination=row["destination"],
                        now=moment,
                    )
                    decision = evaluate(
                        candidate,
                        policy,
                        history,
                        moment,
                        busy=busy,
                    )
                    if decision is not Decision.ELIGIBLE_FOR_AUTHORIZATION:
                        continue

                    attempt_id = str(uuid4())
                    changed = db.execute(
                        """
                        UPDATE act_system_notice
                        SET attempt_count=attempt_count+1,
                            status='outcome_unknown',
                            receipt_id=NULL,
                            error_type='DeliveryInProgress',
                            finished_at=NULL
                        WHERE notice_id=? AND status='queued'
                        """,
                        (row["notice_id"],),
                    )
                    if changed.rowcount != 1:
                        continue

                    payload = DeliveryPayload(
                        attempt_id=attempt_id,
                        message_id=row["notice_id"],
                        recipient_id=row["recipient_id"],
                        channel=row["channel"],
                        destination=row["destination"],
                        evidence_id=row["evidence_id"],
                        content=row["content"],
                    )
                    break

        if payload is None:
            return None

        try:
            result = sender(payload)
            if not isinstance(result, SendResult):
                raise TypeError("ACT sender must return SendResult")
        except Exception as exc:
            self._finish_delivery(
                payload=payload,
                result=SendResult(
                    DeliveryOutcome.OUTCOME_UNKNOWN,
                    error_type=type(exc).__name__,
                ),
                at=moment,
                max_attempts=max_attempts,
            )
            raise

        self._finish_delivery(
            payload=payload,
            result=result,
            at=moment,
            max_attempts=max_attempts,
        )
        return result
