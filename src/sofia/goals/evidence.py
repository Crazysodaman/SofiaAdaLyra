"""Typed, fail-closed goal evidence lookup and goal-owned evidence ledger."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class GoalEvidence:
    evidence_ref: str
    kind: str
    observed_at: datetime
    successful: bool | None = None
    goal_id: str | None = None
    action_id: str | None = None
    assertion: str | None = None
    cause_identified: bool = False
    coverage_started_at: datetime | None = None
    coverage_ended_at: datetime | None = None
    coverage_complete: bool = False
    source: str | None = None
    principal_id: str | None = None
    audience: str | None = None


class GoalEvidenceLedger:
    """Records reviewed facts/receipts; a goal record is never evidence."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS goal_evidence_record (
                    evidence_ref TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    successful INTEGER,
                    goal_id TEXT,
                    action_id TEXT,
                    assertion TEXT,
                    cause_identified INTEGER NOT NULL,
                    coverage_started_at TEXT,
                    coverage_ended_at TEXT,
                    coverage_complete INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    principal_id TEXT,
                    audience TEXT
                )
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(goal_evidence_record)")}
            if "principal_id" not in columns:
                db.execute("ALTER TABLE goal_evidence_record ADD COLUMN principal_id TEXT")
            if "audience" not in columns:
                db.execute("ALTER TABLE goal_evidence_record ADD COLUMN audience TEXT")

    def record(
        self,
        *,
        kind: str,
        observed_at: datetime,
        source: str,
        successful: bool | None = None,
        goal_id: str | None = None,
        action_id: str | None = None,
        assertion: str | None = None,
        cause_identified: bool = False,
        coverage_started_at: datetime | None = None,
        coverage_ended_at: datetime | None = None,
        coverage_complete: bool = False,
        payload: dict | None = None,
        evidence_ref: str | None = None,
        principal_id: str | None = None,
        audience: str | None = None,
    ) -> GoalEvidence:
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("evidence time must be timezone-aware")
        identifier = evidence_ref or f"goal-evidence:{uuid4()}"
        document = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
        values = (
            identifier, kind, observed_at.astimezone(timezone.utc).isoformat(),
            None if successful is None else int(successful), goal_id, action_id,
            assertion, int(cause_identified),
            None if coverage_started_at is None else coverage_started_at.isoformat(),
            None if coverage_ended_at is None else coverage_ended_at.isoformat(),
            int(coverage_complete), source, document, principal_id, audience,
        )
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            cursor = db.execute("""
                INSERT OR IGNORE INTO goal_evidence_record(
                    evidence_ref,kind,observed_at,successful,goal_id,action_id,
                    assertion,cause_identified,coverage_started_at,
                    coverage_ended_at,coverage_complete,source,payload_json,
                    principal_id,audience
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, values)
            if cursor.rowcount == 0:
                existing = db.execute("""
                    SELECT evidence_ref,kind,observed_at,successful,goal_id,action_id,
                           assertion,cause_identified,coverage_started_at,
                           coverage_ended_at,coverage_complete,source,payload_json,
                           principal_id,audience
                    FROM goal_evidence_record WHERE evidence_ref=?
                """, (identifier,)).fetchone()
                if existing != values:
                    raise ValueError(
                        "evidence reference already names different immutable evidence"
                    )
        record = GoalEvidenceIndex(self.path).lookup(identifier)
        if record is None:
            raise RuntimeError("goal evidence did not persist")
        return record


class GoalEvidenceIndex:
    """Resolve evidence into a typed record; generic State Plane sources are forbidden."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("canonical state database is required")

    @staticmethod
    def _has(db: sqlite3.Connection, table: str) -> bool:
        return db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,),
        ).fetchone() is not None

    def lookup(self, evidence_ref: str) -> GoalEvidence | None:
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            return None
        uri = self.path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
            if self._has(db, "goal_evidence_record"):
                row = db.execute("""
                    SELECT kind,observed_at,successful,goal_id,action_id,assertion,
                           cause_identified,coverage_started_at,coverage_ended_at,
                           coverage_complete,source,principal_id,audience
                    FROM goal_evidence_record WHERE evidence_ref=?
                """, (evidence_ref,)).fetchone()
                if row is not None:
                    return GoalEvidence(
                        evidence_ref, row[0], datetime.fromisoformat(row[1]),
                        None if row[2] is None else bool(row[2]), row[3], row[4],
                        row[5], bool(row[6]),
                        None if row[7] is None else datetime.fromisoformat(row[7]),
                        None if row[8] is None else datetime.fromisoformat(row[8]),
                        bool(row[9]), row[10], row[11], row[12],
                    )
            if self._has(db, "conversation_messages"):
                row = db.execute(
                    "SELECT created_at FROM conversation_messages WHERE id=?", (evidence_ref,),
                ).fetchone()
                if row is not None:
                    return GoalEvidence(
                        evidence_ref, "conversation_message",
                        datetime.fromisoformat(row[0]), source="conversation",
                    )
            if self._has(db, "ops_maintenance_receipt"):
                row = db.execute("""
                    SELECT completed_at,outcome,operation,target
                    FROM ops_maintenance_receipt WHERE request_id=?
                """, (evidence_ref,)).fetchone()
                if row is not None:
                    return GoalEvidence(
                        evidence_ref, "operation_receipt", datetime.fromisoformat(row[0]),
                        successful=row[1] == "verified", action_id=evidence_ref,
                        assertion=f"{row[2]}:{row[3] or ''}", source="ops-maintenance",
                    )
            if self._has(db, "evolve_evidence"):
                row = db.execute(
                    "SELECT kind,observed_at FROM evolve_evidence WHERE evidence_id=?",
                    (evidence_ref,),
                ).fetchone()
                if row is not None:
                    return GoalEvidence(
                        evidence_ref, "reviewed_evidence", datetime.fromisoformat(row[1]),
                        assertion=row[0], source="evolve",
                    )
            if self._has(db, "net_web_evidence"):
                row = db.execute(
                    "SELECT observed_at,status FROM net_web_evidence WHERE evidence_id=?",
                    (evidence_ref,),
                ).fetchone()
                if row is not None:
                    return GoalEvidence(
                        evidence_ref, "external_observation", datetime.fromisoformat(row[0]),
                        successful=row[1] == "success", source="public-web",
                    )
        return None

    def __call__(self, evidence_ref: str) -> bool:
        return self.lookup(evidence_ref) is not None
