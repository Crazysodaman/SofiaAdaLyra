from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4

from sofia.conversation.model import (
    ConversationMessage,
    ConversationRole,
    ConversationSession,
)


class ConversationStore:
    """
    SQLite-backed persistent conversation storage.

    Stores conversation sessions and their messages.

    The database path is persistent configuration.
    The SQLite connection is a runtime resource and may be
    opened and closed multiple times during the store lifetime.
    """

    def __init__(
        self,
        database_path: Path | str,
    ) -> None:
        self._database_path = Path(database_path)
        self._connection: sqlite3.Connection | None = None
        self._lock = RLock()

        self.open()

    def open(self) -> None:
        """
        Open the SQLite connection and initialize the database.

        Opening an already-open store is a no-op.
        """

        with self._lock:
            if self._connection is not None:
                return

            self._connection = sqlite3.connect(
                str(self._database_path),
                timeout=5.0,
                check_same_thread=False,
            )

            self._initialize_database()

    def _initialize_database(self) -> None:
        connection = self._require_connection()

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        connection.commit()

    def create_session(self) -> ConversationSession:
        with self._lock:
            connection = self._require_connection()

            now = datetime.now(timezone.utc)
            session_id = str(uuid4())

            connection.execute(
                """
                INSERT INTO conversation_sessions (
                    id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    session_id,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

            connection.commit()

        return ConversationSession(
            id=session_id,
            created_at=now,
            updated_at=now,
        )

    def get_session(
        self,
        session_id: str,
    ) -> ConversationSession | None:
        with self._lock:
            connection = self._require_connection()

            row = connection.execute(
                """
                SELECT id, created_at, updated_at
                FROM conversation_sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()

        if row is None:
            return None

        return ConversationSession(
            id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            updated_at=datetime.fromisoformat(row[2]),
        )

    def save(
        self,
        message: ConversationMessage,
    ) -> None:
        with self._lock:
            connection = self._require_connection()

            connection.execute(
                """
                INSERT INTO conversation_messages (
                    id,
                    session_id,
                    role,
                    content,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    session_id = excluded.session_id,
                    role = excluded.role,
                    content = excluded.content,
                    created_at = excluded.created_at
                """,
                (
                    message.id,
                    message.session_id,
                    message.role.value,
                    message.content,
                    message.created_at.isoformat(),
                ),
            )

            connection.execute(
                """
                UPDATE conversation_sessions
                SET updated_at = ?
                WHERE id = ?
                AND updated_at < ?
                """,
                (
                    message.created_at.isoformat(),
                    message.session_id,
                    message.created_at.isoformat(),
                ),
            )

            connection.commit()

    def list_messages(
        self,
        session_id: str,
    ) -> tuple[ConversationMessage, ...]:
        with self._lock:
            connection = self._require_connection()

            rows = connection.execute(
                """
                SELECT id, session_id, role, content, created_at
                FROM conversation_messages
                WHERE session_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            ).fetchall()

        return tuple(
            ConversationMessage(
                id=row[0],
                session_id=row[1],
                role=ConversationRole(row[2]),
                content=row[3],
                created_at=datetime.fromisoformat(row[4]),
            )
            for row in rows
        )

    def close(self) -> None:
        """
        Close the SQLite connection.

        Persistent database contents remain available for a
        subsequent call to open().
        """

        with self._lock:
            if self._connection is None:
                return

            self._connection.close()
            self._connection = None

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError(
                "ConversationStore must be opened before use."
            )

        return self._connection