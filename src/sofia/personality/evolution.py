"""Evidence-reviewed trait-level personality evolution.

Sofía's personality can evolve through experience, but never silently and
never without a reviewed record. This package appends audited trait-level
revisions under one canonical writer. It stores durable personal state;
it never executes anything and never grants authority. The static seed
profile and the identity floor are unchanged by evolution.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path
import re
import sqlite3

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

_TRAIT = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,59}$")


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or (
        value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone()


def _bounded_weight(value, label: str = "value") -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(f"{label} must be a number in 0..1")
    return float(value)


class TraitChangeKind(str, Enum):
    """Why one trait revision exists."""

    ORIGIN = "origin"
    ADJUST = "adjust"
    CORRECT = "correct"
    RETIRE = "retire"


class TraitEvolutionError(RuntimeError):
    """Raised when a trait revision does not match the stored revision."""


_WEIGHTED_KINDS = frozenset({
    TraitChangeKind.ORIGIN,
    TraitChangeKind.ADJUST,
    TraitChangeKind.CORRECT,
})


@dataclass(frozen=True, slots=True)
class TraitEvolutionRecord:
    """One stored revision of an evidence-reviewed trait weight."""

    trait: str
    revision: int
    weight: float
    confidence: float
    change_kind: TraitChangeKind
    reason: str
    evidence_refs: tuple[str, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.trait, str) or _TRAIT.fullmatch(self.trait) is None:
            raise ValueError(
                "trait must be a canonical token of 2..60 characters"
            )
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        weight = _bounded_weight(self.weight, "weight")
        _bounded_weight(self.confidence, "confidence")
        if not isinstance(self.change_kind, TraitChangeKind):
            raise TypeError("change_kind must be a TraitChangeKind")
        reason = self.reason.strip()
        if not 1 <= len(reason) <= 600:
            raise ValueError("reason must be bounded text of 1..600 characters")
        if not self._refs_are_valid(self.evidence_refs):
            raise ValueError(
                "evidence_refs must be 1..8 distinct bounded "
                "`source:value` references"
            )
        if self.revision == 1 and self.change_kind is not (
            TraitChangeKind.ORIGIN
        ):
            raise ValueError("the first revision must have change_kind origin")
        if self.revision > 1 and self.change_kind is TraitChangeKind.ORIGIN:
            raise ValueError("only the first revision may have change_kind origin")
        if self.change_kind is TraitChangeKind.RETIRE and weight != 0.0:
            raise ValueError("a retired trait must record weight 0.0")
        if self.change_kind in _WEIGHTED_KINDS and weight <= 0.0:
            raise ValueError("an active trait revision must have weight > 0.0")
        if self.recorded_at.tzinfo is None or (
            self.recorded_at.utcoffset() is None
        ):
            raise ValueError("recorded_at must be timezone-aware")

    @staticmethod
    def _refs_are_valid(refs: tuple[str, ...]) -> bool:
        if not isinstance(refs, tuple) or not 1 <= len(refs) <= 8:
            return False
        if len(set(refs)) != len(refs):
            return False
        for ref in refs:
            if not isinstance(ref, str):
                return False
            if len(ref) < 4 or len(ref) > 240:
                return False
            if ":" not in ref:
                return False
            source, _, value = ref.partition(":")
            if not source.isidentifier():
                return False
            if not value.strip():
                return False
            if ref != ref.strip():
                return False
        return True


@dataclass(frozen=True, slots=True)
class TraitDriftEntry:
    """Weight movement for one trait across a bounded observation window."""

    trait: str
    previous_weight: float
    current_weight: float
    revisions_in_window: int

    @property
    def delta(self) -> float:
        return round(self.current_weight - self.previous_weight, 6)


class TraitEvolutionStore:
    """Canonical append-only writer for trait evolution revisions."""

    def __init__(self, state_path: Path | str) -> None:
        self._guard = CanonicalSQLiteGuard(state_path)
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS personality_trait_evolution_revision (
                    trait TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    weight REAL NOT NULL
                        CHECK(weight >= 0 AND weight <= 1),
                    confidence REAL NOT NULL
                        CHECK(confidence >= 0 AND confidence <= 1),
                    change_kind TEXT NOT NULL
                        CHECK(change_kind IN
                            ('origin','adjust','correct','retire')),
                    reason TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(trait, revision)
                );
                CREATE TABLE IF NOT EXISTS personality_trait_current (
                    trait TEXT NOT NULL PRIMARY KEY,
                    revision INTEGER NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode(record: TraitEvolutionRecord) -> tuple:
        return (
            record.trait,
            record.revision,
            record.weight,
            record.confidence,
            record.change_kind.value,
            record.reason,
            json.dumps(list(record.evidence_refs)),
            record.recorded_at.isoformat(),
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> TraitEvolutionRecord:
        return TraitEvolutionRecord(
            trait=row["trait"],
            revision=int(row["revision"]),
            weight=float(row["weight"]),
            confidence=float(row["confidence"]),
            change_kind=TraitChangeKind(row["change_kind"]),
            reason=row["reason"],
            evidence_refs=tuple(json.loads(row["evidence_refs"])),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    def hold(
        self,
        *,
        trait: str,
        weight: float,
        confidence: float,
        change_kind: TraitChangeKind,
        reason: str,
        evidence_refs: tuple[str, ...],
        expected_revision: int | None,
        now: datetime,
    ) -> TraitEvolutionRecord:
        recorded_at = _utc(now, "trait evolution timestamp")
        revision = (
            1 if expected_revision is None else int(expected_revision) + 1
        )
        record = TraitEvolutionRecord(
            trait=trait,
            revision=revision,
            weight=weight,
            confidence=confidence,
            change_kind=change_kind,
            reason=reason,
            evidence_refs=evidence_refs,
            recorded_at=recorded_at,
        )
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT revision FROM personality_trait_current
                WHERE trait=?
                """,
                (record.trait,),
            ).fetchone()
            current = None if row is None else int(row["revision"])
            if expected_revision is None:
                if current is not None:
                    raise TraitEvolutionError(
                        "trait already records origin; reload and adjust "
                        f"with expected_revision={current}"
                    )
            else:
                if current != expected_revision:
                    raise TraitEvolutionError(
                        f"revision changed; expected {expected_revision} "
                        f"but current is {current}"
                    )
            db.execute(
                """
                INSERT INTO personality_trait_evolution_revision VALUES
                (?,?,?,?,?,?,?,?)
                """,
                self._encode(record),
            )
            db.execute(
                """
                INSERT INTO personality_trait_current (trait, revision)
                VALUES (?,?)
                ON CONFLICT(trait) DO UPDATE SET revision=excluded.revision
                """,
                (record.trait, record.revision),
            )
        return record

    def current(self, trait: str) -> TraitEvolutionRecord | None:
        if not isinstance(trait, str) or _TRAIT.fullmatch(trait) is None:
            raise ValueError("trait must be a canonical token")
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT r.* FROM personality_trait_evolution_revision r
                JOIN personality_trait_current c
                  ON c.trait=r.trait AND c.revision=r.revision
                WHERE c.trait=?
                """,
                (trait,),
            ).fetchone()
        return None if row is None else self._decode(row)

    def current_all(self) -> tuple[TraitEvolutionRecord, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT r.* FROM personality_trait_evolution_revision r
                JOIN personality_trait_current c
                  ON c.trait=r.trait AND c.revision=r.revision
                ORDER BY r.trait
                """
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def history(self, trait: str) -> tuple[TraitEvolutionRecord, ...]:
        if not isinstance(trait, str) or _TRAIT.fullmatch(trait) is None:
            raise ValueError("trait must be a canonical token")
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT r.* FROM personality_trait_evolution_revision r
                WHERE r.trait=?
                ORDER BY r.revision
                """,
                (trait,),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def weight_before(self, trait: str, *, at: datetime) -> float | None:
        """Latest recorded weight at or before `at`; None when unrecorded."""
        if not isinstance(trait, str) or _TRAIT.fullmatch(trait) is None:
            raise ValueError("trait must be a canonical token")
        at = _utc(at, "observation timestamp")
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT weight FROM personality_trait_evolution_revision
                WHERE trait=? AND recorded_at<=?
                ORDER BY recorded_at DESC, revision DESC
                LIMIT 1
                """,
                (trait, at.isoformat()),
            ).fetchone()
        return None if row is None else float(row["weight"])

    def active_influences(
        self,
        *,
        minimum_confidence: float = 0.6,
        minimum_weight: float = 0.05,
        limit: int = 12,
    ) -> tuple[TraitEvolutionRecord, ...]:
        """Deterministic projection of active reviewed trait influences."""
        _bounded_weight(minimum_confidence, "minimum_confidence")
        _bounded_weight(minimum_weight, "minimum_weight")
        if type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("limit must be in 1..32")
        selected = [
            record
            for record in sorted(
                self.current_all(),
                key=lambda record: (-record.weight, record.trait),
            )
            if record.change_kind is not TraitChangeKind.RETIRE
            and record.weight >= minimum_weight
            and record.confidence >= minimum_confidence
        ]
        return tuple(selected[:limit])

    def drift_entries(
        self,
        *,
        window_days: int,
        now: datetime,
    ) -> tuple[TraitDriftEntry, ...]:
        """Per-trait weight movement across a bounded observation window."""
        if type(window_days) is not int or not 1 <= window_days <= 365:
            raise ValueError("window_days must be in 1..365")
        now = _utc(now, "observation timestamp")
        window_start = now - timedelta(days=window_days)
        entries: list[TraitDriftEntry] = []
        for current_record in self.current_all():
            trait = current_record.trait
            previous = self.weight_before(trait, at=window_start)
            with closing(self._connect()) as db:
                row = db.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM personality_trait_evolution_revision
                    WHERE trait=? AND recorded_at>? AND recorded_at<=?
                    """,
                    (trait, window_start.isoformat(), now.isoformat()),
                ).fetchone()
            entries.append(TraitDriftEntry(
                trait=trait,
                previous_weight=(0.0 if previous is None else previous),
                current_weight=current_record.weight,
                revisions_in_window=int(row["total"]),
            ))
        return tuple(entries)
