"""Durable evidence-only storage for full ChatGPT conversation exports."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from sofia.memory.chatgpt_export import ChatGPTExportBatch


class ChatGPTExportEvidenceStore:
    """Persist source text without promoting it into cognitive memory."""

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS chatgpt_export_batch (
                        source_digest TEXT PRIMARY KEY,
                        observed_at TEXT NOT NULL,
                        conversation_count INTEGER NOT NULL,
                        message_count INTEGER NOT NULL,
                        skipped_do_not_remember INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS chatgpt_export_conversation (
                        source_digest TEXT NOT NULL,
                        conversation_id TEXT NOT NULL,
                        title TEXT,
                        source_created_at TEXT,
                        source_updated_at TEXT,
                        memory_scope TEXT,
                        is_archived INTEGER NOT NULL,
                        PRIMARY KEY (source_digest, conversation_id),
                        FOREIGN KEY (source_digest)
                            REFERENCES chatgpt_export_batch(source_digest)
                            ON DELETE RESTRICT
                    );
                    CREATE TABLE IF NOT EXISTS chatgpt_export_message (
                        source_digest TEXT NOT NULL,
                        conversation_id TEXT NOT NULL,
                        message_id TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        source_created_at TEXT,
                        position INTEGER NOT NULL,
                        PRIMARY KEY (source_digest, conversation_id, message_id),
                        UNIQUE (source_digest, source_id),
                        FOREIGN KEY (source_digest, conversation_id)
                            REFERENCES chatgpt_export_conversation(
                                source_digest, conversation_id
                            )
                            ON DELETE RESTRICT
                    );
                    CREATE INDEX IF NOT EXISTS chatgpt_export_message_source
                        ON chatgpt_export_message(source_id);
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def save(self, batch: ChatGPTExportBatch) -> bool:
        if not isinstance(batch, ChatGPTExportBatch):
            raise TypeError("batch must be ChatGPTExportBatch")
        with closing(self._connect()) as db:
            existing = db.execute(
                "SELECT conversation_count, message_count, "
                "skipped_do_not_remember FROM chatgpt_export_batch "
                "WHERE source_digest=?",
                (batch.source_digest,),
            ).fetchone()
            expected = (
                len(batch.conversations),
                batch.message_count,
                batch.skipped_do_not_remember,
            )
            if existing is not None:
                if tuple(existing) != expected:
                    raise RuntimeError(
                        "ChatGPT export digest conflicts with stored metadata"
                    )
                return False

            with db:
                db.execute(
                    "INSERT INTO chatgpt_export_batch "
                    "(source_digest, observed_at, conversation_count, "
                    "message_count, skipped_do_not_remember) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        batch.source_digest,
                        batch.observed_at.isoformat(),
                        len(batch.conversations),
                        batch.message_count,
                        batch.skipped_do_not_remember,
                    ),
                )
                for conversation in batch.conversations:
                    db.execute(
                        "INSERT INTO chatgpt_export_conversation "
                        "(source_digest, conversation_id, title, "
                        "source_created_at, source_updated_at, memory_scope, "
                        "is_archived) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            batch.source_digest,
                            conversation.conversation_id,
                            conversation.title,
                            (
                                conversation.source_created_at.isoformat()
                                if conversation.source_created_at is not None
                                else None
                            ),
                            (
                                conversation.source_updated_at.isoformat()
                                if conversation.source_updated_at is not None
                                else None
                            ),
                            conversation.memory_scope,
                            int(conversation.is_archived),
                        ),
                    )
                    for message in conversation.messages:
                        db.execute(
                            "INSERT INTO chatgpt_export_message "
                            "(source_digest, conversation_id, message_id, "
                            "source_id, role, content, source_created_at, "
                            "position) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                batch.source_digest,
                                conversation.conversation_id,
                                message.message_id,
                                message.source_id,
                                message.role,
                                message.content,
                                (
                                    message.source_created_at.isoformat()
                                    if message.source_created_at is not None
                                    else None
                                ),
                                message.position,
                            ),
                        )
        return True

    def counts(self, source_digest: str) -> tuple[int, int, int] | None:
        if not isinstance(source_digest, str) or not source_digest.strip():
            raise ValueError("source_digest must be nonempty")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT conversation_count, message_count, "
                "skipped_do_not_remember FROM chatgpt_export_batch "
                "WHERE source_digest=?",
                (source_digest,),
            ).fetchone()
        return None if row is None else tuple(int(value) for value in row)

    def messages_for_conversation(
        self,
        source_digest: str,
        conversation_id: str,
    ) -> tuple[tuple[str, str, str, int], ...]:
        if not source_digest.strip() or not conversation_id.strip():
            raise ValueError("source_digest and conversation_id are required")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT message_id, role, content, position "
                "FROM chatgpt_export_message "
                "WHERE source_digest=? AND conversation_id=? "
                "ORDER BY position ASC, message_id ASC",
                (source_digest, conversation_id),
            ).fetchall()
        return tuple(
            (str(row[0]), str(row[1]), str(row[2]), int(row[3]))
            for row in rows
        )
