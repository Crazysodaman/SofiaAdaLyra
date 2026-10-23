"""Relationship repair offers, without forgiveness timers or leverage.

A repair record is Sofía's own evidence-linked apology or repair offer for
one subject scope, plus its observed outcome. Acceptance or refusal is only
ever a recorded observation; nothing here can force forgiveness, erase
another person's judgment, or convert a refusal into pressure. Reconnection
stays vulnerable and non-coercive by construction.
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
from sofia.core.social.principals import (
    PrincipalContext,
    SPARKS_PRINCIPAL_ID,
)


_SUBJECT = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,119}$")
_EVIDENCE = re.compile(r"^[a-z0-9][a-z0-9_.:@/-]{0,159}$")


class RepairChangeKind(str, Enum):
    OFFER = "offer"
    ACCEPT = "accept"
    DECLINE = "decline"
    WITHDRAW = "withdraw"


class RepairStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class RepairError(RuntimeError):
    """Race or stale revision in a repair record write."""


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("repair timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class RepairRecord:
    """One append-only revision of a relationship-repair offer."""

    repair_id: str
    revision: int
    principal_id: str
    subject: str
    message: str
    evidence_refs: tuple[str, ...]
    impression_ref: str | None
    audience_id: str
    change_kind: RepairChangeKind
    status: RepairStatus
    recorded_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.repair_id, str)
            or not self.repair_id.startswith("repair:")
            or len(self.repair_id) > 120
        ):
            raise ValueError("repair_id must be a canonical repair id")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("repair revision must be a positive integer")
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
        if (
            not isinstance(self.message, str)
            or not self.message.strip()
            or len(self.message.strip()) > 600
        ):
            raise ValueError("repair message must be bounded nonempty text")
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
            raise ValueError("repair evidence must be 1..8 distinct bounded refs")
        if self.impression_ref is not None and (
            not isinstance(self.impression_ref, str)
            or not self.impression_ref.startswith("impression:")
            or len(self.impression_ref) > 120
        ):
            raise ValueError(
                "impression_ref must be None or a canonical impression id"
            )
        if (
            not isinstance(self.audience_id, str)
            or not self.audience_id.strip()
            or len(self.audience_id) > 160
        ):
            raise ValueError("audience_id must be bounded nonempty text")
        if not isinstance(self.change_kind, RepairChangeKind):
            raise TypeError("change_kind must be RepairChangeKind")
        if not isinstance(self.status, RepairStatus):
            raise TypeError("status must be RepairStatus")
        expected = {
            RepairChangeKind.OFFER: RepairStatus.OPEN,
            RepairChangeKind.ACCEPT: RepairStatus.ACCEPTED,
            RepairChangeKind.DECLINE: RepairStatus.DECLINED,
            RepairChangeKind.WITHDRAW: RepairStatus.WITHDRAWN,
        }[self.change_kind]
        if self.status is not expected:
            raise ValueError("repair status must match its change kind")
        if self.revision == 1 and self.change_kind is not (
            RepairChangeKind.OFFER
        ):
            raise ValueError("repair origin is always an offer")
        if _utc(self.recorded_at) != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")


class RepairStore:
    """Canonical append-only persistence for relationship-repair offers."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS rel_repair_revision (
                    repair_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    principal_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    message TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    impression_ref TEXT,
                    audience_id TEXT NOT NULL,
                    change_kind TEXT NOT NULL CHECK(change_kind IN (
                        'offer','accept','decline','withdraw')),
                    status TEXT NOT NULL CHECK(status IN (
                        'open','accepted','declined','withdrawn')),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(repair_id,revision)
                );
                CREATE INDEX IF NOT EXISTS rel_repair_scope
                    ON rel_repair_revision(principal_id,audience_id,subject);
                CREATE TABLE IF NOT EXISTS rel_repair_current (
                    repair_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    UNIQUE(principal_id,subject,audience_id,repair_id)
                );
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode(record: RepairRecord) -> tuple:
        return (
            record.repair_id, record.revision, record.principal_id,
            record.subject, record.message,
            json.dumps(list(record.evidence_refs)), record.impression_ref,
            record.audience_id, record.change_kind.value,
            record.status.value, record.recorded_at.isoformat(),
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> RepairRecord:
        return RepairRecord(
            repair_id=row["repair_id"],
            revision=int(row["revision"]),
            principal_id=row["principal_id"],
            subject=row["subject"],
            message=row["message"],
            evidence_refs=tuple(json.loads(row["evidence_refs"])),
            impression_ref=row["impression_ref"],
            audience_id=row["audience_id"],
            change_kind=RepairChangeKind(row["change_kind"]),
            status=RepairStatus(row["status"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    def hold(
        self, value: RepairRecord, *, expected_revision: int | None,
    ) -> RepairRecord:
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT repair_id,revision FROM rel_repair_current
                WHERE principal_id=? AND subject=? AND audience_id=?""",
                (value.principal_id, value.subject, value.audience_id),
            ).fetchone()
            if expected_revision is None:
                if row is not None:
                    raise RepairError(
                        "a repair offer already exists for this scope; "
                        "revise it instead of opening a parallel one"
                    )
                if value.revision != 1 or value.change_kind is not (
                    RepairChangeKind.OFFER
                ):
                    raise RepairError(
                        "creating a repair requires offer revision 1"
                    )
            else:
                if row is None or int(row["revision"]) != expected_revision:
                    raise RepairError(
                        "revision changed or repair is absent; reload first"
                    )
                if row["repair_id"] != value.repair_id:
                    raise RepairError(
                        "repair identity changed; reload before revising"
                    )
            db.execute(
                """INSERT INTO rel_repair_revision VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                self._encode(value),
            )
            if row is None:
                db.execute(
                    """INSERT INTO rel_repair_current
                    (repair_id,principal_id,subject,audience_id,revision)
                    VALUES(?,?,?,?,?)""",
                    (value.repair_id, value.principal_id, value.subject,
                     value.audience_id, value.revision),
                )
            else:
                db.execute(
                    """UPDATE rel_repair_current SET revision=?
                    WHERE repair_id=?""",
                    (value.revision, value.repair_id),
                )
        return value

    def current(
        self, *, principal_id: str, subject: str, audience_id: str,
    ) -> RepairRecord | None:
        with closing(self._open()) as db:
            row = db.execute(
                """SELECT r.* FROM rel_repair_current c
                JOIN rel_repair_revision r
                ON r.repair_id=c.repair_id AND r.revision=c.revision
                WHERE c.principal_id=? AND c.subject=? AND c.audience_id=?""",
                (principal_id, subject, audience_id),
            ).fetchone()
        return None if row is None else self._decode(row)

    def history(self, repair_id: str, *, audience_id: str | None = None) -> tuple[RepairRecord, ...]:
        if audience_id is None:
            with closing(self._open()) as db:
                rows = db.execute(
                    """SELECT * FROM rel_repair_revision
                    WHERE repair_id=? ORDER BY revision ASC""",
                    (repair_id,),
                ).fetchall()
        else:
            with closing(self._open()) as db:
                rows = db.execute(
                    """SELECT r.* FROM rel_repair_revision r
                    JOIN rel_repair_current c ON c.repair_id=r.repair_id
                    WHERE r.repair_id=? AND c.audience_id=?
                    ORDER BY r.revision ASC""",
                    (repair_id, audience_id),
                ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def open_offers(
        self, *, audience_id: str, limit: int = 16,
    ) -> tuple[RepairRecord, ...]:
        if not isinstance(limit, int) or not 1 <= limit <= 64:
            raise ValueError("limit must be an int in 1..64")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT r.* FROM rel_repair_current c
                JOIN rel_repair_revision r
                ON r.repair_id=c.repair_id AND r.revision=c.revision
                WHERE c.audience_id=? AND r.status='open'
                ORDER BY r.recorded_at ASC LIMIT ?""",
                (audience_id, limit),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def new_repair_id(self) -> str:
        return f"repair:{uuid4()}"


class RepairService:
    """Owner-session-gated writer for relationship-repair offers."""

    def __init__(self, store: RepairStore) -> None:
        self._store = store

    @property
    def store(self) -> RepairStore:
        return self._store

    @staticmethod
    def _require_sparks(principal: PrincipalContext) -> None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "repair writes require the authenticated Sparks principal"
            )

    def offer(
        self, principal: PrincipalContext, *, about: str, subject: str,
        message: str, evidence_refs: tuple[str, ...],
        audience_id: str, impression_ref: str | None = None,
        recorded_at: datetime | None = None,
    ) -> RepairRecord:
        self._require_sparks(principal)
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = RepairRecord(
            repair_id=self._store.new_repair_id(),
            revision=1,
            principal_id=about,
            subject=subject,
            message=message,
            evidence_refs=tuple(evidence_refs),
            impression_ref=impression_ref,
            audience_id=audience_id,
            change_kind=RepairChangeKind.OFFER,
            status=RepairStatus.OPEN,
            recorded_at=stamp,
        )
        return self._store.hold(record, expected_revision=None)

    def observe_outcome(
        self, principal: PrincipalContext, *, repair_id: str,
        expected_revision: int, outcome: RepairChangeKind,
        message: str, evidence_refs: tuple[str, ...],
        recorded_at: datetime | None = None,
    ) -> RepairRecord:
        """Record an observed accept/decline or a voluntary withdrawal."""
        self._require_sparks(principal)
        if outcome is RepairChangeKind.OFFER:
            raise ValueError("outcomes are accept, decline, or withdraw")
        history = self._store.history(repair_id)
        if not history:
            raise LookupError("unknown repair id")
        latest = history[-1]
        if latest.status is not RepairStatus.OPEN:
            raise ValueError("only open repair offers have outcomes")
        stamp = _utc(recorded_at) if recorded_at is not None else _utc(
            datetime.now(timezone.utc)
        )
        record = RepairRecord(
            repair_id=latest.repair_id,
            revision=expected_revision + 1,
            principal_id=latest.principal_id,
            subject=latest.subject,
            message=message,
            evidence_refs=tuple(evidence_refs),
            impression_ref=latest.impression_ref,
            audience_id=latest.audience_id,
            change_kind=outcome,
            status={
                RepairChangeKind.ACCEPT: RepairStatus.ACCEPTED,
                RepairChangeKind.DECLINE: RepairStatus.DECLINED,
                RepairChangeKind.WITHDRAW: RepairStatus.WITHDRAWN,
            }[outcome],
            recorded_at=stamp,
        )
        return self._store.hold(record, expected_revision=expected_revision)
