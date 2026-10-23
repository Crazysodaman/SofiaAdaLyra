"""Bounded, authority-free Fleet pressure shadow pilot (ML-008/ML-010).

The pilot reuses OPS telemetry, the canonical learning lineage owner and the
application background coordinator.  It never selects a host, moves a
workload, calls a capability, or changes its own prediction mode.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from sofia.core.goals.evidence import GoalEvidenceLedger
from sofia.platform.ops.activity import ActivityMode
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .contracts import DataUse, OutcomeClass, Prediction, PredictionMode, SourceClass
from .fleet_advisory import FleetAdvisoryEngine
from .service import GroundedSample, LearningService


_PURPOSE = "host-pressure-forecast"
_ALGORITHM = "bounded-cpu-linear-ewma-v1"
_CANDIDATE_DIGEST = sha256(_ALGORITHM.encode("utf-8")).hexdigest()
_REQUIRED_USES = (
    DataUse.OBSERVATION,
    DataUse.STORAGE,
    DataUse.FEATURE_EXTRACTION,
    DataUse.STATISTICAL_TRAINING,
)


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _bounded(value: float) -> float:
    return min(100.0, max(0.0, value))


@dataclass(frozen=True, slots=True)
class PressureForecast:
    forecast_id: str
    host_id: str
    prediction_at: datetime
    target_at: datetime
    candidate_percent: float
    last_value_percent: float
    ewma_percent: float
    uncertainty: float
    source_ref: str


class FleetPressurePilot:
    """CPU-first forecast/evaluation attached to existing application owners."""

    def __init__(
        self,
        state_path: str | Path,
        *,
        learning: LearningService,
        ops_service,
        principal_id: str = "sparks",
        audience_id: str = "local:text",
        horizon: timedelta = timedelta(minutes=5),
        max_source_age: timedelta = timedelta(minutes=10),
        retention: timedelta = timedelta(days=30),
    ) -> None:
        self._guard = CanonicalSQLiteGuard(Path(state_path))
        self._learning = learning
        self._ops = ops_service
        self._principal_id = principal_id
        self._audience_id = audience_id
        self._horizon = horizon
        self._max_source_age = max_source_age
        self._retention = retention
        self._advisory = FleetAdvisoryEngine(state_path, ops_service=ops_service)
        if horizon <= timedelta(0) or horizon > timedelta(hours=1):
            raise ValueError("forecast horizon must be in (0, 1 hour]")
        if max_source_age <= timedelta(0) or max_source_age > timedelta(hours=1):
            raise ValueError("source age must be in (0, 1 hour]")
        if retention < timedelta(days=1) or retention > timedelta(days=90):
            raise ValueError("pilot retention must be in [1, 90] days")
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS ml_fleet_pressure_forecast(
                    forecast_id TEXT PRIMARY KEY,
                    host_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    grant_id TEXT NOT NULL,
                    prediction_at TEXT NOT NULL,
                    target_at TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    source_observed_at TEXT NOT NULL,
                    feature_json TEXT NOT NULL,
                    candidate_digest TEXT NOT NULL,
                    candidate_percent REAL NOT NULL,
                    last_value_percent REAL NOT NULL,
                    ewma_percent REAL NOT NULL,
                    uncertainty REAL NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','settled','unknown')),
                    outcome_ref TEXT,
                    actual_percent REAL,
                    candidate_error REAL,
                    last_value_error REAL,
                    ewma_error REAL,
                    settled_at TEXT,
                    retention_until TEXT NOT NULL,
                    UNIQUE(host_id,source_observed_at,target_at)
                );
                CREATE INDEX IF NOT EXISTS idx_ml_fleet_pressure_pending
                ON ml_fleet_pressure_forecast(status,target_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return self._guard.connect(timeout=10)

    def ready(self, *, at: datetime, busy: bool = False) -> bool:
        moment = _utc(at, "at")
        if type(busy) is not bool:
            raise TypeError("busy must be bool")
        return (
            not busy
            and self._learning.mode() in {PredictionMode.OBSERVE, PredictionMode.SHADOW}
            and self._learning.active_grant(
                principal_id=self._principal_id,
                audience_id=self._audience_id,
                purpose=_PURPOSE,
                required=_REQUIRED_USES,
                at=moment,
            ) is not None
        )

    @staticmethod
    def _predict(observations, *, target_at: datetime) -> tuple[dict[str, float | int], float, float, float, float]:
        usable = tuple(item for item in observations if item.cpu_percent is not None)
        if len(usable) < 4:
            raise ValueError("at least four CPU observations are required")
        values = [float(item.cpu_percent) for item in usable]
        times = [item.observed_at.astimezone(timezone.utc).timestamp() for item in usable]
        origin = times[-1]
        xs = [value - origin for value in times]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(values) / len(values)
        denominator = sum((value - mean_x) ** 2 for value in xs)
        slope = 0.0 if denominator == 0 else sum(
            (x - mean_x) * (y - mean_y) for x, y in zip(xs, values)
        ) / denominator
        # Bound extrapolation so a damaged cadence cannot create absurd output.
        slope = min(0.5, max(-0.5, slope))
        future_seconds = target_at.timestamp() - origin
        candidate = _bounded(values[-1] + slope * future_seconds)
        ewma = values[0]
        for value in values[1:]:
            ewma = 0.5 * value + 0.5 * ewma
        cadence = [right - left for left, right in zip(times, times[1:])]
        irregularity = 0.0 if not cadence else min(
            1.0, (max(cadence) - min(cadence)) / max(1.0, sum(cadence) / len(cadence)),
        )
        uncertainty = min(1.0, 0.15 + irregularity * 0.5 + 1.0 / len(values))
        features = {
            "cpu_last": values[-1],
            "cpu_ewma": ewma,
            "cpu_slope_per_second": slope,
            "observation_count": len(values),
            "window_seconds": int(times[-1] - times[0]),
        }
        return features, candidate, values[-1], ewma, uncertainty

    def _record_source(self, host_id: str, telemetry) -> str:
        payload = {
            "host_id": host_id,
            "observed_at": telemetry.observed_at.astimezone(timezone.utc).isoformat(),
            "cpu_percent": telemetry.cpu_percent,
            "source_table": "ops_telemetry_history",
        }
        reference = "ml-fleet-source:" + _digest(payload)
        GoalEvidenceLedger(self._guard.path).record(
            evidence_ref=reference, kind="external_observation",
            observed_at=telemetry.observed_at, source="fleet:telemetry",
            successful=None, principal_id=self._principal_id,
            audience=self._audience_id, payload=payload,
        )
        return reference

    def _forecast_host(self, host_id: str, *, at: datetime, grant) -> PressureForecast | None:
        observations = self._ops.history.observations(host_id, through=at, limit=64)
        usable = tuple(item for item in observations if item.cpu_percent is not None)
        if len(usable) < 4:
            return None
        latest = usable[-1]
        age = at - latest.observed_at.astimezone(timezone.utc)
        if age < timedelta(0) or age > self._max_source_age:
            return None
        target = at + self._horizon
        features, candidate, last_value, ewma, uncertainty = self._predict(
            usable, target_at=target,
        )
        source_ref = self._record_source(host_id, latest)
        body = {
            "host_id": host_id, "prediction_at": at.isoformat(),
            "target_at": target.isoformat(), "source_ref": source_ref,
            "source_observed_at": latest.observed_at.astimezone(timezone.utc).isoformat(),
            "features": features, "candidate_digest": _CANDIDATE_DIGEST,
            "candidate_percent": candidate, "last_value_percent": last_value,
            "ewma_percent": ewma, "uncertainty": uncertainty,
            "grant_id": grant.grant_id,
        }
        forecast_id = "ml-fleet-forecast:" + _digest(body)
        mode = self._learning.mode()
        with closing(self._connect()) as db, db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO ml_fleet_pressure_forecast VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    forecast_id, host_id, self._principal_id, self._audience_id,
                    grant.grant_id, at.isoformat(), target.isoformat(), source_ref,
                    body["source_observed_at"], _canonical(features), _CANDIDATE_DIGEST,
                    candidate, last_value, ewma, uncertainty, mode.value, "pending",
                    None, None, None, None, None, None,
                    (at + self._retention).isoformat(),
                ),
            ).rowcount == 1
        prediction = Prediction(
            prediction_id=forecast_id, candidate_digest=_CANDIDATE_DIGEST,
            subject_id=f"host:{host_id}", principal_id=self._principal_id,
            audience_id=self._audience_id, generated_at=at,
            expires_at=target + self._horizon, mode=mode,
            value={
                "cpu_pressure_percent": candidate,
                "last_value_percent": last_value,
                "ewma_percent": ewma,
            },
            uncertainty=uncertainty, reason_refs=(source_ref,),
        )
        self._learning.record_prediction(prediction)
        if not inserted:
            return None
        return PressureForecast(
            forecast_id, host_id, at, target, candidate, last_value, ewma,
            uncertainty, source_ref,
        )

    def _settle(self, *, at: datetime, grant, limit: int = 32) -> tuple[int, int]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT forecast_id,host_id,prediction_at,target_at,source_ref,feature_json,"
                "candidate_percent,last_value_percent,ewma_percent,retention_until "
                "FROM ml_fleet_pressure_forecast WHERE status='pending' AND target_at<=? "
                "AND grant_id=? "
                "ORDER BY target_at,forecast_id LIMIT ?",
                (at.isoformat(), grant.grant_id, limit),
            ).fetchall()
        settled = unknown = 0
        for row in rows:
            forecast_id, host_id = row[0], row[1]
            prediction_at, target_at = datetime.fromisoformat(row[2]), datetime.fromisoformat(row[3])
            candidates = self._ops.history.observations(host_id, through=at, limit=512)
            actual = next((
                item for item in candidates
                if item.observed_at.astimezone(timezone.utc) >= target_at
                and item.cpu_percent is not None
            ), None)
            gap_deadline = target_at + self._horizon * 2
            if actual is None and at < gap_deadline:
                continue
            actual_percent = None if actual is None else float(actual.cpu_percent)
            outcome_payload = {
                "forecast_id": forecast_id, "host_id": host_id,
                "target_at": target_at.isoformat(),
                "actual_observed_at": None if actual is None else actual.observed_at.astimezone(timezone.utc).isoformat(),
                "actual_cpu_percent": actual_percent,
                "coverage": "missing" if actual is None else "observed",
            }
            outcome_ref = "ml-fleet-outcome:" + _digest(outcome_payload)
            observed_at = at if actual is None else actual.observed_at
            GoalEvidenceLedger(self._guard.path).record(
                evidence_ref=outcome_ref, kind="external_observation",
                observed_at=observed_at, source="fleet:pressure-outcome",
                successful=None if actual is None else actual_percent >= 80.0,
                principal_id=self._principal_id, audience=self._audience_id,
                payload=outcome_payload,
            )
            label = (
                OutcomeClass.UNKNOWN if actual is None
                else OutcomeClass.POSITIVE if actual_percent >= 80.0
                else OutcomeClass.NEGATIVE
            )
            sample = GroundedSample(
                sample_id="ml-fleet-sample:" + _digest({"forecast": forecast_id, "outcome": outcome_ref}),
                source_class=SourceClass.FLEET_TELEMETRY,
                source_ref=row[4], outcome_ref=outcome_ref,
                principal_id=self._principal_id, audience_id=self._audience_id,
                subject_id=f"host:{host_id}", group_id=host_id,
                prediction_at=prediction_at, outcome=label,
                features=json.loads(row[5]), retention_until=datetime.fromisoformat(row[9]),
                purpose=_PURPOSE, max_source_age_seconds=int(self._max_source_age.total_seconds()),
            )
            self._learning.admit_sample(sample, grant)
            values = (None, None, None) if actual is None else (
                abs(row[6] - actual_percent), abs(row[7] - actual_percent),
                abs(row[8] - actual_percent),
            )
            with closing(self._connect()) as db, db:
                changed = db.execute(
                    "UPDATE ml_fleet_pressure_forecast SET status=?,outcome_ref=?,actual_percent=?,"
                    "candidate_error=?,last_value_error=?,ewma_error=?,settled_at=? "
                    "WHERE forecast_id=? AND status='pending'",
                    (
                        "unknown" if actual is None else "settled", outcome_ref,
                        actual_percent, *values, at.isoformat(), forecast_id,
                    ),
                )
            if changed.rowcount:
                unknown += int(actual is None)
                settled += int(actual is not None)
        return settled, unknown

    def tick(self, *, at: datetime, busy: bool = False) -> dict[str, int | str] | None:
        moment = _utc(at, "at")
        if type(busy) is not bool:
            raise TypeError("busy must be bool")
        grant = self._learning.active_grant(
            principal_id=self._principal_id, audience_id=self._audience_id,
            purpose=_PURPOSE, required=_REQUIRED_USES, at=moment,
        )
        # This specific unpromoted pilot is shadow-only even if another
        # prediction consumer has separately advanced the global mode.
        if (
            busy or grant is None
            or self._learning.mode() not in {PredictionMode.OBSERVE, PredictionMode.SHADOW}
        ):
            return None
        settled, unknown = self._settle(at=moment, grant=grant)
        created = 0
        resource_created = resource_settled = resource_skipped = resource_errors = 0
        # Fleet registry is authoritative, but one optional tick must remain
        # cheap even when many enrolled workers exist.
        for host in self._ops.fleet()[:32]:
            advisory = self._advisory.observe_host(host, at=moment)
            resource_created += advisory["created"]
            resource_settled += advisory["settled"]
            resource_skipped += advisory["skipped"]
            resource_errors += advisory["errors"]
            if not host.get("trusted") or host.get("lifecycle") not in {"enrolled", "healthy"}:
                continue
            activity = self._ops.activity.state(host["host_id"]).effective
            if activity in {ActivityMode.GAMING, ActivityMode.BUSY, ActivityMode.DO_NOT_DISTURB}:
                continue
            created += int(self._forecast_host(host["host_id"], at=moment, grant=grant) is not None)
        if not any((created, settled, unknown, resource_created, resource_settled,
                    resource_skipped, resource_errors)):
            return None
        return {
            "forecasts_created": created, "outcomes_settled": settled,
            "outcomes_unknown": unknown, "mode": self._learning.mode().value,
            "resource_targets_created": resource_created,
            "resource_targets_settled": resource_settled,
            "resource_targets_skipped": resource_skipped,
            "resource_errors": resource_errors,
        }

    def enforce_retention(self, *, at: datetime, limit: int = 500) -> int:
        moment = _utc(at, "at")
        if type(limit) is not int or not 1 <= limit <= 5000:
            raise ValueError("retention limit must be in [1, 5000]")
        with closing(self._connect()) as db, db:
            rows = db.execute(
                "SELECT f.forecast_id FROM ml_fleet_pressure_forecast f "
                "LEFT JOIN ml_data_use_revocation r ON r.grant_id=f.grant_id "
                "LEFT JOIN ml_source_revocation s ON s.source_ref=f.source_ref "
                "WHERE f.retention_until<=? OR r.grant_id IS NOT NULL OR s.source_ref IS NOT NULL "
                "ORDER BY f.retention_until,f.forecast_id LIMIT ?",
                (moment.isoformat(), limit),
            ).fetchall()
            if rows:
                db.executemany(
                    "DELETE FROM ml_fleet_pressure_forecast WHERE forecast_id=?", rows,
                )
        return len(rows)

    def placement_advisory(self, workload, *, at: datetime) -> dict[str, object] | None:
        """Delegate eligibility to OPS and add a no-authority cost annotation."""
        return self._advisory.placement_advisory(workload, at=at)

    def diagnostics(self, *, limit: int = 50) -> dict[str, object]:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("diagnostic limit must be in [1, 200]")
        with closing(self._connect()) as db:
            totals = dict(db.execute(
                "SELECT status,COUNT(*) FROM ml_fleet_pressure_forecast "
                "WHERE principal_id=? AND audience_id=? GROUP BY status",
                (self._principal_id, self._audience_id),
            ).fetchall())
            rows = db.execute(
                "SELECT forecast_id,host_id,prediction_at,target_at,status,candidate_percent,"
                "last_value_percent,ewma_percent,actual_percent,candidate_error,"
                "last_value_error,ewma_error,mode,outcome_ref "
                "FROM ml_fleet_pressure_forecast WHERE principal_id=? AND audience_id=? "
                "ORDER BY prediction_at DESC,forecast_id LIMIT ?",
                (self._principal_id, self._audience_id, limit),
            ).fetchall()
            metrics = db.execute(
                "SELECT COUNT(*),AVG(candidate_error),AVG(last_value_error),"
                "AVG(ewma_error),SUM(CASE WHEN candidate_error<last_value_error "
                "AND candidate_error<ewma_error THEN 1 ELSE 0 END) "
                "FROM ml_fleet_pressure_forecast WHERE principal_id=? AND audience_id=? "
                "AND status='settled'",
                (self._principal_id, self._audience_id),
            ).fetchone()
        return {
            "algorithm": _ALGORITHM, "candidate_digest": _CANDIDATE_DIGEST,
            "authority": False, "actions_executed": 0,
            "totals": totals,
            "paired_metrics": {
                "settled": metrics[0], "candidate_mae": metrics[1],
                "last_value_mae": metrics[2], "ewma_mae": metrics[3],
                "candidate_wins": metrics[4] or 0,
                "advancement_authorized": False,
            },
            "forecasts": tuple({
                "forecast_id": row[0], "host_id": row[1], "prediction_at": row[2],
                "target_at": row[3], "status": row[4], "candidate_percent": row[5],
                "last_value_percent": row[6], "ewma_percent": row[7],
                "actual_percent": row[8], "candidate_error": row[9],
                "last_value_error": row[10], "ewma_error": row[11],
                "mode": row[12], "outcome_ref": row[13],
            } for row in rows),
            "resource_advisory": self._advisory.diagnostics(),
        }
