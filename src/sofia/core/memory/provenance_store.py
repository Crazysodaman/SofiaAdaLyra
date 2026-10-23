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

from sofia.core.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.core.memory.originals import SourceMessage
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


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

        # The operator-held deletion ledger is deliberately stored outside
        # sofia.db backups. On a configured production restart, reconcile
        # any durable erasure whose live SQL transaction was interrupted
        # BEFORE opening the candidate store or projecting recalled text.
        from os import environ
        journal_path = environ.get("SOFIA_MEMORY_ERASURE_JOURNAL", "").strip()
        key_path = environ.get("SOFIA_MEMORY_ERASURE_KEY", "").strip()
        if bool(journal_path) != bool(key_path):
            raise RuntimeError(
                "memory erasure requires both external journal and operator key"
            )
        if journal_path:
            if not target.is_file():
                raise FileNotFoundError(
                    "erasure-enabled runtime requires existing canonical state"
                )
            from sofia.core.memory.deletion_ledger import MemoryDeletionLedger
            from sofia.platform.ops.backup import BackupCipher, load_backup_key
            MemoryDeletionLedger(
                Path(journal_path).absolute(),
                BackupCipher(load_backup_key(Path(key_path))),
            ).apply_to_sqlite(target)

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
            # A verified reviewed-memory source is an immutable link to
            # current canonical originals, not a copied claim that can outlive
            # original erasure or a changed conversation audience.
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_candidate_source_review (
                    candidate_id TEXT PRIMARY KEY,
                    source_session_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    audience_kind TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES memory_candidate(candidate_id)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_candidate_validity (
                    candidate_id TEXT PRIMARY KEY,
                    expires_at TEXT,
                    reviewed_at TEXT NOT NULL,
                    reviewed_by TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES memory_candidate(candidate_id)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_candidate_validity_event (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id TEXT NOT NULL,
                    previous_expires_at TEXT,
                    expires_at TEXT,
                    reviewed_at TEXT NOT NULL,
                    reviewed_by TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES memory_candidate(candidate_id)
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

    def set_expiration(
        self, candidate_id: UUID, *, expires_at: datetime | None,
        reviewed_by: str, reason: str,
    ) -> None:
        """Reviewed time validity, not inferred decay or irreversible erasure.

        A null expiration revokes a prior expiry decision, while retaining
        append-only evidence of the earlier review. Promotion status and
        original source provenance never change.
        """
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be UUID")
        if expires_at is not None:
            deadline = _utc(expires_at)
        else:
            deadline = None
        if not isinstance(reviewed_by, str) or not reviewed_by.strip():
            raise ValueError("reviewed_by must identify the owner")
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 500:
            raise ValueError("a bounded reviewer reason is required")
        stamp = _utc(datetime.now(timezone.utc))
        with self._lock:
            db = self._require_db()
            with db:
                db.execute("BEGIN IMMEDIATE")
                candidate = db.execute(
                    "SELECT status,principal_id FROM memory_candidate "
                    "WHERE candidate_id=?", (str(candidate_id),),
                ).fetchone()
                if candidate is None:
                    raise LookupError("candidate does not exist")
                if candidate[0] != CandidateStatus.PROMOTED.value:
                    raise ValueError("expiration requires promoted memory")
                if candidate[1] is None or candidate[1] != reviewed_by:
                    raise PermissionError("expiration must be reviewed by the owner")
                previous = db.execute(
                    "SELECT expires_at FROM memory_candidate_validity "
                    "WHERE candidate_id=?", (str(candidate_id),),
                ).fetchone()
                db.execute(
                    "INSERT INTO memory_candidate_validity "
                    "(candidate_id,expires_at,reviewed_at,reviewed_by,reason) "
                    "VALUES(?,?,?,?,?) "
                    "ON CONFLICT(candidate_id) DO UPDATE SET "
                    "expires_at=excluded.expires_at,"
                    "reviewed_at=excluded.reviewed_at,"
                    "reviewed_by=excluded.reviewed_by,reason=excluded.reason",
                    (str(candidate_id), deadline, stamp, reviewed_by, reason.strip()),
                )
                db.execute(
                    "INSERT INTO memory_candidate_validity_event "
                    "(candidate_id,previous_expires_at,expires_at,"
                    "reviewed_at,reviewed_by,reason) VALUES(?,?,?,?,?,?)",
                    (str(candidate_id), None if previous is None else previous[0],
                     deadline, stamp, reviewed_by, reason.strip()),
                )

    def expiration(self, candidate_id: UUID) -> datetime | None:
        """Read approved validity without hiding historical review evidence."""
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be UUID")
        with self._lock:
            row = self._require_db().execute(
                "SELECT expires_at FROM memory_candidate_validity "
                "WHERE candidate_id=?", (str(candidate_id),),
            ).fetchone()
        return None if row is None or row[0] is None else datetime.fromisoformat(row[0])

    def require_current_original_at_recall(
        self, candidate_id: UUID, *, session_id: str,
        principal_id: str, audience_id: str, audience_kind: str,
    ) -> None:
        """Record extra fail-closed eligibility for *reviewed* real originals.

        This adds a guard; it never creates approval, grants any audience, or
        changes a candidate's reviewed/immutable source bytes. It is called
        only after the application independently re-reads original evidence.
        """
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be UUID")
        for value in (session_id, principal_id, audience_id, audience_kind):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("complete verified source binding is required")
        with self._lock:
            db = self._require_db()
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT status,principal_id,audience_id "
                    "FROM memory_candidate WHERE candidate_id=?",
                    (str(candidate_id),),
                ).fetchone()
                if row is None:
                    raise LookupError("candidate does not exist")
                if row[0] != CandidateStatus.PROPOSED.value:
                    raise ValueError("only proposed candidates can gain source recall guard")
                if row[1] != principal_id or row[2] not in (None, audience_id):
                    raise PermissionError("source review belongs to another audience")
                source = db.execute(
                    "SELECT COUNT(*),MIN(session_id),MAX(session_id) "
                    "FROM memory_candidate_source WHERE candidate_id=?",
                    (str(candidate_id),),
                ).fetchone()
                if (
                    source is None or not 1 <= int(source[0]) <= 64
                    or source[1] != session_id or source[2] != session_id
                ):
                    raise ValueError("bounded single-session original review required")
                prior = db.execute(
                    "SELECT source_session_id,principal_id,audience_id,audience_kind "
                    "FROM memory_candidate_source_review WHERE candidate_id=?",
                    (str(candidate_id),),
                ).fetchone()
                expected = (session_id, principal_id, audience_id, audience_kind)
                if prior is not None:
                    if tuple(prior) != expected:
                        raise PermissionError("original source review binding cannot change")
                    return
                db.execute(
                    "INSERT INTO memory_candidate_source_review VALUES(?,?,?,?,?,?)",
                    (
                        str(candidate_id), session_id, principal_id,
                        audience_id, audience_kind,
                        _utc(datetime.now(timezone.utc)),
                    ),
                )

    def is_recall_eligible(
        self, candidate_id: UUID, *, at: datetime | None = None,
    ) -> bool:
        """Late revocation and approved deadline check against canonical state."""
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be UUID")
        stamp = _utc(at or datetime.now(timezone.utc))
        with self._lock:
            db = self._require_db()
            row = db.execute(
                "SELECT 1 FROM memory_candidate c "
                "LEFT JOIN memory_candidate_validity v "
                "ON v.candidate_id=c.candidate_id "
                "WHERE c.candidate_id=? AND c.status=? "
                "AND (v.expires_at IS NULL OR v.expires_at>?)",
                (str(candidate_id), CandidateStatus.PROMOTED.value, stamp),
            ).fetchone()
            if row is None:
                return False
            reviewed = db.execute(
                "SELECT source_session_id,principal_id,audience_id,audience_kind "
                "FROM memory_candidate_source_review WHERE candidate_id=?",
                (str(candidate_id),),
            ).fetchone()
            if reviewed is None:
                # Historic low-level imported candidates predate source review
                # attestations. Do not silently rewrite or erase those rows.
                return True
            originals = db.execute(
                "SELECT src.session_id,src.role,src.content,src.created_at,"
                "m.id,m.role,m.content,m.created_at,"
                "s.principal_id,s.audience_id,s.audience_kind "
                "FROM memory_candidate_source AS src "
                "LEFT JOIN conversation_messages AS m "
                "ON m.id=src.message_id AND m.session_id=src.session_id "
                "LEFT JOIN social_session_principal AS s "
                "ON s.session_id=m.session_id "
                "WHERE src.candidate_id=? ORDER BY src.ordinal",
                (str(candidate_id),),
            ).fetchall()
            if not originals or len(originals) > 64:
                return False
            for source in originals:
                if (
                    source[0] != reviewed[0]
                    or source[4] is None
                    or source[1] != source[5]
                    or source[2] != source[6]
                    or source[8] != reviewed[1]
                    or source[9] != reviewed[2]
                    or source[10] != reviewed[3]
                ):
                    return False
                try:
                    before = datetime.fromisoformat(source[3])
                    current = datetime.fromisoformat(source[7])
                except (TypeError, ValueError):
                    return False
                if (
                    before.tzinfo is None or before.utcoffset() is None
                    or current.tzinfo is None or current.utcoffset() is None
                ):
                    return False
                if before.astimezone(timezone.utc) != current.astimezone(timezone.utc):
                    return False
            return True

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

        with self._lock:
            existing_tables = {
                row[0] for row in self._require_db().execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name IN "
                    "('conversation_messages','social_session_principal')"
                ).fetchall()
            }
        if existing_tables == {"conversation_messages", "social_session_principal"}:
            # An originally reviewed fact whose source was deleted, edited
            # or rebound must not take a relevance slot away from other
            # current facts. This is one indexed correlated SQL eligibility
            # check per keyset batch, NOT one SQLite fetch per candidate.
            source_guard = (
                "NOT EXISTS ("
                "SELECT 1 FROM memory_candidate_source_review AS r "
                "WHERE r.candidate_id=memory_candidate.candidate_id "
                "AND (NOT EXISTS ("
                "SELECT 1 FROM memory_candidate_source AS src "
                "WHERE src.candidate_id=r.candidate_id"
                ") OR EXISTS ("
                "SELECT 1 FROM memory_candidate_source AS src "
                "LEFT JOIN conversation_messages AS m "
                "ON m.id=src.message_id AND m.session_id=src.session_id "
                "LEFT JOIN social_session_principal AS s "
                "ON s.session_id=m.session_id "
                "WHERE src.candidate_id=r.candidate_id AND ("
                "src.session_id!=r.source_session_id OR m.id IS NULL "
                "OR m.role!=src.role OR m.content!=src.content "
                "OR julianday(src.created_at) IS NULL "
                "OR julianday(m.created_at) IS NULL "
                "OR julianday(src.created_at)!=julianday(m.created_at) "
                "OR s.principal_id IS NULL OR s.principal_id!=r.principal_id "
                "OR s.audience_id!=r.audience_id "
                "OR s.audience_kind!=r.audience_kind"
                ")"
                ")))"
            )
        else:
            # Unmarked historic fixtures remain readable. An attested
            # candidate must never pass when its source tables disappear.
            source_guard = (
                "NOT EXISTS (SELECT 1 FROM memory_candidate_source_review AS r "
                "WHERE r.candidate_id=memory_candidate.candidate_id)"
            )

        clauses = [
            "status=?",
            source_guard,
            "NOT EXISTS (SELECT 1 FROM memory_candidate_validity AS v "
            "WHERE v.candidate_id=memory_candidate.candidate_id "
            "AND v.expires_at IS NOT NULL AND v.expires_at<=?)",
        ]
        scope: list[str] = [
            CandidateStatus.PROMOTED.value, _utc(datetime.now(timezone.utc)),
        ]
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

    @staticmethod
    def _verify_reviewed_originals_in_writer(
        db: sqlite3.Connection, candidate_id: UUID,
    ) -> None:
        """Final current-source proof inside the SAME promotion transaction.

        A source review attestation proves an earlier observation, not that
        its original survived unchanged until publication. Historic low-level
        unattested imports retain their existing separate compatibility
        policy; this guard never promotes or authenticates them.
        """
        key = str(candidate_id)
        reviewed = db.execute(
            "SELECT r.source_session_id,r.principal_id,r.audience_id,"
            "r.audience_kind,c.principal_id,c.audience_id "
            "FROM memory_candidate_source_review AS r "
            "JOIN memory_candidate AS c ON c.candidate_id=r.candidate_id "
            "WHERE r.candidate_id=?", (key,),
        ).fetchone()
        if reviewed is None:
            return
        if reviewed[1] != reviewed[4] or reviewed[5] not in (None, reviewed[2]):
            raise PermissionError("reviewed memory owner or audience changed")
        rows = db.execute(
            "SELECT src.session_id,src.role,src.content,src.created_at,"
            "m.id,m.role,m.content,m.created_at,"
            "s.principal_id,s.audience_id,s.audience_kind "
            "FROM memory_candidate_source AS src "
            "LEFT JOIN conversation_messages AS m "
            "ON m.id=src.message_id AND m.session_id=src.session_id "
            "LEFT JOIN social_session_principal AS s ON s.session_id=m.session_id "
            "WHERE src.candidate_id=? ORDER BY src.ordinal",
            (key,),
        ).fetchall()
        if not 1 <= len(rows) <= 64:
            raise PermissionError("reviewed memory exact originals unavailable")
        for source in rows:
            if (
                source[0] != reviewed[0]
                or source[4] is None
                or source[1] != source[5]
                or source[2] != source[6]
                or source[8] != reviewed[1]
                or source[9] != reviewed[2]
                or source[10] != reviewed[3]
            ):
                raise PermissionError(
                    "reviewed memory original bytes or audience changed before promotion"
                )
            try:
                earlier = datetime.fromisoformat(source[3])
                current = datetime.fromisoformat(source[7])
            except (TypeError, ValueError) as exc:
                raise PermissionError(
                    "reviewed memory original timestamp is unavailable"
                ) from exc
            if (
                earlier.tzinfo is None or earlier.utcoffset() is None
                or current.tzinfo is None or current.utcoffset() is None
                or earlier.astimezone(timezone.utc)
                != current.astimezone(timezone.utc)
            ):
                raise PermissionError(
                    "reviewed memory original time changed before promotion"
                )

    def promote(self, candidate_id: UUID) -> None:
        """Operator-reviewed promotion, atomically superseding a corrected fact."""
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        with self._lock:
            db = self._require_db()
            with db:
                db.execute("BEGIN IMMEDIATE")
                self._verify_reviewed_originals_in_writer(db, candidate_id)
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
