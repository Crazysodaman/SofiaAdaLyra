from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from sofia.act.delivery import DeliveryOutcome, DeliveryPayload, SendResult
from sofia.act.outreach import (
    Candidate,
    Decision,
    History,
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
        if not 0.0 <= salience <= 1.0:
            raise ValueError("salience must be in [0,1]")
        created = self._time(created_at)
        expires = self._time(expires_at)
        if expires <= created:
            raise ValueError("notice must expire after creation")

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
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                old = db.execute(
                    """
                    SELECT notice_id,recipient_id,channel,destination,evidence_id,
                           content,created_at,expires_at,category,importance,salience
                    FROM act_system_notice
                    WHERE notice_id=?
                    """,
                    (notice_id,),
                ).fetchone()
                if old is not None:
                    if tuple(old) != desired:
                        raise ValueError("notice_id reused for different evidence")
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
            notice_id, recipient_id, channel, destination, evidence_id,
            content.strip(), created, expires, "queued",
            category, importance, salience,
        )

    def _history(
        self,
        db: sqlite3.Connection,
        *,
        recipient_id: str,
        channel: str,
        destination: str,
        now: datetime,
    ) -> History:
        rows = db.execute(
            """
            SELECT notice_id AS candidate_id,finished_at,category
            FROM act_system_notice
            WHERE recipient_id=? AND channel=? AND destination=?
              AND status='delivered'
            ORDER BY finished_at,candidate_id
            """,
            (recipient_id, channel, destination),
        ).fetchall()
        operational_times = [
            datetime.fromisoformat(row["finished_at"]).astimezone(timezone.utc)
            for row in rows
            if row["finished_at"] is not None
            and row["category"] == OutreachCategory.OPERATIONAL.value
        ]
        social_notice_times = [
            datetime.fromisoformat(row["finished_at"]).astimezone(timezone.utc)
            for row in rows
            if row["finished_at"] is not None
            and row["category"] == OutreachCategory.SOCIAL.value
        ]

        has_delivery_attempts = db.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='act_delivery_attempts'"
        ).fetchone() is not None
        social_delivery_rows = []
        if has_delivery_attempts:
            social_delivery_rows = db.execute(
                """
                SELECT message_id AS candidate_id,finished_at
                FROM act_delivery_attempts
                WHERE recipient_id=? AND channel=? AND destination=?
                  AND status='delivered'
                ORDER BY finished_at,candidate_id
                """,
                (recipient_id, channel, destination),
            ).fetchall()
        social_delivery_times = [
            datetime.fromisoformat(row["finished_at"]).astimezone(timezone.utc)
            for row in social_delivery_rows
            if row["finished_at"] is not None
        ]

        social_times = sorted(social_notice_times + social_delivery_times)
        all_times = sorted(operational_times + social_times)
        all_ids = frozenset(
            [row["candidate_id"] for row in rows]
            + [row["candidate_id"] for row in social_delivery_rows]
        )
        day = now.date().isoformat()

        def today_count(values):
            return sum(
                1 for value in values
                if value.date().isoformat() == day
            )

        return History(
            delivered_candidate_ids=all_ids,
            last_delivered_at=all_times[-1] if all_times else None,
            delivered_today=today_count(all_times),
            delivered_day_utc=day if all_times else None,
            social_last_delivered_at=social_times[-1] if social_times else None,
            social_delivered_today=today_count(social_times),
            operational_last_delivered_at=(
                operational_times[-1] if operational_times else None
            ),
            operational_delivered_today=today_count(operational_times),
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
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be in 1..10")
        moment = self._time(now)

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """
                    SELECT *
                    FROM act_system_notice
                    WHERE status='queued'
                      AND attempt_count < ?
                    ORDER BY created_at,notice_id
                    LIMIT 1
                    """,
                    (max_attempts,),
                ).fetchone()
                if row is None:
                    return None
                created = datetime.fromisoformat(row["created_at"]).astimezone(timezone.utc)
                expires = datetime.fromisoformat(row["expires_at"]).astimezone(timezone.utc)
                if moment >= expires:
                    db.execute(
                        """
                        UPDATE act_system_notice
                        SET status='failed',error_type='Expired',finished_at=?
                        WHERE notice_id=? AND status='queued'
                        """,
                        (moment.isoformat(), row["notice_id"]),
                    )
                    return None
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
                history = self._history(
                    db,
                    recipient_id=row["recipient_id"],
                    channel=row["channel"],
                    destination=row["destination"],
                    now=moment,
                )
                decision = evaluate(candidate, policy, history, moment, busy=busy)
                if decision is not Decision.ELIGIBLE_FOR_AUTHORIZATION:
                    return None
                db.execute(
                    """
                    UPDATE act_system_notice
                    SET attempt_count=attempt_count+1
                    WHERE notice_id=? AND status='queued'
                    """,
                    (row["notice_id"],),
                )
                payload = DeliveryPayload(
                    attempt_id=str(uuid4()),
                    message_id=row["notice_id"],
                    recipient_id=row["recipient_id"],
                    channel=row["channel"],
                    destination=row["destination"],
                    evidence_id=row["evidence_id"],
                    content=row["content"],
                )

        try:
            result = sender(payload)
        except Exception as exc:
            result = SendResult(
                DeliveryOutcome.FAILED,
                error_type=type(exc).__name__,
            )
        if not isinstance(result, SendResult):
            raise TypeError("ACT sender must return SendResult")

        status = {
            DeliveryOutcome.DELIVERED: "delivered",
            DeliveryOutcome.FAILED: "failed",
            DeliveryOutcome.OUTCOME_UNKNOWN: "outcome_unknown",
        }[result.outcome]
        with closing(self._connect()) as db:
            with db:
                if status == "failed":
                    attempts = db.execute(
                        "SELECT attempt_count FROM act_system_notice WHERE notice_id=?",
                        (payload.message_id,),
                    ).fetchone()
                    final_status = (
                        "failed"
                        if attempts is not None and int(attempts[0]) >= max_attempts
                        else "queued"
                    )
                else:
                    final_status = status
                db.execute(
                    """
                    UPDATE act_system_notice
                    SET status=?,receipt_id=?,error_type=?,finished_at=?
                    WHERE notice_id=?
                    """,
                    (
                        final_status,
                        result.receipt_id,
                        result.error_type,
                        moment.isoformat(),
                        payload.message_id,
                    ),
                )
        return result
