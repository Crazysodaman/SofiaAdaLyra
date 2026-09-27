from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
from threading import RLock

from sofia.memory.chatgpt_import import ChatGPTMemoryImportBatch, ChatGPTMemoryImportItem


class ChatGPTMemoryImportStore:
    """
    Durable exact-source storage for imported ChatGPT memory dumps.

    Imported data is evidence only. This store does not promote imported text
    into normal cognition or reviewed long-term memory.
    """

    def __init__(self, database_path: Path | str) -> None:
        self._database_path = Path(database_path)
        self._lock = RLock()
        self._connection = sqlite3.connect(
            str(self._database_path),
            timeout=5.0,
            check_same_thread=False,
        )
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            db = self._require_connection()
            db.execute("PRAGMA foreign_keys = ON")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS chatgpt_memory_import_batch (
                    source_digest TEXT PRIMARY KEY,
                    observed_at TEXT NOT NULL,
                    original_payload TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS chatgpt_memory_import_item (
                    source_digest TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    source_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_created_at TEXT,
                    PRIMARY KEY (source_digest, ordinal),
                    UNIQUE (source_digest, source_id),
                    FOREIGN KEY (source_digest)
                        REFERENCES chatgpt_memory_import_batch(source_digest)
                        ON DELETE RESTRICT
                )
                """
            )
            db.commit()

    def save(
        self,
        batch: ChatGPTMemoryImportBatch,
        *,
        original_payload: str,
    ) -> bool:
        """
        Persist one parsed dump.

        Returns True when a new batch was stored and False when the exact same
        payload was already present. A digest collision with different payload
        fails closed.
        """
        if not isinstance(batch, ChatGPTMemoryImportBatch):
            raise TypeError("batch must be a ChatGPTMemoryImportBatch")
        if not isinstance(original_payload, str) or not original_payload:
            raise ValueError("original_payload must be a nonempty string")

        with self._lock:
            db = self._require_connection()
            existing = db.execute(
                """
                SELECT original_payload
                FROM chatgpt_memory_import_batch
                WHERE source_digest = ?
                """,
                (batch.source_digest,),
            ).fetchone()

            if existing is not None:
                if existing[0] != original_payload:
                    raise RuntimeError(
                        "ChatGPT memory import digest collision detected"
                    )
                return False

            with db:
                db.execute(
                    """
                    INSERT INTO chatgpt_memory_import_batch (
                        source_digest,
                        observed_at,
                        original_payload
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        batch.source_digest,
                        batch.observed_at.isoformat(),
                        original_payload,
                    ),
                )
                for ordinal, item in enumerate(batch.items):
                    db.execute(
                        """
                        INSERT INTO chatgpt_memory_import_item (
                            source_digest,
                            ordinal,
                            source_id,
                            content,
                            source_created_at
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            batch.source_digest,
                            ordinal,
                            item.source_id,
                            item.content,
                            (
                                item.source_created_at.isoformat()
                                if item.source_created_at is not None
                                else None
                            ),
                        ),
                    )
        return True


    def load_batch(
        self,
        source_digest: str,
    ) -> ChatGPTMemoryImportBatch | None:
        if not isinstance(source_digest, str) or not source_digest.strip():
            raise ValueError("source_digest must be a nonempty string")
        with self._lock:
            db = self._require_connection()
            batch = db.execute(
                """
                SELECT observed_at
                FROM chatgpt_memory_import_batch
                WHERE source_digest = ?
                """,
                (source_digest,),
            ).fetchone()
            if batch is None:
                return None
            rows = db.execute(
                """
                SELECT source_id, content, source_created_at
                FROM chatgpt_memory_import_item
                WHERE source_digest = ?
                ORDER BY ordinal ASC
                """,
                (source_digest,),
            ).fetchall()
        return ChatGPTMemoryImportBatch(
            source_digest=source_digest,
            observed_at=datetime.fromisoformat(batch[0]),
            items=tuple(
                ChatGPTMemoryImportItem(
                    source_id=row[0],
                    content=row[1],
                    source_created_at=(
                        None
                        if row[2] is None
                        else datetime.fromisoformat(row[2])
                    ),
                )
                for row in rows
            ),
        )

    def has_batch(self, source_digest: str) -> bool:
        if not isinstance(source_digest, str) or not source_digest.strip():
            raise ValueError("source_digest must be a nonempty string")
        with self._lock:
            row = self._require_connection().execute(
                """
                SELECT 1
                FROM chatgpt_memory_import_batch
                WHERE source_digest = ?
                """,
                (source_digest,),
            ).fetchone()
        return row is not None

    def original_payload(self, source_digest: str) -> str | None:
        if not isinstance(source_digest, str) or not source_digest.strip():
            raise ValueError("source_digest must be a nonempty string")
        with self._lock:
            row = self._require_connection().execute(
                """
                SELECT original_payload
                FROM chatgpt_memory_import_batch
                WHERE source_digest = ?
                """,
                (source_digest,),
            ).fetchone()
        return None if row is None else row[0]

    def list_imports(self) -> tuple[tuple[str, datetime, int], ...]:
        with self._lock:
            rows = self._require_connection().execute(
                """
                SELECT
                    batch.source_digest,
                    batch.observed_at,
                    COUNT(item.ordinal)
                FROM chatgpt_memory_import_batch AS batch
                LEFT JOIN chatgpt_memory_import_item AS item
                    ON item.source_digest = batch.source_digest
                GROUP BY batch.source_digest, batch.observed_at
                ORDER BY batch.observed_at ASC, batch.source_digest ASC
                """
            ).fetchall()
        return tuple(
            (
                row[0],
                datetime.fromisoformat(row[1]),
                int(row[2]),
            )
            for row in rows
        )

    def close(self) -> None:
        with self._lock:
            if self._connection is None:
                return
            self._connection.close()
            self._connection = None

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("ChatGPT memory import store is closed")
        return self._connection
