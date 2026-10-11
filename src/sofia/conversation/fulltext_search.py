"""Optional, operator-built FTS5 index for canonical conversation originals.

Reuses SQLite FTS5 techniques already used by KnowledgeIndex, but keeps
personal transcripts in their original conversation tables and audience
boundaries. Index creation/backfill is an EXPLICIT offline maintenance
operation, never invoked by production chat startup. No second database.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3

from sofia.conversation.model import ConversationMessage, ConversationRole


@dataclass(frozen=True, slots=True)
class ConversationSearchStatus:
    ready: bool
    row_count: int
    source: str = "canonical_sofia_db"


class ConversationFullTextSearch:
    """One canonical SQLite transcript index, no model calls or embeddings."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("canonical conversation database required")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def status(self) -> ConversationSearchStatus:
        """Inspection only. Absent index means no search guarantee."""
        with closing(self._connect()) as db:
            marker = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='conversation_fts_meta'"
            ).fetchone()
            if marker is None:
                return ConversationSearchStatus(False, 0)
            row = db.execute(
                "SELECT is_ready, indexed_source_count FROM conversation_fts_meta "
                "WHERE singleton=1"
            ).fetchone()
            return ConversationSearchStatus(
                bool(row["is_ready"]) if row is not None else False,
                int(row["indexed_source_count"]) if row is not None else 0,
            )

    def rebuild_offline(self, *, independently_authorized: bool) -> ConversationSearchStatus:
        """Exclusive SQLite maintenance: potentially expensive on decades of data.

        Must run on the single fenced writer during an approved maintenance
        window. Does not delete or rewrite source messages. A failed rebuild
        rolls back its readiness marker and index in the same transaction.
        """
        if independently_authorized is not True:
            raise PermissionError("index rebuild needs reviewed maintenance approval")
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='conversation_messages'"
                ).fetchone() is None:
                    raise ValueError("canonical conversation source table missing")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS conversation_fts_meta("
                    "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
                    "is_ready INTEGER NOT NULL, indexed_source_count INTEGER NOT NULL)"
                )
                db.execute(
                    "INSERT INTO conversation_fts_meta VALUES(1,0,0) "
                    "ON CONFLICT(singleton) DO UPDATE SET is_ready=0"
                )
                db.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS conversation_messages_fts "
                    "USING fts5(content, content='conversation_messages', "
                    "content_rowid='rowid', tokenize='unicode61')"
                )
                db.execute(
                    "CREATE TRIGGER IF NOT EXISTS conversation_source_fts_insert "
                    "AFTER INSERT ON conversation_messages BEGIN "
                    "INSERT INTO conversation_messages_fts(rowid,content) "
                    "VALUES(new.rowid,new.content); END"
                )
                db.execute(
                    "CREATE TRIGGER IF NOT EXISTS conversation_source_fts_delete "
                    "AFTER DELETE ON conversation_messages BEGIN "
                    "INSERT INTO conversation_messages_fts("
                    "conversation_messages_fts,rowid,content) "
                    "VALUES('delete',old.rowid,old.content); END"
                )
                db.execute(
                    "CREATE TRIGGER IF NOT EXISTS conversation_source_fts_update "
                    "AFTER UPDATE ON conversation_messages BEGIN "
                    "INSERT INTO conversation_messages_fts("
                    "conversation_messages_fts,rowid,content) "
                    "VALUES('delete',old.rowid,old.content); "
                    "INSERT INTO conversation_messages_fts(rowid,content) "
                    "VALUES(new.rowid,new.content); END"
                )
                db.execute(
                    "INSERT INTO conversation_messages_fts(conversation_messages_fts) "
                    "VALUES('rebuild')"
                )
                count = int(db.execute(
                    "SELECT COUNT(*) FROM conversation_messages"
                ).fetchone()[0])
                db.execute(
                    "UPDATE conversation_fts_meta SET indexed_source_count=?,"
                    "is_ready=1 WHERE singleton=1", (count,),
                )
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return ConversationSearchStatus(True, count)

    def keyword_search(
        self, *, session_id: str, terms: tuple[str, ...],
        limit: int = 16, user_only: bool = False,
    ) -> tuple[ConversationMessage, ...]:
        """FTS token search over an authorized session. No cross-session joins.

        The caller must enforce the session's current authenticated principal
        and audience binding before using or displaying returned text.
        """
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("exact authorized session ID required")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded search limit required")
        if not isinstance(terms, tuple) or not 1 <= len(terms) <= 8 or any(
            not isinstance(s, str) or not s.isascii()
            or not s.isalnum() or not 2 <= len(s) <= 48 for s in terms
        ):
            raise ValueError("1–8 alphanumeric search terms required")
        if not self.status().ready:
            raise RuntimeError("full-text index has not been explicitly rebuilt")
        expression = " OR ".join('"' + word.lower() + '"' for word in terms)
        extra = "AND m.role='user' " if user_only else ""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT m.id,m.session_id,m.role,m.content,m.created_at "
                "FROM conversation_messages_fts "
                "JOIN conversation_messages AS m "
                "ON m.rowid=conversation_messages_fts.rowid "
                "WHERE conversation_messages_fts MATCH ? "
                "AND m.session_id=? " + extra +
                "ORDER BY bm25(conversation_messages_fts),"
                "m.created_at DESC,m.id DESC LIMIT ?",
                (expression, session_id, limit),
            ).fetchall()
        return tuple(
            ConversationMessage(
                id=row["id"], session_id=row["session_id"],
                role=ConversationRole(row["role"]), content=row["content"],
                created_at=datetime.fromisoformat(row["created_at"]),
            ) for row in rows
        )
