"""Bounded, resumable reflection batches for independent Aegis Cores.

Reflection is retrospective processing of supplied, owner-scoped candidates.
It is idempotent, checkpointed, cancellable and resumable, and it never writes
protected identity, protected memory, capabilities or execution authority.
Important corrections are surfaced for explicit confirmation rather than
applied silently.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
import sqlite3
from typing import Iterable
from uuid import UUID, uuid4

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

MAX_ROUTINE_CANDIDATES = 12
DEFAULT_TOKEN_BUDGET = 1600
REFLECTION_INTERVAL = timedelta(hours=24)
MAX_TEXT = 4000


class ReflectionStateError(RuntimeError):
    """The requested reflection batch transition is not valid."""


class ReflectionRateLimited(PermissionError):
    """This Core already completed a reflection window in the last 24 hours."""


class ReflectionConflictError(ValueError):
    """An idempotency key already names different reflection input."""


class ReflectionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


def _uuid(value: UUID | str, label: str) -> UUID:
    if isinstance(value, UUID):
        result = value
    elif isinstance(value, str) and value.strip():
        try:
            result = UUID(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a UUID") from exc
    else:
        raise TypeError(f"{label} must be a UUID or UUID string")
    if result.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return result


def _optional_owner(value: UUID | str | None) -> UUID | None:
    return None if value is None else _uuid(value, "owner_core_id")


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _approx_tokens(value: str) -> int:
    return max(1, ceil(len(value) / 4))


def _text(value: str, label: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must be bounded nonempty text")
    return value


@dataclass(frozen=True, slots=True)
class ReflectionCandidate:
    candidate_id: UUID
    owner_core_id: UUID
    content: str
    evidence: tuple[UUID, ...]
    significance: int = 5
    kind: str = "routine"

    def __post_init__(self) -> None:
        _uuid(self.candidate_id, "candidate_id")
        _uuid(self.owner_core_id, "owner_core_id")
        _text(self.content, "content")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise ValueError("reflection candidates require evidence references")
        for item in self.evidence:
            _uuid(item, "evidence")
        if type(self.significance) is not int or not 0 <= self.significance <= 10:
            raise ValueError("significance must be in [0, 10]")
        if self.kind not in ("routine", "correction"):
            raise ValueError("reflection kind must be routine or correction")

    def as_json(self) -> dict[str, object]:
        return {
            "candidate_id": str(self.candidate_id),
            "owner_core_id": str(self.owner_core_id),
            "content": self.content,
            "evidence": [str(item) for item in self.evidence],
            "significance": self.significance,
            "kind": self.kind,
        }

    @classmethod
    def from_json(cls, value: dict[str, object]) -> "ReflectionCandidate":
        return cls(
            candidate_id=UUID(str(value["candidate_id"])),
            owner_core_id=UUID(str(value["owner_core_id"])),
            content=str(value["content"]),
            evidence=tuple(UUID(str(item)) for item in value["evidence"]),
            significance=int(value["significance"]),
            kind=str(value["kind"]),
        )


@dataclass(frozen=True, slots=True)
class ReflectionAuditEvent:
    audit_id: UUID
    batch_id: UUID
    owner_core_id: UUID
    actor: str
    action: str
    occurred_at: datetime
    detail: dict[str, object]

    @property
    def grants_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ReflectionBatch:
    batch_id: UUID
    batch_key: str
    owner_core_id: UUID
    status: ReflectionStatus
    candidates: tuple[ReflectionCandidate, ...]
    checkpoint: int
    token_count: int
    max_candidates: int
    token_budget: int
    requires_confirmation: bool
    confirmation_prompt: str | None
    audit_actor: str
    created_at: datetime
    started_at: datetime | None
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None

    @property
    def total_candidates(self) -> int:
        return len(self.candidates)

    @property
    def output_ready(self) -> bool:
        return self.status is ReflectionStatus.COMPLETED

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def modifies_protected_identity(self) -> bool:
        return False

    @property
    def modifies_protected_memory(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ReflectionOutput:
    batch_id: UUID
    owner_core_id: UUID
    candidate_id: UUID
    summary: str
    requires_confirmation: bool
    recorded_at: datetime

    @property
    def grants_authority(self) -> bool:
        return False


class MulticoreReflectionService:
    """Checkpointed reflection batches with no capability or identity writes."""

    def __init__(
        self,
        state_path: str | Path,
        owner_core_id: UUID | str | None = None,
    ) -> None:
        self._owner_core_id = _optional_owner(owner_core_id)
        self._guard = CanonicalSQLiteGuard(Path(state_path))
        self._initialize()

    @property
    def owner_core_id(self) -> UUID | None:
        return self._owner_core_id

    def _connect(self) -> sqlite3.Connection:
        return self._guard.connect(timeout=10, check_same_thread=False)

    def _initialize(self) -> None:
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA busy_timeout = 10000")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS multicore_reflection_batch(
                    batch_id TEXT PRIMARY KEY,
                    batch_key TEXT NOT NULL,
                    owner_core_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    candidates_json TEXT NOT NULL,
                    checkpoint INTEGER NOT NULL,
                    token_count INTEGER NOT NULL,
                    max_candidates INTEGER NOT NULL,
                    token_budget INTEGER NOT NULL,
                    requires_confirmation INTEGER NOT NULL,
                    confirmation_prompt TEXT,
                    audit_actor TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    cancelled_at TEXT,
                    UNIQUE(owner_core_id, batch_key)
                );
                CREATE INDEX IF NOT EXISTS multicore_reflection_owner
                ON multicore_reflection_batch(owner_core_id, created_at);
                CREATE TABLE IF NOT EXISTS multicore_reflection_output(
                    batch_id TEXT NOT NULL,
                    owner_core_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    requires_confirmation INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(batch_id, candidate_id)
                );
                CREATE TABLE IF NOT EXISTS multicore_reflection_audit(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_id TEXT NOT NULL UNIQUE,
                    batch_id TEXT NOT NULL,
                    owner_core_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    detail_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS multicore_reflection_audit_batch
                ON multicore_reflection_audit(batch_id, sequence);
                """
            )

    def _require_owner(self, explicit: UUID | str | None = None) -> UUID:
        candidate = _optional_owner(explicit)
        if self._owner_core_id is not None:
            if candidate is not None and candidate != self._owner_core_id:
                raise PermissionError("reflection owner does not match this bound service")
            return self._owner_core_id
        if candidate is None:
            raise PermissionError("an explicit owner_core_id is required")
        return candidate

    @staticmethod
    def _row_batch(row: tuple[object, ...]) -> ReflectionBatch:
        return ReflectionBatch(
            batch_id=UUID(str(row[0])),
            batch_key=str(row[1]),
            owner_core_id=UUID(str(row[2])),
            status=ReflectionStatus(str(row[3])),
            candidates=tuple(
                ReflectionCandidate.from_json(item)
                for item in json.loads(str(row[4]))
            ),
            checkpoint=int(row[5]),
            token_count=int(row[6]),
            max_candidates=int(row[7]),
            token_budget=int(row[8]),
            requires_confirmation=bool(row[9]),
            confirmation_prompt=None if row[10] is None else str(row[10]),
            audit_actor=str(row[11]),
            created_at=datetime.fromisoformat(str(row[12])),
            started_at=None if row[13] is None else datetime.fromisoformat(str(row[13])),
            updated_at=datetime.fromisoformat(str(row[14])),
            completed_at=None if row[15] is None else datetime.fromisoformat(str(row[15])),
            cancelled_at=None if row[16] is None else datetime.fromisoformat(str(row[16])),
        )

    @staticmethod
    def _select_batch(db: sqlite3.Connection, batch_id: UUID):
        return db.execute(
            "SELECT batch_id,batch_key,owner_core_id,status,candidates_json,"
            "checkpoint,token_count,max_candidates,token_budget,"
            "requires_confirmation,confirmation_prompt,audit_actor,created_at,"
            "started_at,updated_at,completed_at,cancelled_at "
            "FROM multicore_reflection_batch WHERE batch_id=?",
            (str(batch_id),),
        ).fetchone()

    @staticmethod
    def _audit(
        db: sqlite3.Connection,
        *,
        batch_id: UUID,
        owner_core_id: UUID,
        actor: str,
        action: str,
        occurred_at: datetime,
        detail: dict[str, object] | None = None,
    ) -> UUID:
        identifier = uuid4()
        db.execute(
            "INSERT INTO multicore_reflection_audit("
            "audit_id,batch_id,owner_core_id,actor,action,occurred_at,detail_json"
            ") VALUES(?,?,?,?,?,?,?)",
            (
                str(identifier),
                str(batch_id),
                str(owner_core_id),
                actor,
                action,
                _iso(occurred_at),
                _canonical(detail or {}),
            ),
        )
        return identifier

    def create_batch(
        self,
        owner_core_id: UUID | str | None,
        candidates: Iterable[ReflectionCandidate],
        *,
        batch_key: str,
        now: datetime,
        actor: str = "reflection",
        max_candidates: int = MAX_ROUTINE_CANDIDATES,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
    ) -> ReflectionBatch | None:
        """Create one idempotent, rate-limited batch; empty input is skipped."""
        owner = self._require_owner(owner_core_id)
        moment = _utc(now, "now")
        if not isinstance(batch_key, str) or not batch_key.strip() or len(batch_key) > 160:
            raise ValueError("batch_key must be bounded nonempty text")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("actor must be nonempty text")
        if type(max_candidates) is not int or max_candidates < 1:
            raise ValueError("max_candidates must be a positive integer")
        if type(token_budget) is not int or token_budget < 1:
            raise ValueError("token_budget must be a positive integer")
        cap = min(max_candidates, MAX_ROUTINE_CANDIDATES)
        budget = min(token_budget, DEFAULT_TOKEN_BUDGET)

        kept: list[ReflectionCandidate] = []
        seen: set[UUID] = set()
        tokens = 0
        for candidate in candidates:
            if not isinstance(candidate, ReflectionCandidate):
                raise TypeError("candidates must be ReflectionCandidate values")
            if candidate.owner_core_id != owner:
                raise PermissionError("reflection candidate belongs to another Core")
            if candidate.content.strip() == "" or candidate.candidate_id in seen:
                continue
            cost = _approx_tokens(candidate.content)
            if len(kept) >= cap or tokens + cost > budget:
                break
            kept.append(candidate)
            seen.add(candidate.candidate_id)
            tokens += cost

        if not kept:
            return None

        encoded = tuple(candidate.as_json() for candidate in kept)
        encoded_text = _canonical(encoded)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT batch_id,batch_key,owner_core_id,status,candidates_json,"
                "checkpoint,token_count,max_candidates,token_budget,"
                "requires_confirmation,confirmation_prompt,audit_actor,created_at,"
                "started_at,updated_at,completed_at,cancelled_at "
                "FROM multicore_reflection_batch WHERE owner_core_id=? AND batch_key=?",
                (str(owner), batch_key),
            ).fetchone()
            if existing is not None:
                if str(existing[4]) != encoded_text:
                    raise ReflectionConflictError(
                        "batch_key already names different reflection input"
                    )
                return self._row_batch(tuple(existing))

            latest = db.execute(
                "SELECT COALESCE(started_at,created_at) FROM multicore_reflection_batch "
                "WHERE owner_core_id=? ORDER BY COALESCE(started_at,created_at) DESC LIMIT 1",
                (str(owner),),
            ).fetchone()
            if latest is not None:
                last = datetime.fromisoformat(str(latest[0]))
                if moment - last < REFLECTION_INTERVAL:
                    raise ReflectionRateLimited(
                        "this Core already reflected within the last 24 hours"
                    )

            important = tuple(
                candidate
                for candidate in kept
                if candidate.kind == "correction" or candidate.significance >= 8
            )
            prompt = None
            if important:
                prompt = (
                    "Confirm important correction before applying it to durable "
                    "memory: "
                    + ", ".join(str(item.candidate_id) for item in important[:MAX_ROUTINE_CANDIDATES])
                )
            batch_id = uuid4()
            db.execute(
                "INSERT INTO multicore_reflection_batch VALUES("
                "?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(batch_id),
                    batch_key,
                    str(owner),
                    ReflectionStatus.PENDING.value,
                    encoded_text,
                    0,
                    tokens,
                    cap,
                    budget,
                    int(bool(important)),
                    prompt,
                    actor,
                    _iso(moment),
                    None,
                    _iso(moment),
                    None,
                    None,
                ),
            )
            self._audit(
                db,
                batch_id=batch_id,
                owner_core_id=owner,
                actor=actor,
                action="batch_created",
                occurred_at=moment,
                detail={
                    "batch_key": batch_key,
                    "candidates": len(kept),
                    "token_count": tokens,
                    "requires_confirmation": bool(important),
                    "granted_authority": False,
                },
            )
            row = self._select_batch(db, batch_id)
        if row is None:
            raise ReflectionStateError("reflection batch could not be read after creation")
        return self._row_batch(tuple(row))

    def get_batch(
        self,
        batch_id: UUID | str,
        *,
        owner_core_id: UUID | str | None = None,
    ) -> ReflectionBatch | None:
        owner = self._require_owner(owner_core_id)
        identifier = _uuid(batch_id, "batch_id")
        with closing(self._connect()) as db:
            row = self._select_batch(db, identifier)
        if row is None or str(row[2]) != str(owner):
            return None
        return self._row_batch(tuple(row))

    def run(
        self,
        batch_id: UUID | str,
        *,
        now: datetime,
        owner_core_id: UUID | str | None = None,
        actor: str = "reflection",
        max_steps: int | None = None,
        cancel_after: int | None = None,
    ) -> ReflectionBatch:
        """Process from the durable checkpoint, writing one audit step per item."""
        owner = self._require_owner(owner_core_id)
        identifier = _uuid(batch_id, "batch_id")
        moment = _utc(now, "now")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("actor must be nonempty text")
        if max_steps is not None and (type(max_steps) is not int or max_steps < 1):
            raise ValueError("max_steps must be a positive integer or None")
        if cancel_after is not None and (type(cancel_after) is not int or cancel_after < 0):
            raise ValueError("cancel_after must be a nonnegative integer or None")

        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = self._select_batch(db, identifier)
            if row is None or str(row[2]) != str(owner):
                raise KeyError(str(identifier))
            batch = self._row_batch(tuple(row))
            if batch.status is ReflectionStatus.COMPLETED:
                return batch
            if batch.status is ReflectionStatus.CANCELLED:
                return batch
            if batch.status in (ReflectionStatus.PENDING, ReflectionStatus.FAILED):
                db.execute(
                    "UPDATE multicore_reflection_batch SET status=?,started_at=?,updated_at=? "
                    "WHERE batch_id=?",
                    (
                        ReflectionStatus.RUNNING.value,
                        _iso(batch.started_at or moment),
                        _iso(moment),
                        str(identifier),
                    ),
                )
                self._audit(
                    db,
                    batch_id=identifier,
                    owner_core_id=owner,
                    actor=actor,
                    action="batch_started",
                    occurred_at=moment,
                    detail={"checkpoint": batch.checkpoint},
                )

            processed = 0
            cancelled = False
            for index in range(batch.checkpoint, len(batch.candidates)):
                if max_steps is not None and processed >= max_steps:
                    break
                if cancel_after is not None and processed >= cancel_after:
                    cancelled = True
                    break
                candidate = batch.candidates[index]
                # Output and checkpoint are one atomic step. A crash before
                # commit leaves the previous checkpoint intact.
                self._record_output(db, batch, candidate, moment)
                db.execute(
                    "UPDATE multicore_reflection_batch SET checkpoint=?,updated_at=? "
                    "WHERE batch_id=?",
                    (index + 1, _iso(moment), str(identifier)),
                )
                self._audit(
                    db,
                    batch_id=identifier,
                    owner_core_id=owner,
                    actor=actor,
                    action="candidate_reflected",
                    occurred_at=moment,
                    detail={
                        "candidate_id": str(candidate.candidate_id),
                        "kind": candidate.kind,
                        "requires_confirmation": (
                            candidate.kind == "correction" or candidate.significance >= 8
                        ),
                        "checkpoint": index + 1,
                    },
                )
                processed += 1

            if cancelled:
                db.execute(
                    "UPDATE multicore_reflection_batch SET status=?,cancelled_at=?,updated_at=? "
                    "WHERE batch_id=?",
                    (
                        ReflectionStatus.CANCELLED.value,
                        _iso(moment),
                        _iso(moment),
                        str(identifier),
                    ),
                )
                self._audit(
                    db,
                    batch_id=identifier,
                    owner_core_id=owner,
                    actor=actor,
                    action="batch_cancelled",
                    occurred_at=moment,
                    detail={"checkpoint": batch.checkpoint + processed},
                )
            elif batch.checkpoint + processed >= len(batch.candidates):
                db.execute(
                    "UPDATE multicore_reflection_batch SET status=?,checkpoint=?,"
                    "completed_at=?,updated_at=? WHERE batch_id=?",
                    (
                        ReflectionStatus.COMPLETED.value,
                        len(batch.candidates),
                        _iso(moment),
                        _iso(moment),
                        str(identifier),
                    ),
                )
                self._audit(
                    db,
                    batch_id=identifier,
                    owner_core_id=owner,
                    actor=actor,
                    action="batch_completed",
                    occurred_at=moment,
                    detail={
                        "candidates": len(batch.candidates),
                        "requires_confirmation": batch.requires_confirmation,
                        "granted_authority": False,
                    },
                )
            updated = self._select_batch(db, identifier)
        if updated is None:
            raise ReflectionStateError("reflection batch could not be reread")
        return self._row_batch(tuple(updated))

    @staticmethod
    def _record_output(
        db: sqlite3.Connection,
        batch: ReflectionBatch,
        candidate: ReflectionCandidate,
        moment: datetime,
    ) -> None:
        requires_confirmation = (
            candidate.kind == "correction" or candidate.significance >= 8
        )
        summary = (
            f"Reflected {candidate.kind} candidate from {len(candidate.evidence)} "
            f"evidence reference(s); significance {candidate.significance}/10."
        )
        db.execute(
            "INSERT OR IGNORE INTO multicore_reflection_output VALUES(?,?,?,?,?,?,?)",
            (
                str(batch.batch_id),
                str(batch.owner_core_id),
                str(candidate.candidate_id),
                sha256(candidate.content.encode("utf-8")).hexdigest(),
                summary,
                int(requires_confirmation),
                _iso(moment),
            ),
        )

    def cancel(
        self,
        batch_id: UUID | str,
        *,
        now: datetime,
        owner_core_id: UUID | str | None = None,
        actor: str = "reflection",
    ) -> ReflectionBatch:
        owner = self._require_owner(owner_core_id)
        identifier = _uuid(batch_id, "batch_id")
        moment = _utc(now, "now")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("actor must be nonempty text")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = self._select_batch(db, identifier)
            if row is None or str(row[2]) != str(owner):
                raise KeyError(str(identifier))
            batch = self._row_batch(tuple(row))
            if batch.status is ReflectionStatus.COMPLETED:
                raise ReflectionStateError("a completed reflection batch cannot be cancelled")
            if batch.status is not ReflectionStatus.CANCELLED:
                db.execute(
                    "UPDATE multicore_reflection_batch SET status=?,cancelled_at=?,updated_at=? "
                    "WHERE batch_id=?",
                    (
                        ReflectionStatus.CANCELLED.value,
                        _iso(moment),
                        _iso(moment),
                        str(identifier),
                    ),
                )
                self._audit(
                    db,
                    batch_id=identifier,
                    owner_core_id=owner,
                    actor=actor,
                    action="batch_cancelled",
                    occurred_at=moment,
                    detail={"checkpoint": batch.checkpoint},
                )
            updated = self._select_batch(db, identifier)
        if updated is None:
            raise ReflectionStateError("reflection batch could not be reread")
        return self._row_batch(tuple(updated))

    def resume(
        self,
        batch_id: UUID | str,
        *,
        now: datetime,
        owner_core_id: UUID | str | None = None,
        actor: str = "reflection",
        max_steps: int | None = None,
    ) -> ReflectionBatch:
        owner = self._require_owner(owner_core_id)
        identifier = _uuid(batch_id, "batch_id")
        moment = _utc(now, "now")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = self._select_batch(db, identifier)
            if row is None or str(row[2]) != str(owner):
                raise KeyError(str(identifier))
            batch = self._row_batch(tuple(row))
            if batch.status is ReflectionStatus.COMPLETED:
                return batch
            if batch.status is ReflectionStatus.CANCELLED:
                db.execute(
                    "UPDATE multicore_reflection_batch SET status=?,updated_at=? WHERE batch_id=?",
                    (ReflectionStatus.PENDING.value, _iso(moment), str(identifier)),
                )
                self._audit(
                    db,
                    batch_id=identifier,
                    owner_core_id=owner,
                    actor=actor,
                    action="batch_resumed",
                    occurred_at=moment,
                    detail={"checkpoint": batch.checkpoint},
                )
        return self.run(
            identifier,
            now=moment,
            owner_core_id=owner,
            actor=actor,
            max_steps=max_steps,
        )

    def audit(
        self,
        batch_id: UUID | str,
        *,
        owner_core_id: UUID | str | None = None,
    ) -> tuple[ReflectionAuditEvent, ...]:
        owner = self._require_owner(owner_core_id)
        identifier = _uuid(batch_id, "batch_id")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT audit_id,batch_id,owner_core_id,actor,action,occurred_at,"
                "detail_json FROM multicore_reflection_audit "
                "WHERE batch_id=? AND owner_core_id=? ORDER BY sequence",
                (str(identifier), str(owner)),
            ).fetchall()
        return tuple(
            ReflectionAuditEvent(
                audit_id=UUID(str(row[0])),
                batch_id=UUID(str(row[1])),
                owner_core_id=UUID(str(row[2])),
                actor=str(row[3]),
                action=str(row[4]),
                occurred_at=datetime.fromisoformat(str(row[5])),
                detail=json.loads(str(row[6])),
            )
            for row in rows
        )

    def outputs(
        self,
        batch_id: UUID | str,
        *,
        owner_core_id: UUID | str | None = None,
    ) -> tuple[ReflectionOutput, ...]:
        owner = self._require_owner(owner_core_id)
        identifier = _uuid(batch_id, "batch_id")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT batch_id,owner_core_id,candidate_id,summary,"
                "requires_confirmation,recorded_at FROM multicore_reflection_output "
                "WHERE batch_id=? AND owner_core_id=? "
                "ORDER BY candidate_id",
                (str(identifier), str(owner)),
            ).fetchall()
        return tuple(
            ReflectionOutput(
                batch_id=UUID(str(row[0])),
                owner_core_id=UUID(str(row[1])),
                candidate_id=UUID(str(row[2])),
                summary=str(row[3]),
                requires_confirmation=bool(row[4]),
                recorded_at=datetime.fromisoformat(str(row[5])),
            )
            for row in rows
        )

    def close(self) -> None:
        return None

    def open(self) -> None:
        self._guard.validate()
