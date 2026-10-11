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

    @property
    def database_path(self) -> Path:
        """Return the exact SQLite file backing this conversation store."""
        return self._database_path

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

            try:
                self._initialize_database()
            except BaseException:
                self.close()
                raise

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

        # Keyset pagination for decades of history. Do not use OFFSET for
        # long-lived sessions: its cost increases with the skipped rows.
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversation_session_cursor "
            "ON conversation_messages(session_id, created_at, id)"
        )
        connection.commit()

    def create_session(self) -> ConversationSession:
        with self._lock:
            connection = self._require_connection()
            with connection:
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
            with connection:
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

    def list_messages_page(
        self, session_id: str, *,
        after: tuple[datetime, str] | None = None,
        limit: int = 100,
    ) -> tuple[ConversationMessage, ...]:
        """Return a bounded stable ascending page of exactly one session.

        The (created_at, id) cursor resolves timestamp ties. The caller must
        preserve its authenticated session/audience binding; this method
        does not authorize access and never searches a different session.
        """
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be nonempty")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be in 1..500")
        if after is not None and (
            not isinstance(after, tuple) or len(after) != 2
            or not isinstance(after[0], datetime)
            or not isinstance(after[1], str) or not after[1]
        ):
            raise ValueError("after must be a (datetime, message_id) cursor")
        arguments: tuple[object, ...]
        if after is None:
            filter_sql = ""
            arguments = (session_id, limit)
        else:
            filter_sql = "AND (created_at > ? OR (created_at = ? AND id > ?))"
            stamp = after[0].isoformat()
            arguments = (session_id, stamp, stamp, after[1], limit)
        with self._lock:
            rows = self._require_connection().execute(
                "SELECT id, session_id, role, content, created_at "
                "FROM conversation_messages WHERE session_id=? "
                + filter_sql + " ORDER BY created_at, id LIMIT ?",
                arguments,
            ).fetchall()
        return tuple(
            ConversationMessage(
                id=row[0], session_id=row[1], role=ConversationRole(row[2]),
                content=row[3], created_at=datetime.fromisoformat(row[4]),
            )
            for row in rows
        )

    def recent_messages(
        self, session_id: str, *, limit: int = 24
    ) -> tuple[ConversationMessage, ...]:
        """Bounded recent context ordered oldest-to-newest for the provider."""
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be in 1..500")
        with self._lock:
            rows = self._require_connection().execute(
                "SELECT id, session_id, role, content, created_at "
                "FROM conversation_messages WHERE session_id=? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return tuple(
            ConversationMessage(
                id=row[0], session_id=row[1], role=ConversationRole(row[2]),
                content=row[3], created_at=datetime.fromisoformat(row[4]),
            )
            for row in reversed(rows)
        )

    def search_messages(
        self, session_id: str, *,
        terms: tuple[str, ...],
        exclude_message_id: str = "",
        user_only: bool = False,
        limit: int = 6,
    ) -> tuple[ConversationMessage, ...]:
        """Bounded evidence search scoped to one already-authorized session.

        This is a conservative SQLite-backed stepping stone to FTS5. It caps
        returned rows and memory; older rows still require index/FTS work.
        Source message IDs remain available for user-verifiable provenance.
        """
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("nonempty session ID required")
        if type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("bounded evidence limit required")
        if not isinstance(terms, tuple) or len(terms) > 8 or any(
            not isinstance(term, str) or not term.isascii()
            or not term.isalnum() or not 2 <= len(term) <= 48
            for term in terms
        ):
            raise ValueError("up to 8 bounded alphanumeric search terms required")
        predicates = ["session_id=?", "id<>?"]
        params: list[object] = [session_id, exclude_message_id]
        if user_only:
            predicates.append("role='user'")
        if terms:
            predicates.append("(" + " OR ".join(
                "instr(lower(content), ?) > 0" for _ in terms
            ) + ")")
            params.extend(terms)
        params.append(256)
        with self._lock:
            rows = self._require_connection().execute(
                "SELECT id, session_id, role, content, created_at FROM "
                "conversation_messages WHERE " + " AND ".join(predicates)
                + " ORDER BY created_at DESC, id DESC LIMIT ?",
                params,
            ).fetchall()
        ranked = sorted(
            rows,
            key=lambda row: (
                sum(token in row[3].casefold() for token in terms),
                row[4], row[0],
            ),
            reverse=True,
        )[:limit]
        ranked.sort(key=lambda row: (row[4], row[0]))
        return tuple(
            ConversationMessage(
                id=row[0], session_id=row[1],
                role=ConversationRole(row[2]), content=row[3],
                created_at=datetime.fromisoformat(row[4]),
            ) for row in ranked
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
