"""Durable personal impressions and subject-scoped relationship stances.

Impressions are Sofía's own evidence-linked social state toward one principal
about one bounded subject. A disagreement about one subject is a subject-
scoped row and must never silently poison unrelated interaction; every
revision keeps its evidence and reconciliation is an explicit evidence-
carrying change, not an automatic forgiving timer.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.social.principals import (
    PrincipalContext,
    SPARKS_PRINCIPAL_ID,
)


_SUBJECT = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,119}$")
_EVIDENCE = re.compile(r"^[a-z0-9][a-z0-9_.:@/-]{0,159}$")


class ImpressionKind(str, Enum):
    TRUST = "trust"
    RESPECT = "respect"
    AFFECTION = "affection"
    SKEPTICISM = "skepticism"
    DISAPPOINTMENT = "disappointment"
    FRUSTRATION = "frustration"
    GUARDEDNESS = "guardedness"
    APPRECIATION = "appreciation"


class ImpressionChangeKind(str, Enum):
    ORIGIN = "origin"
    RECONCILE = "reconcile"
    WITHDRAW = "withdraw"


class ImpressionStatus(str, Enum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class ImpressionError(RuntimeError):
    """Race or identity mismatch in an impression revision."""


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("impression timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ImpressionRecord:
    """One append-only impression revision inside one subject scope."""

    impression_id: str
    revision: int
    principal_id: str
    subject: str
    kind: ImpressionKind
    level: float
    reason: str
    evidence_refs: tuple[str, ...]
    audience_id: str
    change_kind: ImpressionChangeKind
    status: ImpressionStatus
    recorded_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.impression_id, str)
            or not self.impression_id.startswith("impression:")
            or len(self.impression_id) > 120
        ):
            raise ValueError("impression_id must be a canonical impression id")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("impression revision must be a positive integer")
        if (
            not isinstance(self.principal_id, str)
            or not self.principal_id.strip()
            or len(self.principal_id) > 160
        ):
            raise ValueError("principal_id must be bounded nonempty text")
        if isinstance(self.subject, str) and _SUBJECT.fullmatch(self.subject):
            pass
        else:
            raise ValueError("subject must be a canonical bounded identifier")
        if not isinstance(self.kind, ImpressionKind):
            raise TypeError("kind must be ImpressionKind")
        if not 0.0 <= self.level <= 1.0:
            raise ValueError("impression level must be in 0..1")
        if (
            not isinstance(self.reason, str)
            or not self.reason.strip()
            or len(self.reason.strip()) > 600
        ):
            raise ValueError("impression reason must be bounded nonempty text")
        if type(self.evidence_refs) is not tuple:
            raise TypeError("evidence_refs must be a tuple")
        if (
            not self.evidence_refs
            or len(self.evidence_refs) > 8
            or len(set(self.evidence_refs)) != len(self.evidence_refs)
            or any(
                not isinstance(value, str) or _EVIDENCE.fullmatch(value) is None
                for value in self.evidence_refs
            )
        ):
            raise ValueError(
                "impression evidence must be 1..8 distinct bounded refs"
            )
        if (
            not isinstance(self.audience_id, str)
            or not self.audience_id.strip()
            or len(self.audience_id) > 160
        ):
            raise ValueError("audience_id must be bounded nonempty text")
        if not isinstance(self.change_kind, ImpressionChangeKind):
            raise TypeError("change_kind must be ImpressionChangeKind")
        if not isinstance(self.status, ImpressionStatus):
            raise TypeError("status must be ImpressionStatus")
        if self.status is ImpressionStatus.WITHDRAWN and (
            self.change_kind is not ImpressionChangeKind.WITHDRAW
        ):
            raise ValueError("withdrawn impressions must record a withdraw")
        if _utc(self.recorded_at) != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")


@dataclass(frozen=True, slots=True)
class ImpressionEntry:
    """A scoped current impression read for conversation context."""

    impression: ImpressionRecord

    @property
    def kind(self) -> ImpressionKind:
        return self.impression.kind

    @property
    def subject(self) -> str:
        return self.impression.subject


class ImpressionStore:
    """Canonical append-only persistence for personal impressions."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS rel_impression_revision (
                    impression_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    principal_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN (
                        'trust','respect','affection','skepticism',
                        'disappointment','frustration','guardedness',
                        'appreciation')),
                    level REAL NOT NULL CHECK(level>=0 AND level<=1),
                    reason TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    change_kind TEXT NOT NULL CHECK(change_kind IN (
                        'origin','reconcile','withdraw')),
                    status TEXT NOT NULL CHECK(status IN ('active','withdrawn')),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(impression_id,revision)
                );
                CREATE INDEX IF NOT EXISTS rel_impression_scope
                    ON rel_impression_revision(principal_id,audience_id,subject);
                CREATE TABLE IF NOT EXISTS rel_impression_current (
                    impression_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    UNIQUE(principal_id,subject,kind,audience_id,impression_id)
                );
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode(record: ImpressionRecord) -> tuple:
        return (
            record.impression_id, record.revision, record.principal_id,
            record.subject, record.kind.value, record.level, record.reason,
            json.dumps(list(record.evidence_refs)), record.audience_id,
            record.change_kind.value, record.status.value,
            record.recorded_at.isoformat(),
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> ImpressionRecord:
        return ImpressionRecord(
            impression_id=row["impression_id"],
            revision=int(row["revision"]),
            principal_id=row["principal_id"],
            subject=row["subject"],
            kind=ImpressionKind(row["kind"]),
            level=float(row["level"]),
            reason=row["reason"],
            evidence_refs=tuple(json.loads(row["evidence_refs"])),
            audience_id=row["audience_id"],
            change_kind=ImpressionChangeKind(row["change_kind"]),
            status=ImpressionStatus(row["status"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    def hold(self, value: ImpressionRecord, *, expected_revision: int | None) -> ImpressionRecord:
        """CAS-append one impression revision under one subject scope."""
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT impression_id,revision,principal_id,subject,kind,
                audience_id FROM rel_impression_current
                WHERE principal_id=? AND subject=? AND kind=? AND audience_id=?""",
                (value.principal_id, value.subject, value.kind.value,
                 value.audience_id),
            ).fetchone()
            if expected_revision is None:
                if row is not None:
                    raise ImpressionError(
                        "impression already exists; reload and revise with "
                        f"expected_revision={int(row['revision'])}"
                    )
                if value.revision != 1 or value.change_kind is not (
                    ImpressionChangeKind.ORIGIN
                ):
                    raise ImpressionError(
                        "creating an impression requires origin revision 1"
                    )
            else:
                if row is None or int(row["revision"]) != expected_revision:
                    raise ImpressionError(
                        "revision changed or impression is absent; "
                        "reload before revising"
                    )
                if row["impression_id"] != value.impression_id:
                    raise ImpressionError(
                        "impression identity changed; reload before revising"
                    )
            db.execute(
                """INSERT INTO rel_impression_revision VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                self._encode(value),
            )
            if row is None:
                db.execute(
                    """INSERT INTO rel_impression_current
                    (impression_id,principal_id,subject,kind,audience_id,revision)
                    VALUES(?,?,?,?,?,?)""",
                    (value.impression_id, value.principal_id, value.subject,
                     value.kind.value, value.audience_id, value.revision),
                )
            else:
                db.execute(
                    """UPDATE rel_impression_current
                    SET revision=? WHERE impression_id=?""",
                    (value.revision, value.impression_id),
                )
        return value

    def current(
        self, *, principal_id: str, subject: str, kind: ImpressionKind,
        audience_id: str,
    ) -> ImpressionRecord | None:
        with closing(self._open()) as db:
            row = db.execute(
                """SELECT r.* FROM rel_impression_current c
                JOIN rel_impression_revision r
                ON r.impression_id=c.impression_id
                AND r.revision=c.revision
                WHERE c.principal_id=? AND c.subject=? AND c.kind=?
                AND c.audience_id=?""",
                (principal_id, subject, kind.value, audience_id),
            ).fetchone()
        return None if row is None else self._decode(row)

    def history(
        self, impression_id: str, *,
        principal_id: str | None = None, audience_id: str | None = None,
    ) -> tuple[ImpressionRecord, ...]:
        query = (
            """SELECT * FROM rel_impression_revision
            WHERE impression_id=? ORDER BY revision ASC"""
        )
        params: list = [impression_id]
        if principal_id is not None:
            query = (
                """SELECT r.* FROM rel_impression_revision r
                JOIN rel_impression_current c ON c.impression_id=r.impression_id
                WHERE r.impression_id=? AND c.principal_id=?
                AND c.audience_id=? ORDER BY r.revision ASC"""
            )
            params = [impression_id, principal_id, audience_id]
        with closing(self._open()) as db:
            rows = db.execute(query, params).fetchall()
        return tuple(self._decode(row) for row in rows)

    def active_impressions(
        self, *, principal_id: str, audience_id: str, limit: int = 32,
    ) -> tuple[ImpressionRecord, ...]:
        """Active impressions for one principal/audience scope."""
        if not isinstance(limit, int) or not 1 <= limit <= 128:
            raise ValueError("limit must be an int in 1..128")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT r.* FROM rel_impression_current c
                JOIN rel_impression_revision r
                ON r.impression_id=c.impression_id
                AND r.revision=c.revision
                WHERE c.principal_id=? AND c.audience_id=?
                AND r.status='active'
                ORDER BY r.recorded_at DESC, r.impression_id LIMIT ?""",
                (principal_id, audience_id, limit),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def new_impression_id(self) -> str:
        return f"impression:{uuid4()}"


class ImpressionService:
    """The only production writer for Sofía's personal impressions.

    Writes are owner-session-gated: only the authenticated Sparks principal
    may record, reconcile, or withdraw impressions. Reads that are bounded
    and audience-scoped may happen through production read paths.
    """

    def __init__(self, store: ImpressionStore) -> None:
        self._store = store

    @property
    def store(self) -> ImpressionStore:
        return self._store

    @staticmethod
    def _require_sparks(principal: PrincipalContext) -> None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "impression writes require the authenticated Sparks principal"
            )

    def observe(
        self, principal: PrincipalContext, *, about: str, subject: str,
        kind: ImpressionKind, level: float, reason: str,
        evidence_refs: tuple[str, ...], audience_id: str,
        recorded_at: datetime | None = None,
    ) -> ImpressionRecord:
        """Record a first impression inside one subject scope."""
        self._require_sparks(principal)
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = ImpressionRecord(
            impression_id=self._store.new_impression_id(),
            revision=1,
            principal_id=about,
            subject=subject,
            kind=kind,
            level=level,
            reason=reason,
            evidence_refs=tuple(evidence_refs),
            audience_id=audience_id,
            change_kind=ImpressionChangeKind.ORIGIN,
            status=ImpressionStatus.ACTIVE,
            recorded_at=stamp,
        )
        return self._store.hold(record, expected_revision=None)

    def reconcile(
        self, principal: PrincipalContext, *, impression_id: str,
        expected_revision: int, level: float, reason: str,
        evidence_refs: tuple[str, ...],
        recorded_at: datetime | None = None,
    ) -> ImpressionRecord:
        """Explicitly reconcile an impression through new experience."""
        self._require_sparks(principal)
        history = self._store.history(impression_id)
        if not history:
            raise LookupError("unknown impression id")
        latest = history[-1]
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = ImpressionRecord(
            impression_id=latest.impression_id,
            revision=expected_revision + 1,
            principal_id=latest.principal_id,
            subject=latest.subject,
            kind=latest.kind,
            level=level,
            reason=reason,
            evidence_refs=tuple(evidence_refs),
            audience_id=latest.audience_id,
            change_kind=ImpressionChangeKind.RECONCILE,
            status=ImpressionStatus.ACTIVE,
            recorded_at=stamp,
        )
        return self._store.hold(record, expected_revision=expected_revision)

    def withdraw(
        self, principal: PrincipalContext, *, impression_id: str,
        expected_revision: int, reason: str,
        evidence_refs: tuple[str, ...],
        recorded_at: datetime | None = None,
    ) -> ImpressionRecord:
        """Voluntarily retire an impression without overwriting history."""
        self._require_sparks(principal)
        history = self._store.history(impression_id)
        if not history:
            raise LookupError("unknown impression id")
        latest = history[-1]
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = ImpressionRecord(
            impression_id=latest.impression_id,
            revision=expected_revision + 1,
            principal_id=latest.principal_id,
            subject=latest.subject,
            kind=latest.kind,
            level=0.0,
            reason=reason,
            evidence_refs=tuple(evidence_refs),
            audience_id=latest.audience_id,
            change_kind=ImpressionChangeKind.WITHDRAW,
            status=ImpressionStatus.WITHDRAWN,
            recorded_at=stamp,
        )
        return self._store.hold(record, expected_revision=expected_revision)

    def active(
        self, principal: PrincipalContext, *, about: str, audience_id: str,
        limit: int = 32,
    ) -> tuple[ImpressionRecord, ...]:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        return self._store.active_impressions(
            principal_id=about, audience_id=audience_id, limit=limit
        )

    def working_context(
        self, principal: PrincipalContext, *, about: str, audience_id: str,
    ) -> str | None:
        """Bounded read-only projection for conversation context."""
        records = self._store.active_impressions(
            principal_id=about, audience_id=audience_id, limit=16
        )
        if not records:
            return None
        lines = [
            "SUBJECT-SCOPED IMPRESSIONS (Sofía's recorded stance evidence for "
            "this person; one subject, one audience; re-read on new evidence, "
            "never generalized beyond the subject):",
        ]
        for record in records:
            evidence = ", ".join(record.evidence_refs[:4])
            lines.append(
                f"- {record.kind.value} {record.level:.2f} about "
                f"{record.subject}: {record.reason} (evidence: {evidence})"
            )
        text = "\n".join(lines)
        return text if len(text) <= 2000 else text[:1999]
