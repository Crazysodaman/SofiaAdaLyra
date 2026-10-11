"""Durable at-least-once notification queue for the paired mobile client."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import re
import secrets
import sqlite3

from sofia.act.diagnostics import OutreachTraceStore


_CLAIM_LEASE = timedelta(minutes=5)
_DELIVERY_HANDLE = re.compile(r"mn1_[A-Za-z0-9_-]{24,72}\Z")


@dataclass(frozen=True, slots=True)
class MobileNotification:
    notification_id: str
    title: str
    content: str
    created_at: datetime
    status: str


class MobileNotificationStore:
    """Queue notifications and redeliver claims that were never acknowledged."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS mobile_notification (
                    notification_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(
                        status IN ('queued','claimed','displayed')
                    ),
                    claimed_at TEXT,
                    claimed_device TEXT,
                    displayed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS mobile_notification_pending
                    ON mobile_notification(status,created_at);
                CREATE TABLE IF NOT EXISTS mobile_notification_delivery_handle (
                    handle TEXT PRIMARY KEY,
                    notification_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(notification_id) REFERENCES mobile_notification(notification_id)
                );
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
    def _device(value: str) -> str:
        device = MobileNotificationStore._text(value, "device_id", 128)
        return sha256(device.encode("utf-8")).hexdigest()

    @staticmethod
    def _record(row: sqlite3.Row) -> MobileNotification:
        return MobileNotification(
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
    ) -> MobileNotification:
        key = self._text(notification_id, "notification_id", 200)
        heading = self._text(title, "title", 63)
        body = self._text(content, "content", 2_000)
        moment = self._time(created_at)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM mobile_notification WHERE notification_id=?",
                (key,),
            ).fetchone()
            if row is not None:
                if (row["title"], row["content"]) != (heading, body):
                    raise ValueError(
                        "notification_id already records different content"
                    )
                return self._record(row)
            db.execute(
                "INSERT INTO mobile_notification VALUES "
                "(?,?,?,?, 'queued',NULL,NULL,NULL)",
                (key, heading, body, moment.isoformat()),
            )
            row = db.execute(
                "SELECT * FROM mobile_notification WHERE notification_id=?",
                (key,),
            ).fetchone()
        return self._record(row)

    def delivery_handle(self, notification_id: str) -> str:
        """Return stable random client ID, never an original ACT notice ID.

        These remain stable across claim lease expiries. Existing historical
        notifications obtain their handles on first claim.
        """
        key = self._text(notification_id, "notification_id", 200)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT handle FROM mobile_notification_delivery_handle "
                "WHERE notification_id=?", (key,),
            ).fetchone()
            if existing is not None:
                return str(existing[0])
            if db.execute(
                "SELECT 1 FROM mobile_notification WHERE notification_id=?",
                (key,),
            ).fetchone() is None:
                raise KeyError("notification does not exist")
            handle = "mn1_" + secrets.token_urlsafe(24)
            db.execute(
                "INSERT INTO mobile_notification_delivery_handle "
                "(handle,notification_id,created_at) VALUES(?,?,?)",
                (handle, key, datetime.now(timezone.utc).isoformat()),
            )
        return handle

    def resolve_delivery_handle(self, handle: str) -> str:
        """Resolve ONLY an opaque mobile handle to the original queued notice."""
        if not isinstance(handle, str) or _DELIVERY_HANDLE.fullmatch(handle) is None:
            raise PermissionError("opaque mobile notification handle required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT notification_id FROM mobile_notification_delivery_handle "
                "WHERE handle=?", (handle,),
            ).fetchone()
        if row is None:
            raise PermissionError("unknown mobile notification handle")
        return str(row[0])

    def claim_next(
        self,
        *,
        device_id: str,
        now: datetime,
    ) -> MobileNotification | None:
        device = self._device(device_id)
        moment = self._time(now)
        expired = moment - _CLAIM_LEASE
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE mobile_notification SET status='queued', "
                "claimed_at=NULL, claimed_device=NULL "
                "WHERE status='claimed' AND claimed_at<?",
                (expired.isoformat(),),
            )
            row = db.execute(
                "SELECT * FROM mobile_notification WHERE status='queued' "
                "ORDER BY created_at,notification_id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            changed = db.execute(
                "UPDATE mobile_notification SET status='claimed', "
                "claimed_at=?,claimed_device=? "
                "WHERE notification_id=? AND status='queued'",
                (moment.isoformat(), device, row["notification_id"]),
            )
            if changed.rowcount != 1:
                return None
            values = dict(row)
            values["status"] = "claimed"
        return MobileNotification(
            notification_id=values["notification_id"],
            title=values["title"],
            content=values["content"],
            created_at=datetime.fromisoformat(values["created_at"]),
            status=values["status"],
        )

    def acknowledge(
        self,
        notification_id: str,
        *,
        device_id: str,
        now: datetime,
    ) -> None:
        key = self._text(notification_id, "notification_id", 200)
        device = self._device(device_id)
        moment = self._time(now)
        with closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT status,claimed_device FROM mobile_notification "
                "WHERE notification_id=?",
                (key,),
            ).fetchone()
            if row is None:
                raise KeyError("mobile notification does not exist")
            if row["status"] == "displayed" and row["claimed_device"] == device:
                return
            changed = db.execute(
                "UPDATE mobile_notification SET status='displayed',displayed_at=? "
                "WHERE notification_id=? AND status='claimed' "
                "AND claimed_device=?",
                (moment.isoformat(), key, device),
            )
            if changed.rowcount != 1:
                raise PermissionError(
                    "mobile notification is not claimed by this device"
                )
        if key.startswith("act:"):
            notice_id = key.removeprefix("act:")
            OutreachTraceStore(self.path).confirm_recipient(
                notice_id=notice_id,
                channel="mobile",
                recorded_at=moment,
                receipt_id=f"mobile-ack:{notice_id}",
            )
