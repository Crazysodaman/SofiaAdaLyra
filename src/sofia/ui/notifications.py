"""Durable local notifications shared by the runtime and tray processes."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.act.diagnostics import OutreachTraceStore


@dataclass(frozen=True, slots=True)
class DesktopNotification:
    notification_id: str
    title: str
    content: str
    created_at: datetime
    status: str


class DesktopNotificationStore:
    """Queue once and quarantine uncertain display outcomes after a crash."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS ui_desktop_notification (
                    notification_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(
                        status IN ('queued','outcome_unknown','displayed')
                    ),
                    claimed_at TEXT,
                    displayed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS ui_desktop_notification_pending
                    ON ui_desktop_notification(status,created_at);
                """
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

    @staticmethod
    def _text(value: str, label: str, limit: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"{label} must be bounded nonempty text")
        return value.strip()

    @staticmethod
    def _record(row: sqlite3.Row) -> DesktopNotification:
        return DesktopNotification(
            notification_id=row["notification_id"],
            title=row["title"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            status=row["status"],
        )

    def enqueue(
        self,
        *,
        notification_id: str,
        title: str,
        content: str,
        created_at: datetime,
    ) -> DesktopNotification:
        key = self._text(notification_id, "notification_id", 200)
        heading = self._text(title, "title", 63)
        body = self._text(content, "content", 255)
        moment = self._time(created_at)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM ui_desktop_notification WHERE notification_id=?",
                (key,),
            ).fetchone()
            if row is not None:
                if (row["title"], row["content"]) != (heading, body):
                    raise ValueError(
                        "notification_id already records different content"
                    )
                return self._record(row)
            db.execute(
                "INSERT INTO ui_desktop_notification VALUES (?,?,?,?, 'queued',NULL,NULL)",
                (key, heading, body, moment.isoformat()),
            )
            row = db.execute(
                "SELECT * FROM ui_desktop_notification WHERE notification_id=?",
                (key,),
            ).fetchone()
        return self._record(row)

    def claim_next(self, *, now: datetime) -> DesktopNotification | None:
        moment = self._time(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM ui_desktop_notification "
                "WHERE status='queued' ORDER BY created_at,notification_id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            changed = db.execute(
                "UPDATE ui_desktop_notification "
                "SET status='outcome_unknown',claimed_at=? "
                "WHERE notification_id=? AND status='queued'",
                (moment.isoformat(), row["notification_id"]),
            )
            if changed.rowcount != 1:
                return None
            values = dict(row)
            values["status"] = "outcome_unknown"
        return DesktopNotification(
            notification_id=values["notification_id"],
            title=values["title"],
            content=values["content"],
            created_at=datetime.fromisoformat(values["created_at"]),
            status=values["status"],
        )

    def mark_displayed(self, notification_id: str, *, now: datetime) -> None:
        key = self._text(notification_id, "notification_id", 200)
        moment = self._time(now)
        with closing(self._connect()) as db, db:
            changed = db.execute(
                "UPDATE ui_desktop_notification "
                "SET status='displayed',displayed_at=? "
                "WHERE notification_id=? AND status='outcome_unknown'",
                (moment.isoformat(), key),
            )
            if changed.rowcount != 1:
                raise RuntimeError("desktop notification claim is no longer active")
        if key.startswith("act:"):
            notice_id = key.removeprefix("act:")
            OutreachTraceStore(self.path).confirm_recipient(
                notice_id=notice_id,
                channel="desktop",
                recorded_at=moment,
                receipt_id=f"desktop-displayed:{notice_id}",
            )
