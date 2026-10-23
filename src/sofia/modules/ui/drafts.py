"""Persistent unsent draft state for PKG-UI text clients.

Drafts are client state, not conversation messages, memory, authentication, or
proof of authorship. They are never supplied to cognition until an explicit
send operation succeeds in passing them to the canonical conversation service.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from threading import RLock


_MAX_DRAFT_CHARACTERS = 64_000


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    if len(value) > 256:
        raise ValueError(f"{field} is too long")
    return value


@dataclass(frozen=True, slots=True)
class UIDraft:
    client_id: str
    session_id: str
    content: str
    updated_at: datetime

    def __post_init__(self) -> None:
        _identifier(self.client_id, "client_id")
        _identifier(self.session_id, "session_id")
        if not isinstance(self.content, str) or not self.content:
            raise ValueError("draft content must be nonempty")
        if len(self.content) > _MAX_DRAFT_CHARACTERS:
            raise ValueError("draft content is too long")
        if (
            not isinstance(self.updated_at, datetime)
            or self.updated_at.tzinfo is None
            or self.updated_at.utcoffset() is None
        ):
            raise ValueError("updated_at must be timezone-aware")


class UIDraftStore:
    """SQLite-backed draft persistence separated from conversation history."""

    def __init__(self, database_path: Path | str) -> None:
        if not isinstance(database_path, (Path, str)):
            raise TypeError("database_path must be a path")
        self._path = Path(database_path)
        self._lock = RLock()
        self._connection: sqlite3.Connection | None = None
        self.open()

    def open(self) -> None:
        with self._lock:
            if self._connection is not None:
                return
            self._connection = sqlite3.connect(
                str(self._path),
                timeout=5.0,
                check_same_thread=False,
            )
            self._initialize()

    def _initialize(self) -> None:
        connection = self._require_connection()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ui_drafts (
                client_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                content TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (client_id, session_id)
            )
            """
        )
        connection.commit()

    def save(
        self,
        *,
        client_id: str,
        session_id: str,
        content: str,
    ) -> UIDraft | None:
        client_id = _identifier(client_id, "client_id")
        session_id = _identifier(session_id, "session_id")
        if not isinstance(content, str):
            raise TypeError("content must be a string")
        if len(content) > _MAX_DRAFT_CHARACTERS:
            raise ValueError("draft content is too long")

        if not content:
            self.clear(client_id=client_id, session_id=session_id)
            return None

        now = datetime.now(timezone.utc)
        with self._lock:
            connection = self._require_connection()
            connection.execute(
                """
                INSERT INTO ui_drafts (client_id, session_id, content, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_id, session_id) DO UPDATE SET
                    content = excluded.content,
                    updated_at = excluded.updated_at
                """,
                (client_id, session_id, content, now.isoformat()),
            )
            connection.commit()
        return UIDraft(client_id, session_id, content, now)

    def load(
        self,
        *,
        client_id: str,
        session_id: str,
    ) -> UIDraft | None:
        client_id = _identifier(client_id, "client_id")
        session_id = _identifier(session_id, "session_id")
        with self._lock:
            row = self._require_connection().execute(
                """
                SELECT client_id, session_id, content, updated_at
                FROM ui_drafts
                WHERE client_id = ? AND session_id = ?
                """,
                (client_id, session_id),
            ).fetchone()
        if row is None:
            return None
        return UIDraft(
            client_id=row[0],
            session_id=row[1],
            content=row[2],
            updated_at=datetime.fromisoformat(row[3]),
        )

    def clear(
        self,
        *,
        client_id: str,
        session_id: str,
    ) -> None:
        client_id = _identifier(client_id, "client_id")
        session_id = _identifier(session_id, "session_id")
        with self._lock:
            connection = self._require_connection()
            connection.execute(
                "DELETE FROM ui_drafts WHERE client_id = ? AND session_id = ?",
                (client_id, session_id),
            )
            connection.commit()

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("UIDraftStore is closed")
        return self._connection
