"""Durable provenance-backed memory candidate lifecycle for PKG-MEM.

Conversation originals remain authoritative source evidence. This store records
derived candidates and their explicit lifecycle; it never edits or deletes the
source conversation records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import UUID

from sofia.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.memory.retrieval_projection import SourceMessage


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise TypeError("timestamp must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


class DurableMemoryCandidateStore:
    def __init__(self, database_path: Path | str) -> None:
        if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
            raise ValueError("an on-disk SQLite path is required")
        if str(database_path) == ":memory:":
            raise ValueError("in-memory storage is not durable")
        target = Path(database_path)
        if not target.parent.exists():
            raise FileNotFoundError("memory database parent directory must exist")
        self._db = sqlite3.connect(target, timeout=3.0)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA busy_timeout = 3000")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS memory_candidate (
                candidate_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS memory_candidate_source (
                candidate_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                message_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                position INTEGER NOT NULL,
                PRIMARY KEY (candidate_id, ordinal),
                FOREIGN KEY (candidate_id) REFERENCES memory_candidate(candidate_id)
            )
        """)
        self._db.commit()

    def propose(self, candidate: MemoryCandidate) -> None:
        if not isinstance(candidate, MemoryCandidate):
            raise TypeError("candidate must be a MemoryCandidate")
        try:
            with self._db:
                self._db.execute(
                    """INSERT INTO memory_candidate
                       (candidate_id, content, created_at, status)
                       VALUES (?, ?, ?, ?)""",
                    (str(candidate.candidate_id), candidate.content,
                     _utc(candidate.created_at), CandidateStatus.PROPOSED.value),
                )
                for ordinal, source in enumerate(candidate.sources):
                    self._db.execute(
                        """INSERT INTO memory_candidate_source
                           (candidate_id, ordinal, message_id, session_id, role,
                            content, created_at, position)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (str(candidate.candidate_id), ordinal, source.message_id,
                         source.session_id, source.role, source.content,
                         _utc(source.created_at), source.position),
                    )
        except sqlite3.IntegrityError as exc:
            raise ValueError("candidate ID already exists") from exc

    def get(self, candidate_id: UUID) -> MemoryCandidate | None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        row = self._db.execute(
            "SELECT content, created_at FROM memory_candidate WHERE candidate_id = ?",
            (str(candidate_id),),
        ).fetchone()
        if row is None:
            return None
        source_rows = self._db.execute(
            """SELECT message_id, session_id, role, content, created_at, position
               FROM memory_candidate_source
               WHERE candidate_id = ? ORDER BY ordinal ASC""",
            (str(candidate_id),),
        ).fetchall()
        sources = tuple(
            SourceMessage(
                message_id=item[0], session_id=item[1], role=item[2],
                content=item[3], created_at=datetime.fromisoformat(item[4]),
                position=item[5],
            )
            for item in source_rows
        )
        return MemoryCandidate(
            candidate_id=candidate_id,
            content=row[0],
            sources=sources,
            created_at=datetime.fromisoformat(row[1]),
        )

    def candidate_ids_for_source(self, *, session_id: str, message_id: str) -> tuple[UUID, ...]:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be nonempty")
        if not isinstance(message_id, str) or not message_id.strip():
            raise ValueError("message_id must be nonempty")
        rows = self._db.execute(
            """SELECT candidate_id FROM memory_candidate_source
               WHERE session_id = ? AND message_id = ? ORDER BY candidate_id ASC""",
            (session_id, message_id),
        ).fetchall()
        return tuple(UUID(row[0]) for row in rows)

    def status(self, candidate_id: UUID) -> CandidateStatus | None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        row = self._db.execute(
            "SELECT status FROM memory_candidate WHERE candidate_id = ?",
            (str(candidate_id),),
        ).fetchone()
        if row is None:
            return None
        try:
            return CandidateStatus(row[0])
        except ValueError:
            raise RuntimeError("stored memory candidate has invalid lifecycle status")

    def promote(self, candidate_id: UUID) -> None:
        self._transition(candidate_id, CandidateStatus.PROPOSED, CandidateStatus.PROMOTED)

    def reject(self, candidate_id: UUID) -> None:
        self._transition(candidate_id, CandidateStatus.PROPOSED, CandidateStatus.REJECTED)

    def revoke(self, candidate_id: UUID) -> None:
        self._transition(candidate_id, CandidateStatus.PROMOTED, CandidateStatus.REVOKED)

    def _transition(self, candidate_id: UUID, expected: CandidateStatus,
                    target: CandidateStatus) -> None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        with self._db:
            cursor = self._db.execute(
                """UPDATE memory_candidate SET status = ?
                   WHERE candidate_id = ? AND status = ?""",
                (target.value, str(candidate_id), expected.value),
            )
        if cursor.rowcount == 1:
            return
        if self.status(candidate_id) is None:
            raise LookupError("candidate does not exist")
        raise ValueError(f"candidate must be {expected.value} before {target.value}")

    def close(self) -> None:
        self._db.close()
