from datetime import datetime
from pathlib import Path
import sqlite3

from sofia.conversation.model import (
    ConversationMessage,
    ConversationRole,
)


class ConversationStore:
    """
    Persistent storage for conversation messages.

    Conversation history is distinct from long-term memory.
    Messages belong to a session and are retrieved in creation order.
    """

    def __init__(
        self,
        database_path: Path | str,
    ) -> None:
        self._database_path = database_path

        self._connection = sqlite3.connect(
            str(database_path)
        )

        self._initialize_database()

    def _initialize_database(self) -> None:
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

        self._connection.commit()

    def list_messages(
        self,
        session_id: str,
    ) -> tuple[ConversationMessage, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                session_id,
                role,
                content,
                created_at
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