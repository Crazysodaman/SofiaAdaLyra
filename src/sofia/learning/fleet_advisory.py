"""Bounded multi-resource Fleet prediction and anomaly advice (ML-011..014).

This module is a subordinate of :class:`FleetPressurePilot`.  It writes
diagnostic projections only.  OPS remains the sole placement/policy owner and
no record in these tables grants enrollment, execution, or scheduling rights.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
import sqlite3

from sofia.ops.activity import ActivityMode
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


_HORIZONS = (5, 15, 30)
_RESOURCES = ("cpu", "ram", "gpu", "vram")
_THRESHOLDS = {"cpu": 90.0, "ram": 92.0, "gpu": 95.0, "vram": 92.0}


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("advisory clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _value(item, resource: str) -> float | None:
    if resource == "cpu":
        return None if item.cpu_percent is None else float(item.cpu_percent)
    if resource == "gpu":
        return None if item.gpu_percent is None else float(item.gpu_percent)
    used = item.ram_used_bytes if resource == "ram" else item.vram_used_bytes
    total = item.ram_total_bytes if resource == "ram" else item.vram_total_bytes
    if used is None or total is None or total <= 0 or used > total:
        return None
    return 100.0 * float(used) / float(total)


class FleetAdvisoryEngine:
    """Durable no-authority resource targets and advisory health metrics."""

    def __init__(self, state_path: str | Path, *, ops_service) -> None:
        self._guard = CanonicalSQLiteGuard(Path(state_path))
        self._ops = ops_service
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS ml_fleet_resource_target(
                    target_id TEXT PRIMARY KEY,
                    host_id TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    horizon_minutes INTEGER NOT NULL,
                    generated_at TEXT NOT NULL,
                    source_observed_at TEXT NOT NULL,
                    predicted_percent REAL NOT NULL,
                    uncertainty REAL NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','settled','unknown')),
                    actual_percent REAL,
                    absolute_error REAL,
                    outcome_observed_at TEXT,
                    UNIQUE(host_id,resource,horizon_minutes,source_observed_at)
                );
                CREATE INDEX IF NOT EXISTS idx_ml_resource_target_pending
                ON ml_fleet_resource_target(status,generated_at);
                CREATE TABLE IF NOT EXISTS ml_fleet_advisory_event(
                    event_id TEXT PRIMARY KEY,
                    host_id TEXT NOT NULL,
                    event_kind TEXT NOT NULL,
                    resource TEXT,
                    observed_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    disposition TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ml_fleet_advisory_health(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    advisory_enabled INTEGER NOT NULL,
                    disabled_reason TEXT,
                    updated_at TEXT NOT NULL,
                    tick_count INTEGER NOT NULL,
                    error_count INTEGER NOT NULL,
                    skipped_count INTEGER NOT NULL,
                    runtime_ms_total REAL NOT NULL
                );
                INSERT OR IGNORE INTO ml_fleet_advisory_health VALUES(1,1,NULL,'1970-01-01T00:00:00+00:00',0,0,0,0.0);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return self._guard.connect(timeout=10)

    def _event(
        self, *, host_id: str, kind: str, at: datetime, reason: str,
        resource: str | None = None, details: dict | None = None,
        disposition: str = "observed",
    ) -> int:
        body = {
            "host_id": host_id, "kind": kind, "at": at.isoformat(),
            "reason": reason, "resource": resource, "details": details or {},
            "disposition": disposition,
        }
        with closing(self._connect()) as db, db:
            return db.execute(
                "INSERT OR IGNORE INTO ml_fleet_advisory_event VALUES(?,?,?,?,?,?,?,?)",
                ("ml-fleet-event:" + _digest(body), host_id, kind, resource,
                 at.isoformat(), reason, json.dumps(details or {}, sort_keys=True), disposition),
            ).rowcount

    @staticmethod
    def _predict(points: list[tuple[datetime, float]], horizon: int) -> tuple[float, float]:
        values = [value for _, value in points]
        seconds = [(when - points[-1][0]).total_seconds() for when, _ in points]
        mean_x = sum(seconds) / len(seconds)
        mean_y = sum(values) / len(values)
        denominator = sum((x - mean_x) ** 2 for x in seconds)
        slope = 0.0 if denominator == 0 else sum(
            (x - mean_x) * (y - mean_y) for x, y in zip(seconds, values)
        ) / denominator
        slope = min(0.25, max(-0.25, slope))
        predicted = min(100.0, max(0.0, values[-1] + slope * horizon * 60.0))
        spread = max(values) - min(values)
        uncertainty = min(1.0, 0.1 + spread / 100.0 + 1.0 / len(values))
        return predicted, uncertainty

    def _settle(self, *, host_id: str, at: datetime) -> int:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT target_id,resource,generated_at,horizon_minutes,predicted_percent "
                "FROM ml_fleet_resource_target WHERE host_id=? AND status='pending' "
                "ORDER BY generated_at,target_id LIMIT 256", (host_id,),
            ).fetchall()
        observations = self._ops.history.observations(host_id, through=at, limit=512)
        changed = 0
        for target_id, resource, generated_raw, horizon, predicted in rows:
            due = datetime.fromisoformat(generated_raw) + timedelta(minutes=horizon)
            actual = next((item for item in observations if item.observed_at >= due and _value(item, resource) is not None), None)
            if actual is None and at < due + timedelta(minutes=max(10, horizon)):
                continue
            actual_value = None if actual is None else _value(actual, resource)
            status = "unknown" if actual_value is None else "settled"
            with closing(self._connect()) as db, db:
                updated = db.execute(
                    "UPDATE ml_fleet_resource_target SET status=?,actual_percent=?,absolute_error=?,outcome_observed_at=? "
                    "WHERE target_id=? AND status='pending'",
                    (status, actual_value, None if actual_value is None else abs(predicted - actual_value),
                     None if actual is None else actual.observed_at.isoformat(), target_id),
                ).rowcount
                quality = db.execute(
                    "SELECT COUNT(*),AVG(absolute_error) FROM ("
                    "SELECT absolute_error FROM ml_fleet_resource_target "
                    "WHERE status='settled' ORDER BY outcome_observed_at DESC LIMIT 20)"
                ).fetchone()
                if quality[0] >= 8 and quality[1] is not None and quality[1] > 25.0:
                    db.execute(
                        "UPDATE ml_fleet_advisory_health SET advisory_enabled=0,disabled_reason=?,updated_at=? WHERE singleton=1",
                        ("recent forecast error regressed above 25 points; deterministic OPS remains active", at.isoformat()),
                    )
            changed += updated
            if actual_value is not None and predicted >= _THRESHOLDS[resource] and actual_value < _THRESHOLDS[resource]:
                self._event(host_id=host_id, kind="anomaly_outcome", resource=resource, at=at,
                            reason="forecast threshold alert was a false alarm",
                            details={"predicted": predicted, "actual": actual_value}, disposition="false_alarm")
        return changed

    def observe_host(self, host: dict, *, at: datetime) -> dict[str, int]:
        moment = _utc(at)
        host_id = str(host.get("host_id", ""))
        started = perf_counter()
        created = settled = skipped = errors = 0
        try:
            if not host_id or not host.get("trusted") or host.get("lifecycle") not in {"enrolled", "healthy"}:
                skipped = self._event(host_id=host_id or "unknown", kind="skipped", at=moment,
                                      reason="device is unknown, untrusted, or not enrolled")
                return {"created": 0, "settled": 0, "skipped": skipped, "errors": 0}
            activity = self._ops.activity.state(host_id).effective
            if activity in {ActivityMode.GAMING, ActivityMode.BUSY, ActivityMode.DO_NOT_DISTURB}:
                skipped = self._event(host_id=host_id, kind="skipped", at=moment, reason=f"foreground activity: {activity.value}")
                return {"created": 0, "settled": 0, "skipped": skipped, "errors": 0}
            ingested = self._ops.history.ingestion_window(host_id, through=moment, limit=64)
            stamps = [item.observed_at.astimezone(timezone.utc) for item in ingested]
            if any(right <= left for left, right in zip(stamps, stamps[1:])):
                skipped = self._event(host_id=host_id, kind="skipped", at=moment, reason="out-of-order or duplicate source timestamps")
                return {"created": 0, "settled": 0, "skipped": skipped, "errors": 0}
            settled = self._settle(host_id=host_id, at=moment)
            for resource in _RESOURCES:
                points = [(item.observed_at.astimezone(timezone.utc), value) for item in ingested
                          if (value := _value(item, resource)) is not None]
                if len(points) < 4:
                    skipped += self._event(host_id=host_id, kind="skipped", resource=resource, at=moment,
                                           reason="insufficient authentic samples", details={"count": len(points)})
                    continue
                if moment - points[-1][0] > timedelta(minutes=10) or any(
                    right[0] - left[0] > timedelta(minutes=10) for left, right in zip(points, points[1:])
                ):
                    skipped += self._event(host_id=host_id, kind="skipped", resource=resource, at=moment,
                                           reason="telemetry gap or stale source")
                    continue
                for horizon in _HORIZONS:
                    predicted, uncertainty = self._predict(points, horizon)
                    body = {"host": host_id, "resource": resource, "horizon": horizon,
                            "source": points[-1][0].isoformat()}
                    with closing(self._connect()) as db, db:
                        made = db.execute(
                            "INSERT OR IGNORE INTO ml_fleet_resource_target VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            ("ml-resource-target:" + _digest(body), host_id, resource, horizon,
                             moment.isoformat(), points[-1][0].isoformat(), predicted,
                             uncertainty, "pending", None, None, None),
                        ).rowcount
                    created += made
                    if made and predicted >= _THRESHOLDS[resource]:
                        self._event(host_id=host_id, kind="anomaly_candidate", resource=resource, at=moment,
                                    reason="bounded trend exceeds fixed operational threshold",
                                    details={"predicted": predicted, "threshold": _THRESHOLDS[resource],
                                             "horizon_minutes": horizon, "uncertainty": uncertainty})
        except Exception as exc:
            errors = 1
            self._event(host_id=host_id or "unknown", kind="error", at=moment,
                        reason=type(exc).__name__, details={"message": str(exc)[:240]})
        finally:
            elapsed = (perf_counter() - started) * 1000.0
            with closing(self._connect()) as db, db:
                db.execute(
                    "UPDATE ml_fleet_advisory_health SET updated_at=?,tick_count=tick_count+1,"
                    "error_count=error_count+?,skipped_count=skipped_count+?,"
                    "runtime_ms_total=runtime_ms_total+? WHERE singleton=1",
                    (moment.isoformat(), errors, skipped, elapsed),
                )
                row = db.execute("SELECT tick_count,error_count FROM ml_fleet_advisory_health WHERE singleton=1").fetchone()
                if row[0] >= 5 and row[1] / row[0] > 0.2:
                    db.execute(
                        "UPDATE ml_fleet_advisory_health SET advisory_enabled=0,disabled_reason=?,updated_at=? WHERE singleton=1",
                        ("prediction error rate exceeded 20%; deterministic OPS remains active", moment.isoformat()),
                    )
        return {"created": created, "settled": settled, "skipped": skipped, "errors": errors}

    def diagnostics(self) -> dict[str, object]:
        with closing(self._connect()) as db:
            health = db.execute("SELECT * FROM ml_fleet_advisory_health WHERE singleton=1").fetchone()
            counts = dict(db.execute("SELECT status,COUNT(*) FROM ml_fleet_resource_target GROUP BY status").fetchall())
            metrics = db.execute(
                "SELECT COUNT(*),AVG(absolute_error) FROM ml_fleet_resource_target WHERE status='settled'"
            ).fetchone()
            recent = db.execute(
                "SELECT AVG(absolute_error) FROM (SELECT absolute_error FROM ml_fleet_resource_target "
                "WHERE status='settled' ORDER BY outcome_observed_at DESC LIMIT 20)"
            ).fetchone()[0]
            prior = db.execute(
                "SELECT AVG(absolute_error) FROM (SELECT absolute_error FROM ml_fleet_resource_target "
                "WHERE status='settled' ORDER BY outcome_observed_at DESC LIMIT 20 OFFSET 20)"
            ).fetchone()[0]
            events = db.execute(
                "SELECT event_kind,COUNT(*) FROM ml_fleet_advisory_event GROUP BY event_kind"
            ).fetchall()
        return {
            "authority": False, "actions_executed": 0,
            "advisory_enabled": bool(health[1]), "disabled_reason": health[2],
            "tick_count": health[4], "error_count": health[5], "skipped_count": health[6],
            "runtime_ms_total": health[7], "targets": counts,
            "settled_count": metrics[0], "mean_absolute_error": metrics[1],
            "recent_mae": recent, "prior_mae": prior,
            "drift_mae_delta": None if recent is None or prior is None else recent - prior,
            "events": dict(events), "resources": _RESOURCES, "horizons_minutes": _HORIZONS,
            "deterministic_ops_preserved": True,
        }

    def placement_advisory(self, workload, *, at: datetime) -> dict[str, object] | None:
        """Annotate an OPS-owned placement decision; never select independently.

        The enrolled node UUID is the local evidence that the Fleet registry's
        host has completed its pinned-mTLS enrollment.  Missing identity,
        stale capacity, or foreground activity is left to OPS' existing
        deterministic eligibility policy and cannot be repaired by a score.
        """
        moment = _utc(at)
        with closing(self._connect()) as db:
            health = db.execute(
                "SELECT advisory_enabled FROM ml_fleet_advisory_health WHERE singleton=1"
            ).fetchone()
        if not health or not health[0]:
            return None
        registry = getattr(self._ops, "registry", None)
        placement = getattr(self._ops, "placement", None)
        activity_store = getattr(self._ops, "activity", None)
        if registry is None or placement is None or activity_store is None:
            return None
        hosts = tuple(registry.hosts())
        activities = {host.host_id: activity_store.state(host.host_id) for host in hosts}
        decision = placement.choose(workload, hosts, activities=activities, now=moment)
        if decision.host_id is None:
            return {
                "workload_id": decision.workload_id, "suggested_host_id": None,
                "reason": "OPS policy found no eligible host", "authority": False,
                "ops_rejected": decision.rejected,
            }
        selected = next(host for host in hosts if host.host_id == decision.host_id)
        if selected.node_id is None:
            self._event(host_id=selected.host_id, kind="placement_skipped", at=moment,
                        reason="enrolled mTLS node identity is absent")
            return None
        state = activities[selected.host_id]
        if state.effective in {ActivityMode.GAMING, ActivityMode.BUSY, ActivityMode.DO_NOT_DISTURB}:
            self._event(host_id=selected.host_id, kind="placement_skipped", at=moment,
                        reason=f"foreground activity: {state.effective.value}")
            return None
        with closing(self._connect()) as db:
            targets = db.execute(
                "SELECT resource,predicted_percent,uncertainty,source_observed_at "
                "FROM ml_fleet_resource_target WHERE host_id=? AND horizon_minutes=5 "
                "AND status='pending' ORDER BY generated_at DESC,target_id LIMIT 4",
                (selected.host_id,),
            ).fetchall()
        if not targets or any(
            moment - datetime.fromisoformat(row[3]).astimezone(timezone.utc) > timedelta(minutes=10)
            for row in targets
        ):
            self._event(host_id=selected.host_id, kind="placement_skipped", at=moment,
                        reason="fresh predicted capacity is unavailable")
            return None
        return {
            "workload_id": decision.workload_id,
            "suggested_host_id": decision.host_id,
            "eligible_hosts": decision.eligible_hosts,
            "ops_rejected": decision.rejected,
            "predicted_cost": {row[0]: row[1] for row in targets},
            "max_uncertainty": max(row[2] for row in targets),
            "reason": "annotation of existing OPS policy decision",
            "authority": False,
            "can_enroll": False,
            "can_move_workload": False,
        }
