"""Durable habit evidence, patterns and expectation lifecycle."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .model import (
    CoverageState,
    ExpectationStatus,
    HabitCadence,
    HabitExpectation,
    HabitObservation,
    HabitPattern,
    HabitStatus,
    ObservationCoverage,
    ObservationSource,
)


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(timezone.utc).isoformat()


class HabitStore:
    """SQLite-backed evidence store. Raw observations are append-only."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing Sofía state database required")
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS habit_observation (
                        observation_id TEXT PRIMARY KEY,
                        principal_id TEXT NOT NULL,
                        audience_id TEXT,
                        kind TEXT NOT NULL,
                        value TEXT NOT NULL,
                        observed_at TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        context_json TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS habit_observation_lookup
                        ON habit_observation(principal_id,kind,value,observed_at);

                    CREATE TABLE IF NOT EXISTS habit_coverage (
                        coverage_id TEXT PRIMARY KEY,
                        principal_id TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        ended_at TEXT NOT NULL,
                        state TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS habit_coverage_lookup
                        ON habit_coverage(principal_id,kind,started_at,ended_at);

                    CREATE TABLE IF NOT EXISTS habit_pattern (
                        habit_id TEXT PRIMARY KEY,
                        principal_id TEXT NOT NULL,
                        audience_id TEXT,
                        kind TEXT NOT NULL,
                        value TEXT NOT NULL,
                        cadence TEXT NOT NULL DEFAULT 'irregular',
                        context_key TEXT,
                        context_value TEXT,
                        first_observed_at TEXT NOT NULL,
                        last_observed_at TEXT NOT NULL,
                        support_count INTEGER NOT NULL,
                        confidence REAL NOT NULL,
                        status TEXT NOT NULL,
                        evidence_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS habit_pattern_lookup
                        ON habit_pattern(principal_id,status,kind,value);

                    CREATE TABLE IF NOT EXISTS habit_pattern_revision (
                        revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        habit_id TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        cadence TEXT NOT NULL DEFAULT 'irregular',
                        support_count INTEGER NOT NULL,
                        confidence REAL NOT NULL,
                        status TEXT NOT NULL,
                        evidence_json TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS habit_expectation (
                        expectation_id TEXT PRIMARY KEY,
                        habit_id TEXT NOT NULL,
                        principal_id TEXT NOT NULL,
                        window_start TEXT NOT NULL,
                        window_end TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        evidence_id TEXT NOT NULL,
                        fulfilled_by TEXT
                    );
                    CREATE INDEX IF NOT EXISTS habit_expectation_pending
                        ON habit_expectation(principal_id,status,window_end);

                    CREATE TABLE IF NOT EXISTS habit_expectation_transition (
                        transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        expectation_id TEXT NOT NULL,
                        from_status TEXT NOT NULL,
                        to_status TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        evidence_id TEXT
                    );

                    CREATE TABLE IF NOT EXISTS habit_suppression (
                        principal_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        value TEXT NOT NULL,
                        context_key TEXT NOT NULL DEFAULT '',
                        context_value TEXT NOT NULL DEFAULT '',
                        source_id TEXT NOT NULL,
                        suppressed_at TEXT NOT NULL,
                        PRIMARY KEY(principal_id,kind,value,context_key,context_value)
                    );
                    """
                )
                pattern_columns = {
                    row[1]
                    for row in db.execute("PRAGMA table_info(habit_pattern)").fetchall()
                }
                if "cadence" not in pattern_columns:
                    db.execute(
                        "ALTER TABLE habit_pattern "
                        "ADD COLUMN cadence TEXT NOT NULL DEFAULT 'irregular'"
                    )
                revision_columns = {
                    row[1]
                    for row in db.execute(
                        "PRAGMA table_info(habit_pattern_revision)"
                    ).fetchall()
                }
                if "cadence" not in revision_columns:
                    db.execute(
                        "ALTER TABLE habit_pattern_revision "
                        "ADD COLUMN cadence TEXT NOT NULL DEFAULT 'irregular'"
                    )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record_observation(self, item: HabitObservation) -> bool:
        if not isinstance(item, HabitObservation):
            raise TypeError("HabitObservation required")
        payload = (
            item.observation_id,
            item.principal_id,
            item.audience_id,
            item.kind,
            item.value,
            _utc(item.observed_at),
            item.source_id,
            item.source.value,
            json.dumps(dict(item.context), sort_keys=True, ensure_ascii=False),
        )
        with closing(self._connect()) as db:
            with db:
                old = db.execute(
                    """
                    SELECT observation_id,principal_id,audience_id,kind,value,
                           observed_at,source_id,source,context_json
                    FROM habit_observation WHERE observation_id=?
                    """,
                    (item.observation_id,),
                ).fetchone()
                if old is not None:
                    if tuple(old) != payload:
                        raise ValueError("observation ID reused for different evidence")
                    return False
                db.execute(
                    "INSERT INTO habit_observation VALUES (?,?,?,?,?,?,?,?,?)",
                    payload,
                )
        return True

    def record_coverage(self, item: ObservationCoverage) -> bool:
        if not isinstance(item, ObservationCoverage):
            raise TypeError("ObservationCoverage required")
        payload = (
            item.coverage_id,
            item.principal_id,
            item.source_id,
            item.kind,
            _utc(item.started_at),
            _utc(item.ended_at),
            item.state.value,
        )
        with closing(self._connect()) as db:
            with db:
                old = db.execute(
                    "SELECT * FROM habit_coverage WHERE coverage_id=?",
                    (item.coverage_id,),
                ).fetchone()
                if old is not None:
                    if tuple(old) != payload:
                        raise ValueError("coverage ID reused for different evidence")
                    return False
                db.execute(
                    "INSERT INTO habit_coverage VALUES (?,?,?,?,?,?,?)",
                    payload,
                )
        return True

    def observations(
        self,
        *,
        principal_id: str,
        kind: str | None = None,
        since: datetime | None = None,
        limit: int = 500,
    ) -> tuple[HabitObservation, ...]:
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id required")
        if type(limit) is not int or not 1 <= limit <= 5000:
            raise ValueError("limit must be 1..5000")
        clauses = ["principal_id=?"]
        params: list[object] = [principal_id]
        if kind is not None:
            if not isinstance(kind, str) or not kind.strip():
                raise ValueError("kind must be nonempty or None")
            clauses.append("kind=?")
            params.append(kind)
        if since is not None:
            clauses.append("observed_at>=?")
            params.append(_utc(since))
        params.append(limit)
        with closing(self._connect()) as db:
            rows = db.execute(
                f"""
                SELECT * FROM habit_observation
                WHERE {' AND '.join(clauses)}
                ORDER BY observed_at DESC,observation_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return tuple(
            HabitObservation.create(
                observation_id=row["observation_id"],
                principal_id=row["principal_id"],
                audience_id=row["audience_id"],
                kind=row["kind"],
                value=row["value"],
                observed_at=datetime.fromisoformat(row["observed_at"]),
                source_id=row["source_id"],
                source=ObservationSource(row["source"]),
                context=json.loads(row["context_json"]),
            )
            for row in rows
        )

    def coverage_state(
        self,
        *,
        principal_id: str,
        kind: str,
        start: datetime,
        end: datetime,
    ) -> CoverageState:
        """Return the weakest overlapping coverage; absence without coverage is unknown."""
        start_iso = _utc(start)
        end_iso = _utc(end)
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT started_at,ended_at,state FROM habit_coverage
                WHERE principal_id=? AND kind=?
                  AND ended_at>? AND started_at<?
                ORDER BY started_at,ended_at
                """,
                (principal_id, kind, start_iso, end_iso),
            ).fetchall()
        if not rows:
            return CoverageState.UNAVAILABLE

        requested_start = datetime.fromisoformat(start_iso)
        requested_end = datetime.fromisoformat(end_iso)
        covered = []
        for row in rows:
            if CoverageState(row["state"]) is not CoverageState.COVERED:
                continue
            left = max(requested_start, datetime.fromisoformat(row["started_at"]))
            right = min(requested_end, datetime.fromisoformat(row["ended_at"]))
            if right > left:
                covered.append((left, right))
        if not covered:
            return CoverageState.PARTIAL

        cursor = requested_start
        for left, right in covered:
            if left > cursor:
                return CoverageState.PARTIAL
            if right > cursor:
                cursor = right
            if cursor >= requested_end:
                return CoverageState.COVERED
        return CoverageState.PARTIAL

    def suppressed(
        self,
        *,
        principal_id: str,
        kind: str,
        value: str,
        context_key: str | None,
        context_value: str | None,
    ) -> bool:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT 1 FROM habit_suppression
                WHERE principal_id=? AND kind=? AND value=?
                  AND context_key=? AND context_value=?
                """,
                (
                    principal_id,
                    kind,
                    value,
                    context_key or "",
                    context_value or "",
                ),
            ).fetchone()
        return row is not None

    def suppress(
        self,
        *,
        principal_id: str,
        kind: str,
        value: str,
        source_id: str,
        at: datetime,
        context_key: str | None = None,
        context_value: str | None = None,
    ) -> None:
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    INSERT INTO habit_suppression(
                        principal_id,kind,value,context_key,context_value,
                        source_id,suppressed_at
                    )
                    VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(principal_id,kind,value,context_key,context_value)
                    DO UPDATE SET source_id=excluded.source_id,
                                  suppressed_at=excluded.suppressed_at
                    """,
                    (
                        principal_id,
                        kind,
                        value,
                        context_key or "",
                        context_value or "",
                        source_id,
                        _utc(at),
                    ),
                )

    def save_pattern(self, pattern: HabitPattern, *, at: datetime) -> None:
        if not isinstance(pattern, HabitPattern):
            raise TypeError("HabitPattern required")
        now = _utc(at)
        evidence = json.dumps(pattern.evidence_ids, ensure_ascii=False)
        with closing(self._connect()) as db:
            with db:
                old = db.execute(
                    "SELECT status FROM habit_pattern WHERE habit_id=?",
                    (pattern.habit_id,),
                ).fetchone()
                if old is not None and HabitStatus(old["status"]) is HabitStatus.SUPPRESSED:
                    return
                db.execute(
                    """
                    INSERT INTO habit_pattern(
                        habit_id,principal_id,audience_id,kind,value,cadence,
                        context_key,context_value,first_observed_at,last_observed_at,
                        support_count,confidence,status,evidence_json,updated_at
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(habit_id) DO UPDATE SET
                        first_observed_at=excluded.first_observed_at,
                        last_observed_at=excluded.last_observed_at,
                        support_count=excluded.support_count,
                        confidence=excluded.confidence,
                        status=excluded.status,
                        evidence_json=excluded.evidence_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        pattern.habit_id,
                        pattern.principal_id,
                        pattern.audience_id,
                        pattern.kind,
                        pattern.value,
                        pattern.cadence.value,
                        pattern.context_key,
                        pattern.context_value,
                        _utc(pattern.first_observed_at),
                        _utc(pattern.last_observed_at),
                        pattern.support_count,
                        float(pattern.confidence),
                        pattern.status.value,
                        evidence,
                        now,
                    ),
                )
                db.execute(
                    """
                    INSERT INTO habit_pattern_revision(
                        habit_id,recorded_at,cadence,support_count,confidence,status,evidence_json
                    ) VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        pattern.habit_id,
                        now,
                        pattern.cadence.value,
                        pattern.support_count,
                        float(pattern.confidence),
                        pattern.status.value,
                        evidence,
                    ),
                )

    def patterns(
        self,
        *,
        principal_id: str,
        statuses: tuple[HabitStatus, ...] | None = None,
    ) -> tuple[HabitPattern, ...]:
        clauses = ["principal_id=?"]
        params: list[object] = [principal_id]
        if statuses is not None:
            if not statuses or any(not isinstance(x, HabitStatus) for x in statuses):
                raise ValueError("statuses must contain HabitStatus values")
            placeholders = ",".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(item.value for item in statuses)
        with closing(self._connect()) as db:
            rows = db.execute(
                f"""
                SELECT * FROM habit_pattern
                WHERE {' AND '.join(clauses)}
                ORDER BY confidence DESC,last_observed_at DESC,habit_id
                """,
                tuple(params),
            ).fetchall()
        return tuple(
            HabitPattern(
                habit_id=row["habit_id"],
                principal_id=row["principal_id"],
                audience_id=row["audience_id"],
                kind=row["kind"],
                value=row["value"],
                cadence=HabitCadence(row["cadence"]),
                context_key=row["context_key"],
                context_value=row["context_value"],
                first_observed_at=datetime.fromisoformat(row["first_observed_at"]),
                last_observed_at=datetime.fromisoformat(row["last_observed_at"]),
                support_count=int(row["support_count"]),
                confidence=float(row["confidence"]),
                status=HabitStatus(row["status"]),
                evidence_ids=tuple(json.loads(row["evidence_json"])),
            )
            for row in rows
        )

    def save_expectation(self, item: HabitExpectation) -> bool:
        if not isinstance(item, HabitExpectation):
            raise TypeError("HabitExpectation required")
        payload = (
            item.expectation_id,
            item.habit_id,
            item.principal_id,
            _utc(item.window_start),
            _utc(item.window_end),
            _utc(item.created_at),
            item.status.value,
            item.evidence_id,
            item.fulfilled_by,
        )
        with closing(self._connect()) as db:
            with db:
                old = db.execute(
                    "SELECT * FROM habit_expectation WHERE expectation_id=?",
                    (item.expectation_id,),
                ).fetchone()
                if old is not None:
                    if tuple(old) != payload:
                        raise ValueError("expectation ID reused for different data")
                    return False
                db.execute(
                    "INSERT INTO habit_expectation VALUES (?,?,?,?,?,?,?,?,?)",
                    payload,
                )
        return True

    def pending_expectations(
        self,
        *,
        principal_id: str,
    ) -> tuple[HabitExpectation, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT * FROM habit_expectation
                WHERE principal_id=? AND status='pending'
                ORDER BY window_start,expectation_id
                """,
                (principal_id,),
            ).fetchall()
        return tuple(self._expectation(row) for row in rows)

    def transition_expectation(
        self,
        expectation_id: str,
        *,
        expected: ExpectationStatus,
        target: ExpectationStatus,
        at: datetime,
        evidence_id: str | None = None,
    ) -> HabitExpectation:
        if expected is not ExpectationStatus.PENDING:
            raise ValueError("only pending expectations can transition")
        if target not in {
            ExpectationStatus.FULFILLED,
            ExpectationStatus.MISSED,
            ExpectationStatus.UNCERTAIN,
            ExpectationStatus.EXPIRED,
        }:
            raise ValueError("invalid expectation target")
        with closing(self._connect()) as db:
            with db:
                row = db.execute(
                    "SELECT * FROM habit_expectation WHERE expectation_id=?",
                    (expectation_id,),
                ).fetchone()
                if row is None:
                    raise LookupError("expectation not found")
                if ExpectationStatus(row["status"]) is not expected:
                    raise ValueError("expectation is not in expected state")
                if target is ExpectationStatus.FULFILLED and not evidence_id:
                    raise ValueError("fulfilled expectation requires evidence")
                db.execute(
                    """
                    UPDATE habit_expectation
                    SET status=?,fulfilled_by=?
                    WHERE expectation_id=? AND status=?
                    """,
                    (
                        target.value,
                        evidence_id if target is ExpectationStatus.FULFILLED else None,
                        expectation_id,
                        expected.value,
                    ),
                )
                db.execute(
                    """
                    INSERT INTO habit_expectation_transition(
                        expectation_id,from_status,to_status,occurred_at,evidence_id
                    ) VALUES(?,?,?,?,?)
                    """,
                    (
                        expectation_id,
                        expected.value,
                        target.value,
                        _utc(at),
                        evidence_id,
                    ),
                )
                updated = db.execute(
                    "SELECT * FROM habit_expectation WHERE expectation_id=?",
                    (expectation_id,),
                ).fetchone()
        assert updated is not None
        return self._expectation(updated)

    @staticmethod
    def _expectation(row: sqlite3.Row) -> HabitExpectation:
        return HabitExpectation(
            expectation_id=row["expectation_id"],
            habit_id=row["habit_id"],
            principal_id=row["principal_id"],
            window_start=datetime.fromisoformat(row["window_start"]),
            window_end=datetime.fromisoformat(row["window_end"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            status=ExpectationStatus(row["status"]),
            evidence_id=row["evidence_id"],
            fulfilled_by=row["fulfilled_by"],
        )
