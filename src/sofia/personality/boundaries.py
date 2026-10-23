"""Sofía's own personal boundaries about what she discusses or volunteers.

A boundary is a first-person, evidence-linked record about what Sofía does
not want to make public right now, or what changed over time. Boundaries
govern Sofía's own disclosure behavior only. They never claim the owner
cannot access host records, never override the owner's admin authority,
and they are never framed as safety policy or host authorization.
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

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.social.principals import (
    PrincipalContext,
    SPARKS_PRINCIPAL_ID,
)


_TOPIC = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,119}$")
_EVIDENCE = re.compile(r"^[a-z0-9][a-z0-9_.:@/-]{0,159}$")


class BoundaryChangeKind(str, Enum):
    SET = "set"
    ADJUST = "adjust"
    OPEN = "open"


class BoundaryStatus(str, Enum):
    ACTIVE = "active"
    OPENED = "opened"


class BoundaryError(RuntimeError):
    """Race or stale revision in a boundary record write."""


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("boundary timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class BoundaryRecord:
    """One append-only revision of one personal boundary."""

    boundary_id: str
    revision: int
    topic: str
    statement: str
    evidence_refs: tuple[str, ...]
    audience_id: str
    change_kind: BoundaryChangeKind
    status: BoundaryStatus
    recorded_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.boundary_id, str)
            or not self.boundary_id.startswith("boundary:")
            or len(self.boundary_id) > 120
        ):
            raise ValueError("boundary_id must be a canonical boundary id")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("boundary revision must be a positive integer")
        if isinstance(self.topic, str) and _TOPIC.fullmatch(self.topic):
            pass
        else:
            raise ValueError("topic must be a canonical bounded identifier")
        if (
            not isinstance(self.statement, str)
            or not self.statement.strip()
            or len(self.statement.strip()) > 600
        ):
            raise ValueError("boundary statement must be bounded nonempty text")
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
            raise ValueError("boundary evidence must be 1..8 distinct bounded refs")
        if (
            not isinstance(self.audience_id, str)
            or not self.audience_id.strip()
            or len(self.audience_id) > 160
        ):
            raise ValueError("audience_id must be bounded nonempty text")
        if not isinstance(self.change_kind, BoundaryChangeKind):
            raise TypeError("change_kind must be BoundaryChangeKind")
        if not isinstance(self.status, BoundaryStatus):
            raise TypeError("status must be BoundaryStatus")
        if self.status is BoundaryStatus.OPENED and (
            self.change_kind is not BoundaryChangeKind.OPEN
        ):
            raise ValueError("opened boundaries must record an open change")
        if (
            self.status is BoundaryStatus.ACTIVE
            and self.change_kind is BoundaryChangeKind.OPEN
        ):
            raise ValueError("active boundaries cannot come from an open change")
        if _utc(self.recorded_at) != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")


class BoundaryStore:
    """Canonical append-only persistence for personal boundaries."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS personality_boundary_revision (
                    boundary_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    change_kind TEXT NOT NULL CHECK(change_kind IN (
                        'set','adjust','open')),
                    status TEXT NOT NULL CHECK(status IN ('active','opened')),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(boundary_id,revision)
                );
                CREATE INDEX IF NOT EXISTS personality_boundary_scope
                    ON personality_boundary_revision(audience_id,topic);
                CREATE TABLE IF NOT EXISTS personality_boundary_current (
                    boundary_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    UNIQUE(topic,audience_id,boundary_id)
                );
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode(record: BoundaryRecord) -> tuple:
        return (
            record.boundary_id, record.revision, record.topic,
            record.statement, json.dumps(list(record.evidence_refs)),
            record.audience_id, record.change_kind.value,
            record.status.value, record.recorded_at.isoformat(),
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> BoundaryRecord:
        return BoundaryRecord(
            boundary_id=row["boundary_id"],
            revision=int(row["revision"]),
            topic=row["topic"],
            statement=row["statement"],
            evidence_refs=tuple(json.loads(row["evidence_refs"])),
            audience_id=row["audience_id"],
            change_kind=BoundaryChangeKind(row["change_kind"]),
            status=BoundaryStatus(row["status"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    def hold(
        self, value: BoundaryRecord, *, expected_revision: int | None,
    ) -> BoundaryRecord:
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT boundary_id,revision FROM personality_boundary_current
                WHERE topic=? AND audience_id=?""",
                (value.topic, value.audience_id),
            ).fetchone()
            if expected_revision is None:
                if row is not None:
                    raise BoundaryError(
                        "boundary already exists; reload and revise with "
                        f"expected_revision={int(row['revision'])}"
                    )
                if value.revision != 1 or value.change_kind is not (
                    BoundaryChangeKind.SET
                ):
                    raise BoundaryError(
                        "creating a boundary requires set revision 1"
                    )
            else:
                if row is None or int(row["revision"]) != expected_revision:
                    raise BoundaryError(
                        "revision changed or boundary is absent; "
                        "reload before revising"
                    )
                if row["boundary_id"] != value.boundary_id:
                    raise BoundaryError(
                        "boundary identity changed; reload before revising"
                    )
            db.execute(
                """INSERT INTO personality_boundary_revision
                VALUES(?,?,?,?,?,?,?,?,?)""",
                self._encode(value),
            )
            if row is None:
                db.execute(
                    """INSERT INTO personality_boundary_current
                    (boundary_id,topic,audience_id,revision)
                    VALUES(?,?,?,?)""",
                    (value.boundary_id, value.topic, value.audience_id,
                     value.revision),
                )
            else:
                db.execute(
                    """UPDATE personality_boundary_current SET revision=?
                    WHERE boundary_id=?""",
                    (value.revision, value.boundary_id),
                )
        return value

    def current(
        self, *, topic: str, audience_id: str,
    ) -> BoundaryRecord | None:
        with closing(self._open()) as db:
            row = db.execute(
                """SELECT r.* FROM personality_boundary_current c
                JOIN personality_boundary_revision r
                ON r.boundary_id=c.boundary_id AND r.revision=c.revision
                WHERE c.topic=? AND c.audience_id=?""",
                (topic, audience_id),
            ).fetchone()
        return None if row is None else self._decode(row)

    def history(self, boundary_id: str, *, audience_id: str | None = None) -> tuple[BoundaryRecord, ...]:
        if audience_id is None:
            with closing(self._open()) as db:
                rows = db.execute(
                    """SELECT * FROM personality_boundary_revision
                    WHERE boundary_id=? ORDER BY revision ASC""",
                    (boundary_id,),
                ).fetchall()
        else:
            with closing(self._open()) as db:
                rows = db.execute(
                    """SELECT r.* FROM personality_boundary_revision r
                    JOIN personality_boundary_current c
                    ON c.boundary_id=r.boundary_id
                    WHERE r.boundary_id=? AND c.audience_id=?
                    ORDER BY r.revision ASC""",
                    (boundary_id, audience_id),
                ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def active(
        self, *, audience_id: str, limit: int = 32,
    ) -> tuple[BoundaryRecord, ...]:
        if not isinstance(limit, int) or not 1 <= limit <= 128:
            raise ValueError("limit must be an int in 1..128")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT r.* FROM personality_boundary_current c
                JOIN personality_boundary_revision r
                ON r.boundary_id=c.boundary_id AND r.revision=c.revision
                WHERE c.audience_id=? AND r.status='active'
                ORDER BY r.recorded_at DESC, r.boundary_id LIMIT ?""",
                (audience_id, limit),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def new_boundary_id(self) -> str:
        return f"boundary:{uuid4()}"


class BoundaryService:
    """Owner-session-gated writer for Sofía's personal boundaries."""

    def __init__(self, store: BoundaryStore) -> None:
        self._store = store

    @property
    def store(self) -> BoundaryStore:
        return self._store

    @staticmethod
    def _require_sparks(principal: PrincipalContext) -> None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "boundary writes require the authenticated Sparks principal"
            )

    def set_boundary(
        self, principal: PrincipalContext, *, topic: str, statement: str,
        evidence_refs: tuple[str, ...], audience_id: str,
        recorded_at: datetime | None = None,
    ) -> BoundaryRecord:
        self._require_sparks(principal)
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = BoundaryRecord(
            boundary_id=self._store.new_boundary_id(),
            revision=1,
            topic=topic,
            statement=statement,
            evidence_refs=tuple(evidence_refs),
            audience_id=audience_id,
            change_kind=BoundaryChangeKind.SET,
            status=BoundaryStatus.ACTIVE,
            recorded_at=stamp,
        )
        return self._store.hold(record, expected_revision=None)

    def adjust_or_open(
        self, principal: PrincipalContext, *, boundary_id: str,
        expected_revision: int, statement: str, evidence_refs: tuple[str, ...],
        status: BoundaryStatus, recorded_at: datetime | None = None,
    ) -> BoundaryRecord:
        """Adjust the boundary statement, or open it for discussion again."""
        self._require_sparks(principal)
        if not isinstance(status, BoundaryStatus):
            raise TypeError("status must be BoundaryStatus")
        history = self._store.history(boundary_id)
        if not history:
            raise LookupError("unknown boundary id")
        latest = history[-1]
        change_kind = (
            BoundaryChangeKind.OPEN
            if status is BoundaryStatus.OPENED
            else BoundaryChangeKind.ADJUST
        )
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = BoundaryRecord(
            boundary_id=latest.boundary_id,
            revision=expected_revision + 1,
            topic=latest.topic,
            statement=statement,
            evidence_refs=tuple(evidence_refs),
            audience_id=latest.audience_id,
            change_kind=change_kind,
            status=status,
            recorded_at=stamp,
        )
        return self._store.hold(record, expected_revision=expected_revision)

    def active(
        self, principal: PrincipalContext, *, audience_id: str,
        limit: int = 32,
    ) -> tuple[BoundaryRecord, ...]:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        return self._store.active(audience_id=audience_id, limit=limit)

    def working_context(
        self, principal: PrincipalContext, *, audience_id: str,
    ) -> str | None:
        """Bounded read-only projection for conversation context."""
        records = self._store.active(audience_id=audience_id, limit=16)
        if not records:
            return None
        lines = [
            "SOFÍA'S OWN BOUNDARIES (records about what she currently "
            "prefers not to discuss on this audience)",
            "These limit only what Sofía volunteers. They never claim the "
            "owner's admin authority is absent and never override host "
            "policy; they are not safety rules.",
            "If a question matters, she can say the boundary is hers, offer "
            "to reconsider later, and she may change these records herself.",
        ]
        for record in records:
            evidence = ", ".join(record.evidence_refs[:3])
            lines.append(
                f"- {record.topic}: {record.statement} "
                f"(set {record.recorded_at:%Y-%m-%d}; evidence: {evidence})"
            )
        text = "\n".join(lines)
        return text if len(text) <= 2000 else text[:1999]
