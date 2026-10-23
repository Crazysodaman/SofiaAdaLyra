"""Durable non-artifact hobby records for Sofía's independent life.

Hobbies are leisure pursued for its own sake. Unlike LIFE projects they
produce no artifact, enter no goal pipeline, and consume no canonical RUN
authority. They are interior records of what Sofía enjoys spending time
on, with evidence-backed engagements that make decay and fulfillment
observable over time.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import sqlite3

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .model import aware, identifier, refs, text


class HobbyStatus(str, Enum):
    ACTIVE = "active"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class HobbyRecord:
    """One self-chosen hobby at one append-only revision."""

    hobby_id: str
    name: str
    description: str
    strength: float
    confidence: float
    status: HobbyStatus
    reason: str
    evidence_refs: tuple[str, ...]
    audience_id: str
    revision: int
    recorded_at: datetime

    def __post_init__(self) -> None:
        identifier(self.hobby_id, "hobby_id")
        text(self.name, "hobby name", 120)
        text(self.description, "hobby description", 1200)
        if not 0 <= self.strength <= 1 or not 0 <= self.confidence <= 1:
            raise ValueError("hobby strength/confidence must be in 0..1")
        if not isinstance(self.status, HobbyStatus):
            raise TypeError("HobbyStatus required")
        text(self.reason, "hobby reason", 1000)
        refs(self.evidence_refs, "hobby evidence_refs")
        text(self.audience_id, "audience_id", 160)
        if self.revision < 1:
            raise ValueError("hobby revision must be positive")
        aware(self.recorded_at, "recorded_at")


@dataclass(frozen=True, slots=True)
class HobbyEngagement:
    """One bounded, evidence-backed instance of spending time on a hobby."""

    engagement_id: str
    hobby_name: str
    summary: str
    duration_minutes: int
    evidence_refs: tuple[str, ...]
    audience_id: str
    engaged_at: datetime

    def __post_init__(self) -> None:
        identifier(self.engagement_id, "engagement_id")
        text(self.hobby_name, "hobby name", 120)
        text(self.summary, "engagement summary", 800)
        if not 1 <= self.duration_minutes <= 1440:
            raise ValueError("hobby duration must be in 1..1440 minutes")
        refs(self.evidence_refs, "engagement evidence_refs")
        text(self.audience_id, "audience_id", 160)
        aware(self.engaged_at, "engaged_at")


_ENGAGEMENT_RETENTION = 5000


class HobbyStore:
    """Canonical append-only persistence for hobbies and their engagements."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS life_hobby_revision (
                    hobby_id TEXT NOT NULL, name TEXT NOT NULL,
                    description TEXT NOT NULL, strength REAL NOT NULL,
                    confidence REAL NOT NULL, status TEXT NOT NULL,
                    reason TEXT NOT NULL, evidence_refs_json TEXT NOT NULL,
                    audience_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(hobby_id,revision),
                    UNIQUE(name,audience_id,revision)
                );
                CREATE INDEX IF NOT EXISTS life_hobby_current
                    ON life_hobby_revision(audience_id,status,strength DESC);
                CREATE TABLE IF NOT EXISTS life_hobby_engagement (
                    engagement_id TEXT PRIMARY KEY, hobby_name TEXT NOT NULL,
                    summary TEXT NOT NULL, duration_minutes INTEGER NOT NULL,
                    evidence_refs_json TEXT NOT NULL, audience_id TEXT NOT NULL,
                    engaged_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS life_hobby_engagement_hobby
                    ON life_hobby_engagement(audience_id,hobby_name,engaged_at DESC);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _row(row: sqlite3.Row) -> HobbyRecord:
        return HobbyRecord(
            row["hobby_id"], row["name"], row["description"],
            float(row["strength"]), float(row["confidence"]),
            HobbyStatus(row["status"]), row["reason"],
            tuple(json.loads(row["evidence_refs_json"])), row["audience_id"],
            int(row["revision"]), datetime.fromisoformat(row["recorded_at"]),
        )

    def hold(self, value: HobbyRecord, *, expected_revision: int | None) -> None:
        """CAS-append one hobby revision under its (name, audience) identity."""
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT hobby_id, revision FROM life_hobby_revision
                WHERE name=? AND audience_id=?
                ORDER BY revision DESC LIMIT 1""",
                (value.name, value.audience_id),
            ).fetchone()
            current = None if row is None else int(row["revision"])
            if current != expected_revision or value.revision != (
                1 if current is None else current + 1
            ):
                raise RuntimeError("hobby changed concurrently")
            if current is not None and row["hobby_id"] != value.hobby_id:
                raise RuntimeError("hobby identity changed between revisions")
            db.execute(
                "INSERT INTO life_hobby_revision VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    value.hobby_id, value.name, value.description,
                    value.strength, value.confidence, value.status.value,
                    value.reason, json.dumps(value.evidence_refs),
                    value.audience_id, value.revision,
                    value.recorded_at.astimezone(timezone.utc).isoformat(),
                ),
            )

    def current(self, name: str, *, audience_id: str) -> HobbyRecord | None:
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT * FROM life_hobby_revision WHERE name=? AND audience_id=?
                ORDER BY revision DESC LIMIT 1""",
                (name, audience_id),
            ).fetchone()
        return None if row is None else self._row(row)

    def by_id(self, hobby_id: str, *, audience_id: str) -> HobbyRecord | None:
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT * FROM life_hobby_revision
                WHERE hobby_id=? AND audience_id=?
                ORDER BY revision DESC LIMIT 1""",
                (hobby_id, audience_id),
            ).fetchone()
        return None if row is None else self._row(row)

    def last_engaged_at(self, name: str, *, audience_id: str) -> datetime | None:
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT engaged_at FROM life_hobby_engagement
                WHERE hobby_name=? AND audience_id=?
                ORDER BY engaged_at DESC,engagement_id DESC LIMIT 1""",
                (name, audience_id),
            ).fetchone()
        return None if row is None else datetime.fromisoformat(row[0])

    def active_hobbies(self, *, audience_id: str) -> tuple[HobbyRecord, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT current.* FROM life_hobby_revision current
                JOIN (SELECT name,MAX(revision) revision
                      FROM life_hobby_revision WHERE audience_id=?
                      GROUP BY name) latest
                ON current.name=latest.name AND current.revision=latest.revision
                WHERE current.audience_id=? AND current.status='active'
                ORDER BY current.strength DESC,current.name""",
                (audience_id, audience_id),
            ).fetchall()
        return tuple(self._row(row) for row in rows)

    def history(self, name: str, *, audience_id: str) -> tuple[HobbyRecord, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM life_hobby_revision WHERE name=? AND audience_id=?
                ORDER BY revision ASC""",
                (name, audience_id),
            ).fetchall()
        return tuple(self._row(row) for row in rows)

    def engagements(
        self, name: str, *, audience_id: str, limit: int = 32,
    ) -> tuple[HobbyEngagement, ...]:
        if not isinstance(limit, int) or not 1 <= limit <= 256:
            raise ValueError("engagement limit must be an int in 1..256")
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM life_hobby_engagement
                WHERE hobby_name=? AND audience_id=?
                ORDER BY engaged_at DESC,engagement_id DESC LIMIT ?""",
                (name, audience_id, limit),
            ).fetchall()
        return tuple(HobbyEngagement(
            row["engagement_id"], row["hobby_name"], row["summary"],
            int(row["duration_minutes"]), tuple(json.loads(row["evidence_refs_json"])),
            row["audience_id"], datetime.fromisoformat(row["engaged_at"]),
        ) for row in rows)

    def record_engagement(
        self, value: HobbyEngagement, *, now: datetime, hobby_id: str,
    ) -> None:
        """Append one engagement against the active hobby revision."""
        aware(now, "now")
        hobby = self.by_id(hobby_id, audience_id=value.audience_id)
        if hobby is None or hobby.status is not HobbyStatus.ACTIVE:
            raise RuntimeError("engagement requires an active hobby revision")
        if hobby.name != value.hobby_name:
            raise ValueError("engagement hobby name does not match the hobby record")
        if value.engaged_at > now:
            raise ValueError("engagement time may not lie in the future")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO life_hobby_engagement VALUES(?,?,?,?,?,?,?)",
                (
                    value.engagement_id, value.hobby_name, value.summary,
                    value.duration_minutes, json.dumps(value.evidence_refs),
                    value.audience_id,
                    value.engaged_at.astimezone(timezone.utc).isoformat(),
                ),
            )
            db.execute(
                """DELETE FROM life_hobby_engagement WHERE engagement_id IN (
                SELECT engagement_id FROM life_hobby_engagement
                ORDER BY engaged_at DESC,engagement_id DESC LIMIT -1 OFFSET ?)""",
                (_ENGAGEMENT_RETENTION,),
            )
