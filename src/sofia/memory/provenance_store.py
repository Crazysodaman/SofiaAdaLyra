"""Durable provenance-backed memory candidate lifecycle for PKG-MEM.

Conversation originals remain authoritative source evidence. This store records
derived candidates and their explicit lifecycle; it never edits or deletes the
source conversation records.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import UUID

from sofia.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.memory.originals import SourceMessage
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise TypeError("timestamp must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


class DurableMemoryCandidateStore:
    """Thread-safe SQLite store for reviewed memory candidates."""

    def __init__(self, database_path: Path | str) -> None:
        if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
            raise ValueError("an on-disk SQLite path is required")
        if str(database_path) == ":memory:":
            raise ValueError("in-memory storage is not durable")

        target = Path(database_path)
        if not target.parent.exists():
            raise FileNotFoundError("memory database parent directory must exist")

        self._database_path = target
        self._lock = RLock()
        # Existing canonical state is pinned before opening. Independent
        # fixture imports may still bootstrap a new test database, but only
        # the original file identity can be accessed after the first open.
        self._guard = CanonicalSQLiteGuard(target) if target.is_file() else None
        self._db: sqlite3.Connection | None = (
            self._guard.connect(timeout=3.0, check_same_thread=False)
            if self._guard is not None
            else sqlite3.connect(target, timeout=3.0, check_same_thread=False)
        )
        if self._guard is None:
            self._guard = CanonicalSQLiteGuard(target)

        with self._lock:
            db = self._require_db()
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA busy_timeout = 3000")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_candidate (
                    candidate_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    principal_id TEXT,
                    audience_id TEXT
                )
                """
            )
            existing_columns = {
                row[1]
                for row in db.execute(
                    "PRAGMA table_info(memory_candidate)"
                ).fetchall()
            }
            if "principal_id" not in existing_columns:
                db.execute(
                    "ALTER TABLE memory_candidate ADD COLUMN principal_id TEXT"
                )
            if "audience_id" not in existing_columns:
                db.execute(
                    "ALTER TABLE memory_candidate ADD COLUMN audience_id TEXT"
                )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_candidate_correction (
                    new_candidate_id TEXT PRIMARY KEY,
                    old_candidate_id TEXT NOT NULL UNIQUE,
                    linked_at TEXT NOT NULL,
                    FOREIGN KEY(new_candidate_id)
                        REFERENCES memory_candidate(candidate_id),
                    FOREIGN KEY(old_candidate_id)
                        REFERENCES memory_candidate(candidate_id),
                    CHECK(new_candidate_id != old_candidate_id)
                )
                """
            )
            db.execute(
                """
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
                    FOREIGN KEY (candidate_id)
                        REFERENCES memory_candidate(candidate_id)
                )
                """
            )
            # Canonical indexes support bounded keyset search without a
            # second memory database or an unreviewed semantic copy.
            db.execute(
                "CREATE INDEX IF NOT EXISTS memory_candidate_order_idx "
                "ON memory_candidate(status,created_at,candidate_id)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS memory_candidate_principal_order_idx "
                "ON memory_candidate(status,principal_id,created_at,candidate_id)"
            )
            db.commit()

    def propose(self, candidate: MemoryCandidate) -> None:
        if not isinstance(candidate, MemoryCandidate):
            raise TypeError("candidate must be a MemoryCandidate")

        try:
            with self._lock:
                db = self._require_db()
                with db:
                    db.execute(
                        """
                        INSERT INTO memory_candidate
                        (
                            candidate_id, content, created_at, status,
                            principal_id, audience_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(candidate.candidate_id),
                            candidate.content,
                            _utc(candidate.created_at),
                            CandidateStatus.PROPOSED.value,
                            candidate.principal_id,
                            candidate.audience_id,
                        ),
                    )
                    for ordinal, source in enumerate(candidate.sources):
                        db.execute(
                            """
                            INSERT INTO memory_candidate_source
                            (
                                candidate_id,
                                ordinal,
                                message_id,
                                session_id,
                                role,
                                content,
                                created_at,
                                position
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(candidate.candidate_id),
                                ordinal,
                                source.message_id,
                                source.session_id,
                                source.role,
                                source.content,
                                _utc(source.created_at),
                                source.position,
                            ),
                        )
        except sqlite3.IntegrityError as exc:
            raise ValueError("candidate ID already exists") from exc

    def get(self, candidate_id: UUID) -> MemoryCandidate | None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")

        with self._lock:
            db = self._require_db()
            row = db.execute(
                """
                SELECT content, created_at, principal_id, audience_id
                FROM memory_candidate
                WHERE candidate_id = ?
                """,
                (str(candidate_id),),
            ).fetchone()

            if row is None:
                return None

            source_rows = db.execute(
                """
                SELECT
                    message_id,
                    session_id,
                    role,
                    content,
                    created_at,
                    position
                FROM memory_candidate_source
                WHERE candidate_id = ?
                ORDER BY ordinal ASC
                """,
                (str(candidate_id),),
            ).fetchall()

        sources = tuple(
            SourceMessage(
                message_id=item[0],
                session_id=item[1],
                role=item[2],
                content=item[3],
                created_at=datetime.fromisoformat(item[4]),
                position=item[5],
            )
            for item in source_rows
        )

        return MemoryCandidate(
            candidate_id=candidate_id,
            content=row[0],
            sources=sources,
            created_at=datetime.fromisoformat(row[1]),
            principal_id=row[2],
            audience_id=row[3],
        )

    def iter_promoted_summaries(
        self,
        *,
        principal_id: str | None = None,
        audience_id: str | None = None,
        batch_size: int = 128,
    ) -> Iterator[tuple[UUID, str]]:
        """Stream eligible promoted content in stable chronological keyset order.

        Only candidate IDs and derived text are read during relevance ranking.
        Full original-source provenance is loaded only for selected matches.
        Each bounded SQLite page releases the lock before yielding. Concurrent
        revocation is handled by the final memory projection status rechecks.
        """
        if principal_id is not None and (
            not isinstance(principal_id, str) or not principal_id.strip()
        ):
            raise ValueError("principal_id must be None or nonempty")
        if audience_id is not None and (
            not isinstance(audience_id, str) or not audience_id.strip()
        ):
            raise ValueError("audience_id must be None or nonempty")
        if audience_id is not None and principal_id is None:
            raise ValueError("audience_id requires principal_id")
        if type(batch_size) is not int or not 1 <= batch_size <= 512:
            raise ValueError("batch_size must be 1..512")

        clauses = ["status=?"]
        scope: list[str] = [CandidateStatus.PROMOTED.value]
        if principal_id is not None:
            clauses.append("principal_id=?")
            scope.append(principal_id)
            if audience_id is None:
                clauses.append("audience_id IS NULL")
            else:
                clauses.append("(audience_id IS NULL OR audience_id=?)")
                scope.append(audience_id)

        after: tuple[str, str] | None = None
        while True:
            where = list(clauses)
            args = list(scope)
            if after is not None:
                where.append(
                    "(created_at > ? OR "
                    "(created_at = ? AND candidate_id > ?))"
                )
                args.extend((after[0], after[0], after[1]))
            args.append(batch_size)
            with self._lock:
                rows = self._require_db().execute(
                    "SELECT candidate_id,content,created_at "
                    "FROM memory_candidate WHERE " + " AND ".join(where)
                    + " ORDER BY created_at ASC,candidate_id ASC LIMIT ?",
                    tuple(args),
                ).fetchall()
            if not rows:
                return
            after = (rows[-1][2], rows[-1][0])
            for candidate_id, content, _created_at in rows:
                yield UUID(candidate_id), content
            if len(rows) < batch_size:
                return

    def list_ids(
        self,
        *,
        status: CandidateStatus | None = None,
        principal_id: str | None = None,
        audience_id: str | None = None,
    ) -> tuple[UUID, ...]:
        if status is not None and not isinstance(status, CandidateStatus):
            raise TypeError("status must be CandidateStatus or None")
        if principal_id is not None and (
            not isinstance(principal_id, str) or not principal_id.strip()
        ):
            raise ValueError("principal_id must be None or nonempty")
        if audience_id is not None and (
            not isinstance(audience_id, str) or not audience_id.strip()
        ):
            raise ValueError("audience_id must be None or nonempty")
        if audience_id is not None and principal_id is None:
            raise ValueError("audience_id requires principal_id")

        clauses: list[str] = []
        parameters: list[str] = []
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status.value)
        if principal_id is not None:
            clauses.append("principal_id = ?")
            parameters.append(principal_id)
            if audience_id is None:
                clauses.append("audience_id IS NULL")
            else:
                clauses.append("(audience_id IS NULL OR audience_id = ?)")
                parameters.append(audience_id)

        where = (
            ""
            if not clauses
            else "WHERE " + " AND ".join(clauses)
        )
        with self._lock:
            rows = self._require_db().execute(
                f"""
                SELECT candidate_id
                FROM memory_candidate
                {where}
                ORDER BY created_at ASC, candidate_id ASC
                """,
                tuple(parameters),
            ).fetchall()
        return tuple(UUID(row[0]) for row in rows)


    def status(
        self,
        candidate_id: UUID,
    ) -> CandidateStatus | None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")

        with self._lock:
            row = self._require_db().execute(
                """
                SELECT status
                FROM memory_candidate
                WHERE candidate_id = ?
                """,
                (str(candidate_id),),
            ).fetchone()

        if row is None:
            return None

        try:
            return CandidateStatus(row[0])
        except ValueError as exc:
            raise RuntimeError(
                "stored memory candidate has invalid lifecycle status"
            ) from exc

    def promote(self, candidate_id: UUID) -> None:
        """Operator-reviewed promotion, atomically superseding a corrected fact."""
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        with self._lock:
            db = self._require_db()
            with db:
                db.execute("BEGIN IMMEDIATE")
                link = db.execute(
                    "SELECT old_candidate_id FROM memory_candidate_correction "
                    "WHERE new_candidate_id=?", (str(candidate_id),),
                ).fetchone()
                if link is None:
                    current = db.execute(
                        "SELECT status FROM memory_candidate WHERE candidate_id=?",
                        (str(candidate_id),),
                    ).fetchone()
                    if current is None:
                        raise LookupError("candidate does not exist")
                    if current[0] != CandidateStatus.PROPOSED.value:
                        raise ValueError(
                            "candidate must be proposed before promoted"
                        )
                    changed = db.execute(
                        "UPDATE memory_candidate SET status=? "
                        "WHERE candidate_id=? AND status=?",
                        (CandidateStatus.PROMOTED.value, str(candidate_id),
                         CandidateStatus.PROPOSED.value),
                    )
                    if changed.rowcount != 1:
                        raise RuntimeError(
                            "reviewed memory promotion lost its proposed state"
                        )
                    return
                old_id = link[0]
                candidates = db.execute(
                    "SELECT candidate_id,status,principal_id,audience_id "
                    "FROM memory_candidate WHERE candidate_id IN (?,?)",
                    (str(candidate_id), old_id),
                ).fetchall()
                by_id = {row[0]: row for row in candidates}
                original, replacement = by_id.get(old_id), by_id.get(str(candidate_id))
                if (
                    original is None or replacement is None
                    or original[1] != CandidateStatus.PROMOTED.value
                    or replacement[1] != CandidateStatus.PROPOSED.value
                    or tuple(original[2:]) != tuple(replacement[2:])
                ):
                    raise ValueError(
                        "correction requires a promoted original and same-scope proposal"
                    )
                # SQLite serializes this exact reversible state transition;
                # neither the old nor the new fact is doubly promoted.
                old_changed = db.execute(
                    "UPDATE memory_candidate SET status=? "
                    "WHERE candidate_id=? AND status=?",
                    (CandidateStatus.REVOKED.value, old_id,
                     CandidateStatus.PROMOTED.value),
                )
                new_changed = db.execute(
                    "UPDATE memory_candidate SET status=? "
                    "WHERE candidate_id=? AND status=?",
                    (CandidateStatus.PROMOTED.value, str(candidate_id),
                     CandidateStatus.PROPOSED.value),
                )
                if old_changed.rowcount != 1 or new_changed.rowcount != 1:
                    raise RuntimeError("atomic memory correction could not settle")

    def link_correction(
        self, replacement_id: UUID, superseded_id: UUID,
    ) -> None:
        """Stage a correction for explicit reviewer approval via promote().

        Does not change either candidate's status. Original and replacement
        preserve their exact source evidence and must share one principal/audience.
        """
        if not isinstance(replacement_id, UUID) or not isinstance(superseded_id, UUID):
            raise TypeError("correction IDs must be UUID")
        if replacement_id == superseded_id:
            raise ValueError("a candidate cannot supersede itself")
        with self._lock:
            db = self._require_db()
            with db:
                db.execute("BEGIN IMMEDIATE")
                rows = db.execute(
                    "SELECT candidate_id,status,principal_id,audience_id "
                    "FROM memory_candidate WHERE candidate_id IN (?,?)",
                    (str(replacement_id), str(superseded_id)),
                ).fetchall()
                by_id = {row[0]: row for row in rows}
                replacement = by_id.get(str(replacement_id))
                original = by_id.get(str(superseded_id))
                if (
                    replacement is None or original is None
                    or replacement[1] != CandidateStatus.PROPOSED.value
                    or original[1] != CandidateStatus.PROMOTED.value
                    or tuple(replacement[2:]) != tuple(original[2:])
                ):
                    raise ValueError(
                        "correction must link a proposed and promoted same-scope fact"
                    )
                existing = db.execute(
                    "SELECT new_candidate_id,old_candidate_id "
                    "FROM memory_candidate_correction "
                    "WHERE new_candidate_id=? OR old_candidate_id=?",
                    (str(replacement_id), str(superseded_id)),
                ).fetchone()
                if existing is not None:
                    if existing != (str(replacement_id), str(superseded_id)):
                        raise ValueError("candidate is already part of another correction")
                    return
                db.execute(
                    "INSERT INTO memory_candidate_correction "
                    "(new_candidate_id,old_candidate_id,linked_at) VALUES(?,?,?)",
                    (str(replacement_id), str(superseded_id),
                     datetime.now(timezone.utc).isoformat()),
                )

    def correction_link(self, candidate_id: UUID) -> tuple[UUID, UUID] | None:
        """Return replacement/superseded lineage without changing original data."""
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be UUID")
        with self._lock:
            row = self._require_db().execute(
                "SELECT new_candidate_id,old_candidate_id "
                "FROM memory_candidate_correction WHERE new_candidate_id=? "
                "OR old_candidate_id=?",
                (str(candidate_id), str(candidate_id)),
            ).fetchone()
        return None if row is None else (UUID(row[0]), UUID(row[1]))

    def reject(self, candidate_id: UUID) -> None:
        self._transition(
            candidate_id,
            CandidateStatus.PROPOSED,
            CandidateStatus.REJECTED,
        )

    def revoke(self, candidate_id: UUID) -> None:
        self._transition(
            candidate_id,
            CandidateStatus.PROMOTED,
            CandidateStatus.REVOKED,
        )

    def _transition(
        self,
        candidate_id: UUID,
        expected: CandidateStatus,
        target: CandidateStatus,
    ) -> None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")

        with self._lock:
            db = self._require_db()
            with db:
                cursor = db.execute(
                    """
                    UPDATE memory_candidate
                    SET status = ?
                    WHERE candidate_id = ? AND status = ?
                    """,
                    (
                        target.value,
                        str(candidate_id),
                        expected.value,
                    ),
                )

            if cursor.rowcount == 1:
                return

            row = db.execute(
                """
                SELECT status
                FROM memory_candidate
                WHERE candidate_id = ?
                """,
                (str(candidate_id),),
            ).fetchone()

        if row is None:
            raise LookupError("candidate does not exist")

        raise ValueError(
            f"candidate must be {expected.value} before {target.value}"
        )

    def open(self) -> None:
        """Reopen the candidate store after an owned runtime shutdown."""
        with self._lock:
            if self._db is not None:
                return
            self._db = self._guard.connect(
                timeout=3.0,
                check_same_thread=False,
            )
            self._db.execute("PRAGMA foreign_keys = ON")
            self._db.execute("PRAGMA busy_timeout = 3000")

    def close(self) -> None:
        with self._lock:
            if self._db is None:
                return
            self._db.close()
            self._db = None

    def _require_db(self) -> sqlite3.Connection:
        if self._db is None:
            raise RuntimeError("memory candidate store is closed")
        # An already-open SQLite handle survives POSIX unlink/replace.
        # Refuse reading or updating orphaned memory after canonical loss.
        self._guard.validate()
        return self._db
