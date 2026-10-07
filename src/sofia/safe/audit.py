from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


class AuditChain:
    """Append-only API with SHA-256 hash chaining for protected audit evidence."""

    GENESIS = "0" * 64

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS safe_audit_event (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT NOT NULL UNIQUE,
                        occurred_at TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        previous_hash TEXT NOT NULL,
                        event_hash TEXT NOT NULL UNIQUE
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @classmethod
    def _event_hash(
        cls,
        *,
        event_id: str,
        occurred_at: str,
        actor_id: str,
        event_type: str,
        payload_json: str,
        previous_hash: str,
    ) -> str:
        document = {
            "event_id": event_id,
            "occurred_at": occurred_at,
            "actor_id": actor_id,
            "event_type": event_type,
            "payload_json": payload_json,
            "previous_hash": previous_hash,
        }
        return sha256(
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

    def append(
        self,
        *,
        actor_id: str,
        event_type: str,
        payload: dict,
        occurred_at: datetime | None = None,
        event_id: str | None = None,
    ) -> str:
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ValueError("actor_id must be nonempty")
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be nonempty")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        when = occurred_at or datetime.now(timezone.utc)
        if when.tzinfo is None or when.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        identifier = event_id or str(uuid4())
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError("event_id must be nonempty")
        payload_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        occurred = when.astimezone(timezone.utc).isoformat()

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                return self.append_in_transaction(
                    db,
                    actor_id=actor_id,
                    event_type=event_type,
                    payload=payload,
                    occurred_at=when,
                    event_id=identifier,
                )

    def append_in_transaction(
        self,
        db: sqlite3.Connection,
        *,
        actor_id: str,
        event_type: str,
        payload: dict,
        occurred_at: datetime,
        event_id: str | None = None,
    ) -> str:
        """Append using the caller's SQLite transaction.

        This is used when the protected state mutation and its audit evidence
        live in the same state database and must commit atomically.
        """
        if not isinstance(db, sqlite3.Connection):
            raise TypeError("db must be a sqlite3.Connection")
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ValueError("actor_id must be nonempty")
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be nonempty")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        if not isinstance(occurred_at, datetime):
            raise TypeError("occurred_at must be a datetime")
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        identifier = event_id or str(uuid4())
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError("event_id must be nonempty")

        payload_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        occurred = occurred_at.astimezone(timezone.utc).isoformat()
        row = db.execute(
            """
            SELECT event_hash
            FROM safe_audit_event
            ORDER BY sequence DESC
            LIMIT 1
            """
        ).fetchone()
        # The transaction belongs to the caller, so its row_factory is also
        # caller-owned. This single-column lookup must work with SQLite's
        # default tuple rows as well as sqlite3.Row.
        previous = self.GENESIS if row is None else row[0]
        event_hash = self._event_hash(
            event_id=identifier,
            occurred_at=occurred,
            actor_id=actor_id,
            event_type=event_type,
            payload_json=payload_json,
            previous_hash=previous,
        )
        db.execute(
            """
            INSERT INTO safe_audit_event (
                event_id,
                occurred_at,
                actor_id,
                event_type,
                payload_json,
                previous_hash,
                event_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                occurred,
                actor_id,
                event_type,
                payload_json,
                previous,
                event_hash,
            ),
        )
        return event_hash

    def verify(self) -> tuple[bool, str | None]:
        previous = self.GENESIS
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT event_id, occurred_at, actor_id, event_type,
                       payload_json, previous_hash, event_hash
                FROM safe_audit_event
                ORDER BY sequence ASC
                """
            ).fetchall()

        for row in rows:
            if row["previous_hash"] != previous:
                return False, (
                    f"audit previous-hash mismatch at event {row['event_id']}"
                )
            expected = self._event_hash(
                event_id=row["event_id"],
                occurred_at=row["occurred_at"],
                actor_id=row["actor_id"],
                event_type=row["event_type"],
                payload_json=row["payload_json"],
                previous_hash=row["previous_hash"],
            )
            if row["event_hash"] != expected:
                return False, (
                    f"audit event-hash mismatch at event {row['event_id']}"
                )
            previous = row["event_hash"]
        return True, None
