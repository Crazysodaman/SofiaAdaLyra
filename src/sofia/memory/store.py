from datetime import datetime
from pathlib import Path
import sqlite3

from sofia.memory.model import MemoryRecord


class MemoryStore:
    """
    Memory storage with optional SQLite persistence.

    Without a database path, the store preserves the original
    in-memory behavior and object identity semantics.

    With a database path, memories are persisted to SQLite and
    can survive across store instances and process restarts.
    """

    def __init__(
        self,
        database_path: Path | str | None = None,
    ) -> None:
        self._database_path = database_path
        self._memories: dict[str, MemoryRecord] = {}

        self._connection: sqlite3.Connection | None = None

        if database_path is not None:
            self._connection = sqlite3.connect(
                str(database_path)
            )

            self._initialize_database()

    def _initialize_database(self) -> None:
        if self._connection is None:
            return

        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        self._connection.commit()

    def save(self, memory: MemoryRecord) -> None:
        if self._connection is None:
            self._memories[memory.id] = memory
            return

        self._connection.execute(
            """
            INSERT INTO memories (
                id,
                content,
                created_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                created_at = excluded.created_at
            """,
            (
                memory.id,
                memory.content,
                memory.created_at.isoformat(),
            ),
        )

        self._connection.commit()

    def get(self, memory_id: str) -> MemoryRecord | None:
        if self._connection is None:
            return self._memories.get(memory_id)

        row = self._connection.execute(
            """
            SELECT id, content, created_at
            FROM memories
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()

        if row is None:
            return None

        return MemoryRecord(
            id=row[0],
            content=row[1],
            created_at=datetime.fromisoformat(row[2]),
        )

    def close(self) -> None:
        """
        Close the SQLite connection when persistence is enabled.
        """

        if self._connection is not None:
            self._connection.close()
            self._connection = None