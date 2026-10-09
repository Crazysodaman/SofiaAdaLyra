"""Durable, content-minimal diagnostics for the existing ACT delivery path."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


@dataclass(frozen=True, slots=True)
class OutreachTrace:
    trace_id: int
    notice_id: str
    stage: str
    reason: str
    recorded_at: datetime
    channel: str | None
    destination: str | None
    receipt_id: str | None
    recipient_confirmed: bool


def ensure_outreach_trace_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS act_outreach_trace (
            trace_id INTEGER PRIMARY KEY AUTOINCREMENT,
            notice_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            reason TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            channel TEXT,
            destination TEXT,
            receipt_id TEXT,
            recipient_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(
                recipient_confirmed IN (0,1)
            ),
            UNIQUE(notice_id,stage,reason)
        );
        CREATE INDEX IF NOT EXISTS act_outreach_trace_recent
            ON act_outreach_trace(recorded_at DESC,trace_id DESC);
        """
    )


def record_outreach_trace(
    db: sqlite3.Connection,
    *,
    notice_id: str,
    stage: str,
    reason: str,
    recorded_at: datetime,
    channel: str | None = None,
    destination: str | None = None,
    receipt_id: str | None = None,
    recipient_confirmed: bool = False,
) -> None:
    if not isinstance(db, sqlite3.Connection):
        raise TypeError("db must be sqlite3.Connection")
    for name, value in (("notice_id", notice_id), ("stage", stage), ("reason", reason)):
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError(f"{name} must be bounded nonempty text")
    if (
        not isinstance(recorded_at, datetime)
        or recorded_at.tzinfo is None
        or recorded_at.utcoffset() is None
    ):
        raise ValueError("recorded_at must be timezone-aware")
    if type(recipient_confirmed) is not bool:
        raise TypeError("recipient_confirmed must be bool")
    db.execute(
        """
        INSERT OR IGNORE INTO act_outreach_trace(
            notice_id,stage,reason,recorded_at,channel,destination,
            receipt_id,recipient_confirmed
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            notice_id.strip(), stage.strip(), reason.strip(),
            recorded_at.astimezone(timezone.utc).isoformat(),
            channel, destination, receipt_id, int(recipient_confirmed),
        ),
    )
    db.execute(
        """
        DELETE FROM act_outreach_trace WHERE trace_id IN (
            SELECT trace_id FROM act_outreach_trace
            ORDER BY recorded_at DESC,trace_id DESC LIMIT -1 OFFSET 1000
        )
        """
    )


class OutreachTraceStore:
    """Read diagnostics and accept confirmations from trusted UI transports."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        with closing(self._connect()) as db, db:
            ensure_outreach_trace_schema(db)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(self, **kwargs) -> None:
        with closing(self._connect()) as db, db:
            record_outreach_trace(db, **kwargs)

    def confirm_recipient(
        self,
        *,
        notice_id: str,
        channel: str,
        recorded_at: datetime,
        receipt_id: str,
    ) -> None:
        self.record(
            notice_id=notice_id,
            stage="recipient_confirmed",
            reason=f"{channel}_acknowledged",
            recorded_at=recorded_at,
            channel=channel,
            receipt_id=receipt_id,
            recipient_confirmed=True,
        )

    def history(
        self, *, notice_id: str | None = None, limit: int = 100,
    ) -> tuple[OutreachTrace, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be in 1..1000")
        with closing(self._connect()) as db:
            if notice_id is None:
                rows = db.execute(
                    "SELECT * FROM act_outreach_trace "
                    "ORDER BY recorded_at DESC,trace_id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM act_outreach_trace WHERE notice_id=? "
                    "ORDER BY recorded_at,trace_id LIMIT ?",
                    (notice_id, limit),
                ).fetchall()
        return tuple(OutreachTrace(
            trace_id=int(row["trace_id"]),
            notice_id=row["notice_id"],
            stage=row["stage"],
            reason=row["reason"],
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
            channel=row["channel"],
            destination=row["destination"],
            receipt_id=row["receipt_id"],
            recipient_confirmed=bool(row["recipient_confirmed"]),
        ) for row in rows)
