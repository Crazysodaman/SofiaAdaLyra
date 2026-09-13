from datetime import datetime, timezone
from pathlib import Path
import sqlite3
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
    """

    def __init__(
        self,
        database_path: Path | str,
    ) -> None:
        self._connection = sqlite3.connect(
            str(database_path)
        )

        self._initialize_database()

    def _initialize_database(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        self._connection.execute(
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

        self._connection.commit()

    def create_session(self) -> ConversationSession:
        now = datetime.now(timezone.utc)
        session_id = str(uuid4())

        self._connection.execute(
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

        self._connection.commit()

        return ConversationSession(
            id=session_id,
            created_at=now,
            updated_at=now,
        )

    def get_session(
        self,
        session_id: str,
    ) -> ConversationSession | None:
        row = self._connection.execute(
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
        self._connection.execute(
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

        self._connection.execute(
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

        self._connection.commit()

    def list_messages(
        self,
        session_id: str,
    ) -> tuple[ConversationMessage, ...]:
        rows = self._connection.execute(
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
        self._connection.close()