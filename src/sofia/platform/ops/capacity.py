"""Capacity budgets, degraded modes and pre-exhaustion triggers (V18 CA-6109).

The original requirement asks for capacity budgets and triggers derived from the
actual workload for text, audio, avatar assets, project artifacts, index
rebuilds, SSD writes, CPU/RAM, encryption latency, storage growth, backup costs
and retention -- and for degraded modes and alerts that fire *before* disks fill
or archived segments become unreadable.

This module is a pure evaluator. It never measures the host and never changes
runtime state; a caller supplies observed readings and receives a bounded
assessment with explicit triggers. An observed resource with no declared budget
fails closed to ``WARN`` rather than being silently ignored.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

_RESOURCE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class Level(str, Enum):
    NORMAL = "normal"
    WARN = "warn"
    DEGRADED = "degraded"
    STOP = "stop"


_ORDER = {Level.NORMAL: 0, Level.WARN: 1, Level.DEGRADED: 2, Level.STOP: 3}


class CapacityError(ValueError):
    """Raised when a budget or reading is not admissible."""


@dataclass(frozen=True, slots=True)
class CapacityBudget:
    """Declared ceiling and warning thresholds for one measured resource.

    Thresholds are inclusive lower bounds on ``used``: ``used >= stop_limit``
    means stop, and so on. ``None`` disables a threshold.
    """

    resource: str
    warn_at: int
    degrade_at: int
    stop_at: int

    def __post_init__(self) -> None:
        if not isinstance(self.resource, str) or _RESOURCE.fullmatch(
            self.resource
        ) is None:
            raise CapacityError("resource must be a bounded lowercase identifier")
        for name, value in (
            ("warn_at", self.warn_at),
            ("degrade_at", self.degrade_at),
            ("stop_at", self.stop_at),
        ):
            if type(value) is not int or value <= 0:
                raise CapacityError(f"{name} must be a positive integer")
        if not self.warn_at <= self.degrade_at <= self.stop_at:
            raise CapacityError(
                "thresholds must be ordered warn_at <= degrade_at <= stop_at"
            )

    def level_for(self, used: int) -> Level:
        if type(used) is not int or used < 0:
            raise CapacityError("used must be a non-negative integer")
        if used >= self.stop_at:
            return Level.STOP
        if used >= self.degrade_at:
            return Level.DEGRADED
        if used >= self.warn_at:
            return Level.WARN
        return Level.NORMAL


@dataclass(frozen=True, slots=True)
class Reading:
    resource: str
    used: int

    def __post_init__(self) -> None:
        if not isinstance(self.resource, str) or _RESOURCE.fullmatch(
            self.resource
        ) is None:
            raise CapacityError("reading resource must be a bounded identifier")
        if type(self.used) is not int or self.used < 0:
            raise CapacityError("reading used must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ResourceVerdict:
    resource: str
    used: int | None
    level: Level
    budgeted: bool
    trigger: str | None


@dataclass(frozen=True, slots=True)
class CapacityAssessment:
    overall: Level
    verdicts: tuple[ResourceVerdict, ...]
    alerts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.overall, Level):
            raise TypeError("overall must be Level")
        if not isinstance(self.verdicts, tuple) or not self.verdicts:
            raise CapacityError("assessment requires at least one verdict")
        if not isinstance(self.alerts, tuple):
            raise TypeError("alerts must be a tuple")

    def verdict_for(self, resource: str) -> ResourceVerdict | None:
        for verdict in self.verdicts:
            if verdict.resource == resource:
                return verdict
        return None


def assess_capacity(
    budgets: "tuple[CapacityBudget, ...] | list[CapacityBudget]",
    readings: "tuple[Reading, ...] | list[Reading]",
) -> CapacityAssessment:
    """Evaluate observed readings against declared budgets, fail closed.

    A reading without a budget *or a budget without a reading* is reported
    at ``WARN`` with an explicit trigger. An unmeasured resource must never
    silently count as normal; missing values have ``used=None``.
    ``STOP`` means the runtime must shed load before writing more.
    """
    if not isinstance(budgets, (tuple, list)) or not budgets:
        raise CapacityError("at least one capacity budget is required")
    if not isinstance(readings, (tuple, list)) or not readings:
        raise CapacityError("at least one reading is required")
    by_resource: dict[str, CapacityBudget] = {}
    for budget in budgets:
        if not isinstance(budget, CapacityBudget):
            raise TypeError("budgets must be CapacityBudget")
        if budget.resource in by_resource:
            raise CapacityError(f"duplicate budget for {budget.resource}")
        by_resource[budget.resource] = budget

    verdicts: list[ResourceVerdict] = []
    alerts: list[str] = []
    overall = Level.NORMAL
    seen: set[str] = set()
    for reading in readings:
        if not isinstance(reading, Reading):
            raise TypeError("readings must be Reading")
        if reading.resource in seen:
            raise CapacityError(f"duplicate reading for {reading.resource}")
        seen.add(reading.resource)
        budget = by_resource.get(reading.resource)
        if budget is None:
            level = Level.WARN
            trigger = f"unbudgeted resource observed: {reading.resource}"
            budgeted = False
        else:
            level = budget.level_for(reading.used)
            budgeted = True
            trigger = None
            if level is not Level.NORMAL:
                trigger = (
                    f"{reading.resource}={reading.used} reached "
                    f"{level.value} threshold"
                )
        if _ORDER[level] > _ORDER[overall]:
            overall = level
        if trigger is not None:
            alerts.append(trigger)
        verdicts.append(ResourceVerdict(
            resource=reading.resource, used=reading.used, level=level,
            budgeted=budgeted, trigger=trigger,
        ))
    # Distinguish zero observed usage from *no measurement*. Previously
    # omitting a high-risk budget from readings could yield a false NORMAL.
    for resource in by_resource:
        if resource in seen:
            continue
        missing_trigger = f"budgeted resource unobserved: {resource}"
        alerts.append(missing_trigger)
        verdicts.append(ResourceVerdict(
            resource=resource, used=None, level=Level.WARN,
            budgeted=True, trigger=missing_trigger,
        ))
        if _ORDER[Level.WARN] > _ORDER[overall]:
            overall = Level.WARN
    return CapacityAssessment(
        overall=overall, verdicts=tuple(verdicts), alerts=tuple(alerts),
    )


# Default starting budgets for the host measured in the V18 baseline. These are
# declared ceilings to be re-derived from observed workload, not evidence that
# live usage is within them.
DEFAULT_BUDGETS: tuple[CapacityBudget, ...] = (
    CapacityBudget("canonical_db_bytes", warn_at=4 << 30, degrade_at=8 << 30,
                   stop_at=16 << 30),
    CapacityBudget("archive_bytes", warn_at=64 << 30, degrade_at=192 << 30,
                   stop_at=384 << 30),
    CapacityBudget("backup_bytes", warn_at=64 << 30, degrade_at=192 << 30,
                   stop_at=384 << 30),
    CapacityBudget("media_asset_bytes", warn_at=32 << 30, degrade_at=96 << 30,
                   stop_at=192 << 30),
    CapacityBudget("process_rss_bytes", warn_at=4 << 30, degrade_at=8 << 30,
                   stop_at=12 << 30),
    CapacityBudget("cpu_sustained_millicores", warn_at=7000, degrade_at=10000,
                   stop_at=13000),
    CapacityBudget("encrypt_latency_p95_ms", warn_at=250, degrade_at=1000,
                   stop_at=3000),
)
