"""Passive authenticated Fleet round-trip evidence for OPS advice.

Only a completed pinned-mTLS operation may append a sample.  This store does
not probe hosts, enroll nodes, select placement, or grant execution authority.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import sqlite3
from uuid import UUID

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class FleetLatencyEstimate:
    host_id: str
    node_id: UUID
    predicted_ms: float
    baseline_last_ms: float
    uncertainty: float
    sample_count: int
    newest_observed_at: datetime
    oldest_observed_at: datetime
    evidence_kind: str = "pinned_mtls_operation_result"


class FleetLatencyStore:
    """Canonical, bounded history of verified normal Fleet operations."""

    def __init__(self, state_path: Path | str) -> None:
        self._guard = CanonicalSQLiteGuard(Path(state_path))
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS ops_fleet_round_trip(
                    request_id TEXT PRIMARY KEY,
                    host_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    elapsed_ms REAL NOT NULL CHECK(elapsed_ms > 0),
                    observed_at TEXT NOT NULL,
                    evidence_kind TEXT NOT NULL CHECK(evidence_kind='pinned_mtls_operation_result')
                );
                CREATE INDEX IF NOT EXISTS idx_ops_fleet_round_trip_host_time
                ON ops_fleet_round_trip(host_id,observed_at DESC);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return self._guard.connect(timeout=10.0)

    def append_authenticated(
        self, *, request_id: UUID, host_id: str, node_id: UUID,
        capability: str, operation: str, outcome: str, elapsed_ms: float,
        observed_at: datetime,
    ) -> bool:
        if not isinstance(request_id, UUID) or not isinstance(node_id, UUID):
            raise TypeError("request_id and node_id must be UUIDs")
        if not isinstance(host_id, str) or not host_id.strip():
            raise ValueError("host_id required")
        if not all(isinstance(value, str) and value.strip() for value in (capability, operation, outcome)):
            raise ValueError("capability, operation and outcome required")
        if isinstance(elapsed_ms, bool) or not isinstance(elapsed_ms, (int, float)):
            raise TypeError("elapsed_ms must be numeric")
        elapsed = float(elapsed_ms)
        if not math.isfinite(elapsed) or elapsed <= 0 or elapsed > 7_200_000:
            raise ValueError("elapsed_ms outside bounded Fleet operation range")
        moment = _utc(observed_at)
        with closing(self._connect()) as db, db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO ops_fleet_round_trip VALUES(?,?,?,?,?,?,?,?,?)",
                (str(request_id), host_id, str(node_id), capability, operation,
                 outcome, elapsed, moment.isoformat(), "pinned_mtls_operation_result"),
            ).rowcount
            # Bounded per-host retention without touching other hosts.
            db.execute(
                "DELETE FROM ops_fleet_round_trip WHERE host_id=? AND request_id IN ("
                "SELECT request_id FROM ops_fleet_round_trip WHERE host_id=? "
                "ORDER BY observed_at DESC,request_id DESC LIMIT -1 OFFSET 512)",
                (host_id, host_id),
            )
        return bool(inserted)

    def estimate(
        self, *, host_id: str, node_id: UUID, at: datetime,
        max_age: timedelta = timedelta(minutes=10), limit: int = 16,
    ) -> FleetLatencyEstimate | None:
        moment = _utc(at)
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be UUID")
        if not isinstance(host_id, str) or not host_id.strip():
            raise ValueError("host_id required")
        if max_age <= timedelta(0) or type(limit) is not int or not 3 <= limit <= 64:
            raise ValueError("positive max_age and limit in [3, 64] required")
        cutoff = (moment - max_age).isoformat()
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT elapsed_ms,observed_at FROM ops_fleet_round_trip "
                "WHERE host_id=? AND node_id=? AND observed_at>=? AND observed_at<=? "
                "ORDER BY observed_at DESC,request_id DESC LIMIT ?",
                (host_id, str(node_id), cutoff, moment.isoformat(), limit),
            ).fetchall()
        if len(rows) < 3:
            return None
        values = [float(row[0]) for row in rows]
        # Recency-weighted mean is bounded and inspectable; last-value remains
        # visible as the deterministic comparison baseline.
        weights = [1.0 / (index + 1) for index in range(len(values))]
        predicted = sum(value * weight for value, weight in zip(values, weights)) / sum(weights)
        spread = max(values) - min(values)
        uncertainty = min(1.0, spread / max(predicted, 1.0) + 1.0 / len(values))
        stamps = [datetime.fromisoformat(row[1]).astimezone(timezone.utc) for row in rows]
        return FleetLatencyEstimate(
            host_id=host_id, node_id=node_id, predicted_ms=predicted,
            baseline_last_ms=values[0], uncertainty=uncertainty,
            sample_count=len(values), newest_observed_at=max(stamps),
            oldest_observed_at=min(stamps),
        )
