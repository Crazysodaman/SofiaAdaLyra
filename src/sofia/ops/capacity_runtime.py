"""CA-6109: authorized local-storage pressure observation in existing PRESENCE.

This is a diagnostic projection, not an execution authority or a claim that
the task's workload-derived/multi-host acceptance criteria have been met.
The caller is the existing STOP-gated background coordinator, never a new
polling thread or SQLite writer.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil

from sofia.application.presence import WorldAvailability, WorldEpistemicState
from sofia.ops.capacity import (
    CapacityBudget, CapacityError, DEFAULT_BUDGETS, Level,
    assess_capacity,
)
from sofia.ops.capacity_probe import measure_storage

_CANONICAL_BUDGET = next(
    budget for budget in DEFAULT_BUDGETS
    if budget.resource == "canonical_db_bytes"
)
_RANK = {Level.NORMAL: 0, Level.WARN: 1, Level.DEGRADED: 2, Level.STOP: 3}


def _disk_level(*, free: int, total: int) -> Level:
    """Provisional absolute and relative free-space triggers, NOT learned SLOs."""
    if type(free) is not int or type(total) is not int or total <= 0 or not 0 <= free <= total:
        raise CapacityError("invalid observed filesystem capacity")
    # Critical disk conditions stop *advisory capacity acceptance*, not RUN.
    if free <= (1 << 30) or free * 100 <= total * 2:
        return Level.STOP
    if free <= (2 << 30) or free * 100 <= total * 5:
        return Level.DEGRADED
    if free <= (4 << 30) or free * 100 <= total * 10:
        return Level.WARN
    return Level.NORMAL


def record_local_capacity(
    *,
    state_path: Path | str,
    presence,
    now: datetime,
    read_storage=measure_storage,
    disk_usage=shutil.disk_usage,
):
    """Persist one scoped observation via the existing canonical PRESENCE owner.

    Never rewrites state, deletes files, sheds services, grants authorization
    or implies that all other resources are within budget. Exceptions are
    deliberately visible to the existing RUN scheduler's failure receipts.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise CapacityError("capacity observation timestamp must be timezone-aware")
    path = Path(state_path)
    readings = tuple(read_storage(path))
    measurement = next(
        (item for item in readings if item.resource == "canonical_db_bytes"), None
    )
    if measurement is None or sum(
        item.resource == "canonical_db_bytes" for item in readings
    ) != 1:
        raise CapacityError("canonical database measurement missing or duplicated")
    # Deliberately evaluate only the resource actually observed. Unmeasured
    # CPU, archive, backup and latency are not silently called healthy.
    assessed = assess_capacity((_CANONICAL_BUDGET,), (measurement,))
    filesystem = disk_usage(path.absolute().parent)
    space_level = _disk_level(free=filesystem.free, total=filesystem.total)
    db_level = assessed.verdict_for("canonical_db_bytes").level
    overall = max((db_level, space_level), key=lambda level: _RANK[level])
    instant = now.astimezone(timezone.utc)
    stamp = instant.strftime("%Y%m%dT%H%M%S%f")
    return presence.record_state(
        observation_id="world:storage:" + stamp,
        subject_id="runtime:local_storage",
        predicate="storage.capacity",
        source_id="ops:capacity_probe",
        observed_at=instant,
        audience_id=None,  # system-only storage diagnostic; no private content
        freshness=timedelta(minutes=15),
        confidence=1.0,
        epistemic_state=WorldEpistemicState.OBSERVED,
        availability=(
            WorldAvailability.DEGRADED
            if overall in (Level.DEGRADED, Level.STOP)
            else WorldAvailability.HEALTHY
        ),
        value={
            "canonical_db_bytes": measurement.used,
            "filesystem_free_bytes": filesystem.free,
            "filesystem_total_bytes": filesystem.total,
            "db_budget_level": db_level.value,
            "filesystem_pressure_level": space_level.value,
            "overall_advisory_level": overall.value,
            "thresholds": "provisional-not-workload-calibrated",
            "unmeasured": [
                budget.resource for budget in DEFAULT_BUDGETS
                if budget.resource != "canonical_db_bytes"
            ],
            "action_taken": False,
            "acceptance_verified": False,
        },
    )
