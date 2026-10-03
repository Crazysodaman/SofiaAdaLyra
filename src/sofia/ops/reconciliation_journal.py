"""Durable dedupe journal for Fleet reconciliation observations.

The journal records what drift/proposals were observed and when they resolved.
It is evidence/history only. It carries no execution authority.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3

from .repair_plan import FleetRepairProposal


@dataclass(frozen=True, slots=True)
class FleetReconciliationRecord:
    proposal_key: str
    drift_kind: str
    subject_id: str
    expected: str
    observed: str | None
    proposal_kind: str
    reason: str
    first_seen: datetime
    last_seen: datetime
    active: bool

    def __post_init__(self) -> None:
        for value, label in (
            (self.proposal_key, "proposal_key"),
            (self.drift_kind, "drift_kind"),
            (self.subject_id, "subject_id"),
            (self.expected, "expected"),
            (self.proposal_kind, "proposal_kind"),
            (self.reason, "reason"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty")
        for value, label in (
            (self.first_seen, "first_seen"),
            (self.last_seen, "last_seen"),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} must be timezone-aware")
        if type(self.active) is not bool:
            raise TypeError("active must be bool")


class FleetReconciliationJournal:
    def __init__(self, state_path: Path) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS ops_fleet_reconciliation (
                    proposal_key TEXT PRIMARY KEY,
                    drift_kind TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    expected TEXT NOT NULL,
                    observed TEXT,
                    proposal_kind TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK(active IN (0,1))
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ops_fleet_reconcile_active
                ON ops_fleet_reconciliation(active,last_seen DESC)
                """
            )

    @staticmethod
    def key_for(proposal: FleetRepairProposal) -> str:
        if not isinstance(proposal, FleetRepairProposal):
            raise TypeError("proposal must be FleetRepairProposal")
        drift = proposal.drift
        raw = "\0".join(
            (
                drift.kind,
                drift.subject_id,
                drift.expected,
                "" if drift.observed is None else drift.observed,
                proposal.kind.value,
            )
        ).encode("utf-8")
        return "fleet-repair:" + sha256(raw).hexdigest()[:24]

    @staticmethod
    def _moment(now: datetime | None) -> datetime:
        value = now or datetime.now(timezone.utc)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reconciliation time must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _decode(row) -> FleetReconciliationRecord:
        return FleetReconciliationRecord(
            proposal_key=row[0],
            drift_kind=row[1],
            subject_id=row[2],
            expected=row[3],
            observed=row[4],
            proposal_kind=row[5],
            reason=row[6],
            first_seen=datetime.fromisoformat(row[7]),
            last_seen=datetime.fromisoformat(row[8]),
            active=bool(row[9]),
        )

    def observe(
        self,
        proposals: tuple[FleetRepairProposal, ...],
        *,
        now: datetime | None = None,
    ) -> tuple[FleetReconciliationRecord, ...]:
        if not isinstance(proposals, tuple) or any(
            not isinstance(item, FleetRepairProposal) for item in proposals
        ):
            raise TypeError("proposals must be a tuple of FleetRepairProposal")
        moment = self._moment(now)
        active_keys = {self.key_for(item) for item in proposals}
        created_keys: list[str] = []

        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            for proposal in proposals:
                key = self.key_for(proposal)
                drift = proposal.drift
                existing = db.execute(
                    "SELECT 1 FROM ops_fleet_reconciliation WHERE proposal_key=?",
                    (key,),
                ).fetchone()
                if existing is None:
                    created_keys.append(key)
                db.execute(
                    """
                    INSERT INTO ops_fleet_reconciliation(
                        proposal_key,drift_kind,subject_id,expected,observed,
                        proposal_kind,reason,first_seen,last_seen,active
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,1)
                    ON CONFLICT(proposal_key) DO UPDATE SET
                        reason=excluded.reason,
                        last_seen=excluded.last_seen,
                        active=1
                    """,
                    (
                        key,
                        drift.kind,
                        drift.subject_id,
                        drift.expected,
                        drift.observed,
                        proposal.kind.value,
                        proposal.reason,
                        moment.isoformat(),
                        moment.isoformat(),
                    ),
                )

            if active_keys:
                placeholders = ",".join("?" for _ in active_keys)
                db.execute(
                    f"""
                    UPDATE ops_fleet_reconciliation
                    SET active=0,last_seen=?
                    WHERE active=1 AND proposal_key NOT IN ({placeholders})
                    """,
                    (moment.isoformat(), *sorted(active_keys)),
                )
            else:
                db.execute(
                    """
                    UPDATE ops_fleet_reconciliation
                    SET active=0,last_seen=?
                    WHERE active=1
                    """,
                    (moment.isoformat(),),
                )

        return tuple(
            record
            for key in created_keys
            if (record := self.get(key)) is not None
        )

    def get(self, proposal_key: str) -> FleetReconciliationRecord | None:
        if not isinstance(proposal_key, str) or not proposal_key.strip():
            raise ValueError("proposal_key required")
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db:
            row = db.execute(
                """
                SELECT proposal_key,drift_kind,subject_id,expected,observed,
                       proposal_kind,reason,first_seen,last_seen,active
                FROM ops_fleet_reconciliation
                WHERE proposal_key=?
                """,
                (proposal_key,),
            ).fetchone()
        return None if row is None else self._decode(row)

    def active(self) -> tuple[FleetReconciliationRecord, ...]:
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db:
            rows = db.execute(
                """
                SELECT proposal_key,drift_kind,subject_id,expected,observed,
                       proposal_kind,reason,first_seen,last_seen,active
                FROM ops_fleet_reconciliation
                WHERE active=1
                ORDER BY first_seen,proposal_key
                """
            ).fetchall()
        return tuple(self._decode(row) for row in rows)
