"""Durable evidence-only storage for full ChatGPT conversation exports."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
import re
import sqlite3

from sofia.memory.chatgpt_export import ChatGPTExportBatch
from sofia.memory.historical import HistoricalConversationEvidence
from sofia.social.principals import SPARKS_PRINCIPAL_ID


_SEARCH_TOKEN = re.compile(r"[A-Za-z0-9À-ÿ']+")
_SEARCH_STOPWORDS = frozenset({
    "a", "about", "an", "and", "are", "as", "at", "be", "been", "but",
    "by", "can", "could", "did", "do", "does", "for", "from", "had", "has",
    "have", "he", "her", "hers", "him", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "me", "my", "of", "on", "or", "our",
    "ours", "she", "should", "so", "that", "the", "their", "theirs", "them",
    "they", "this", "to", "us", "was", "we", "were", "what", "when",
    "where", "which", "who", "why", "will", "with", "would", "you", "your",
    "yours",
})


def _search_tokens(*values: str, limit: int = 256) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        for raw in _SEARCH_TOKEN.findall(value.casefold()):
            token = raw.strip("'")
            if (
                len(token) < 2
                or token in _SEARCH_STOPWORDS
                or token in seen
            ):
                continue
            seen.add(token)
            ordered.append(token)
            if len(ordered) >= limit:
                return tuple(ordered)
    return tuple(ordered)


def _optional_datetime(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


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
                        principal_id TEXT NOT NULL,
                        conversation_count INTEGER NOT NULL,
                        message_count INTEGER NOT NULL,
                        attachment_count INTEGER NOT NULL,
                        skipped_do_not_remember INTEGER NOT NULL,
                        skipped_memory_disabled INTEGER NOT NULL
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
                    CREATE TABLE IF NOT EXISTS chatgpt_export_attachment (
                        source_digest TEXT NOT NULL,
                        conversation_id TEXT NOT NULL,
                        message_id TEXT NOT NULL,
                        ordinal INTEGER NOT NULL,
                        asset_id TEXT NOT NULL,
                        file_name TEXT,
                        content_type TEXT,
                        PRIMARY KEY (
                            source_digest, conversation_id, message_id, ordinal
                        ),
                        FOREIGN KEY (
                            source_digest, conversation_id, message_id
                        )
                            REFERENCES chatgpt_export_message(
                                source_digest, conversation_id, message_id
                            )
                            ON DELETE RESTRICT
                    );
                    CREATE INDEX IF NOT EXISTS chatgpt_export_message_source
                        ON chatgpt_export_message(source_id);
                    CREATE TABLE IF NOT EXISTS chatgpt_export_search_token (
                        source_digest TEXT NOT NULL,
                        conversation_id TEXT NOT NULL,
                        message_id TEXT NOT NULL,
                        token TEXT NOT NULL,
                        PRIMARY KEY (
                            source_digest, conversation_id, message_id, token
                        ),
                        FOREIGN KEY (
                            source_digest, conversation_id, message_id
                        )
                            REFERENCES chatgpt_export_message(
                                source_digest, conversation_id, message_id
                            )
                            ON DELETE RESTRICT
                    );
                    CREATE INDEX IF NOT EXISTS chatgpt_export_search_token_lookup
                        ON chatgpt_export_search_token(token);
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def save(
        self,
        batch: ChatGPTExportBatch,
        *,
        principal_id: str = SPARKS_PRINCIPAL_ID,
    ) -> bool:
        if not isinstance(batch, ChatGPTExportBatch):
            raise TypeError("batch must be ChatGPTExportBatch")
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id must be nonempty")
        with closing(self._connect()) as db:
            existing = db.execute(
                "SELECT principal_id, conversation_count, message_count, "
                "attachment_count, skipped_do_not_remember, "
                "skipped_memory_disabled "
                "FROM chatgpt_export_batch "
                "WHERE source_digest=?",
                (batch.source_digest,),
            ).fetchone()
            expected = (
                principal_id,
                len(batch.conversations),
                batch.message_count,
                batch.attachment_count,
                batch.skipped_do_not_remember,
                batch.skipped_memory_disabled,
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
                    "(source_digest, observed_at, principal_id, "
                    "conversation_count, message_count, attachment_count, "
                    "skipped_do_not_remember, skipped_memory_disabled) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        batch.source_digest,
                        batch.observed_at.isoformat(),
                        principal_id,
                        len(batch.conversations),
                        batch.message_count,
                        batch.attachment_count,
                        batch.skipped_do_not_remember,
                        batch.skipped_memory_disabled,
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
                        for ordinal, attachment in enumerate(
                            message.attachments
                        ):
                            db.execute(
                                "INSERT INTO chatgpt_export_attachment "
                                "(source_digest, conversation_id, message_id, "
                                "ordinal, asset_id, file_name, content_type) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (
                                    batch.source_digest,
                                    conversation.conversation_id,
                                    message.message_id,
                                    ordinal,
                                    attachment.asset_id,
                                    attachment.file_name,
                                    attachment.content_type,
                                ),
                            )
                        for token in _search_tokens(
                            conversation.title or "",
                            message.content,
                        ):
                            db.execute(
                                "INSERT INTO chatgpt_export_search_token "
                                "(source_digest, conversation_id, message_id, token) "
                                "VALUES (?, ?, ?, ?)",
                                (
                                    batch.source_digest,
                                    conversation.conversation_id,
                                    message.message_id,
                                    token,
                                ),
                            )
        return True

    def counts(
        self,
        source_digest: str,
    ) -> tuple[int, int, int, int, int] | None:
        if not isinstance(source_digest, str) or not source_digest.strip():
            raise ValueError("source_digest must be nonempty")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT conversation_count, message_count, attachment_count, "
                "skipped_do_not_remember, skipped_memory_disabled "
                "FROM chatgpt_export_batch "
                "WHERE source_digest=?",
                (source_digest,),
            ).fetchone()
        return None if row is None else tuple(int(value) for value in row)


    def search_relevant(
        self,
        query: str,
        *,
        principal_id: str,
        limit: int = 4,
        budget_characters: int = 3000,
    ) -> tuple[HistoricalConversationEvidence, ...]:
        """Return bounded principal-scoped historical source evidence."""
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id must be nonempty")
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        if type(budget_characters) is not int or budget_characters < 256:
            raise ValueError("budget_characters must be at least 256")

        terms = _search_tokens(query, limit=8)
        if not terms:
            return ()

        placeholders = ",".join("?" for _ in terms)
        with closing(self._connect()) as db:
            rows = db.execute(
                f"""
                SELECT
                    m.source_digest,
                    m.conversation_id,
                    m.message_id,
                    m.role,
                    c.title,
                    m.content,
                    m.source_created_at,
                    m.position,
                    COUNT(DISTINCT s.token) AS matched_terms
                FROM chatgpt_export_search_token AS s
                JOIN chatgpt_export_message AS m
                  ON m.source_digest=s.source_digest
                 AND m.conversation_id=s.conversation_id
                 AND m.message_id=s.message_id
                JOIN chatgpt_export_conversation AS c
                  ON c.source_digest=m.source_digest
                 AND c.conversation_id=m.conversation_id
                JOIN chatgpt_export_batch AS b
                  ON b.source_digest=m.source_digest
                WHERE b.principal_id=?
                  AND s.token IN ({placeholders})
                  AND length(trim(m.content)) > 0
                GROUP BY
                    m.source_digest,
                    m.conversation_id,
                    m.message_id,
                    m.role,
                    c.title,
                    m.content,
                    m.source_created_at,
                    m.position
                ORDER BY
                    matched_terms DESC,
                    CASE m.role WHEN 'user' THEN 1 ELSE 0 END DESC,
                    COALESCE(m.source_created_at, '') DESC,
                    m.position DESC
                LIMIT ?
                """,
                (
                    principal_id,
                    *terms,
                    max(limit * 4, limit),
                ),
            ).fetchall()

        results: list[HistoricalConversationEvidence] = []
        per_conversation: dict[str, int] = {}
        remaining = budget_characters
        for row in rows:
            conversation_id = str(row[1])
            if per_conversation.get(conversation_id, 0) >= 2:
                continue
            content = str(row[5]).strip()
            allowance = min(1200, remaining)
            if allowance < 96:
                break
            if len(content) > allowance:
                content = content[: max(1, allowance - 1)].rstrip() + "…"
            results.append(
                HistoricalConversationEvidence(
                    source_digest=str(row[0]),
                    conversation_id=conversation_id,
                    message_id=str(row[2]),
                    role=str(row[3]),
                    title=None if row[4] is None else str(row[4]),
                    content=content,
                    source_created_at=_optional_datetime(
                        None if row[6] is None else str(row[6])
                    ),
                )
            )
            per_conversation[conversation_id] = (
                per_conversation.get(conversation_id, 0) + 1
            )
            remaining -= len(content)
            if len(results) >= limit:
                break
        return tuple(results)



    def attachments_for_message(
        self,
        source_digest: str,
        conversation_id: str,
        message_id: str,
    ) -> tuple[tuple[str, str | None, str | None], ...]:
        if not all(
            isinstance(value, str) and value.strip()
            for value in (source_digest, conversation_id, message_id)
        ):
            raise ValueError(
                "source_digest, conversation_id and message_id are required"
            )
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT asset_id, file_name, content_type "
                "FROM chatgpt_export_attachment "
                "WHERE source_digest=? AND conversation_id=? AND message_id=? "
                "ORDER BY ordinal ASC",
                (source_digest, conversation_id, message_id),
            ).fetchall()
        return tuple(
            (
                str(row[0]),
                None if row[1] is None else str(row[1]),
                None if row[2] is None else str(row[2]),
            )
            for row in rows
        )
