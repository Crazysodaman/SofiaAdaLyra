"""Owner-reviewed significance marks over promoted memory candidates.

Significance is a derived owner decision about an already reviewed,
promoted memory. It never creates, edits, or revives memory content;
the candidate's own lifecycle and source review remain the only paths
through which text becomes recallable. Significance rows are append-only
and CAS-guarded, and every read rechecks the host candidate's canonical
eligibility so a stale, revoked, or altered source can never inherit a
prior significance decision.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3
from uuid import UUID

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


class MarkStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class MemorySignificance:
    """One append-only significance decision for one memory candidate."""

    candidate_id: UUID
    principal_id: str
    audience_id: str | None
    significance: float
    reason: str
    decided_by: str
    revision: int
    status: MarkStatus
    decided_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        for name in ("principal_id", "decided_by"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError(f"{name} must be bounded nonempty text")
        if self.audience_id is not None and (
            not isinstance(self.audience_id, str)
            or not self.audience_id.strip()
            or len(self.audience_id) > 200
        ):
            raise ValueError("audience_id must be None or bounded text")
        if not 0 <= self.significance <= 1:
            raise ValueError("significance must be in 0..1")
        if (
            not isinstance(self.reason, str)
            or not self.reason.strip()
            or len(self.reason.strip()) > 600
        ):
            raise ValueError("reason must be bounded nonempty text")
        if self.revision < 1:
            raise ValueError("significance revision must be positive")
        if not isinstance(self.status, MarkStatus):
            raise TypeError("MarkStatus required")
        if (
            not isinstance(self.decided_at, datetime)
            or self.decided_at.tzinfo is None
            or self.decided_at.utcoffset() is None
        ):
            raise ValueError("decided_at must be timezone-aware")


class SignificantMemoryStore:
    """Canonical append-only persistence for memory significance marks."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS memory_significance_revision (
                    candidate_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT,
                    significance REAL NOT NULL,
                    reason TEXT NOT NULL,
                    decided_by TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','revoked')),
                    decided_at TEXT NOT NULL,
                    PRIMARY KEY(candidate_id,revision)
                );
                CREATE INDEX IF NOT EXISTS memory_significance_current
                    ON memory_significance_revision(principal_id,status);
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _mark(row: sqlite3.Row) -> MemorySignificance:
        return MemorySignificance(
            UUID(row["candidate_id"]), row["principal_id"], row["audience_id"],
            float(row["significance"]), row["reason"], row["decided_by"],
            int(row["revision"]), MarkStatus(row["status"]),
            datetime.fromisoformat(row["decided_at"]),
        )

    def hold(
        self, value: MemorySignificance, *, expected_revision: int | None,
    ) -> None:
        """CAS-append one significance revision for an existing candidate."""
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT principal_id,audience_id,revision
                FROM memory_significance_revision WHERE candidate_id=?
                ORDER BY revision DESC LIMIT 1""",
                (str(value.candidate_id),),
            ).fetchone()
            current = None if row is None else int(row["revision"])
            if current != expected_revision or value.revision != (
                1 if current is None else current + 1
            ):
                raise RuntimeError("memory significance changed concurrently")
            if current is not None and (
                row["principal_id"] != value.principal_id
                or row["audience_id"] != value.audience_id
            ):
                raise RuntimeError("memory significance scope cannot change")
            db.execute(
                "INSERT INTO memory_significance_revision VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    str(value.candidate_id), value.principal_id,
                    value.audience_id, value.significance, value.reason,
                    value.decided_by, value.revision, value.status.value,
                    value.decided_at.astimezone(timezone.utc).isoformat(),
                ),
            )

    def current(self, candidate_id: UUID) -> MemorySignificance | None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        with closing(self._open()) as db:
            row = db.execute(
                """SELECT * FROM memory_significance_revision
                WHERE candidate_id=? ORDER BY revision DESC LIMIT 1""",
                (str(candidate_id),),
            ).fetchone()
        return None if row is None else self._mark(row)

    def history(self, candidate_id: UUID) -> tuple[MemorySignificance, ...]:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT * FROM memory_significance_revision
                WHERE candidate_id=? ORDER BY revision ASC""",
                (str(candidate_id),),
            ).fetchall()
        return tuple(self._mark(row) for row in rows)

    def active_marks(
        self, *, principal_id: str, audience_id: str | None = None,
    ) -> tuple[MemorySignificance, ...]:
        """Latest ACTIVE revision per candidate inside one scope."""
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id must be bounded nonempty text")
        if audience_id is not None and not isinstance(audience_id, str):
            raise ValueError("audience_id must be None or a string")
        with closing(self._open()) as db:
            if audience_id is None:
                rows = db.execute(
                    """SELECT m.* FROM memory_significance_revision m
                    JOIN (SELECT candidate_id,MAX(revision) revision
                          FROM memory_significance_revision
                          WHERE principal_id=? GROUP BY candidate_id) latest
                    ON m.candidate_id=latest.candidate_id
                    AND m.revision=latest.revision
                    WHERE m.principal_id=? AND m.status='active'""",
                    (principal_id, principal_id),
                ).fetchall()
            else:
                rows = db.execute(
                    """SELECT m.* FROM memory_significance_revision m
                    JOIN (SELECT candidate_id,MAX(revision) revision
                          FROM memory_significance_revision
                          WHERE principal_id=? GROUP BY candidate_id) latest
                    ON m.candidate_id=latest.candidate_id
                    AND m.revision=latest.revision
                    WHERE m.principal_id=?
                    AND (m.audience_id IS NULL OR m.audience_id=?)
                    AND m.status='active'""",
                    (principal_id, principal_id, audience_id),
                ).fetchall()
        return tuple(self._mark(row) for row in rows)
