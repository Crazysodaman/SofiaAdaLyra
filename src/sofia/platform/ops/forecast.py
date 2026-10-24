"""Deterministic, advisory Fleet pressure forecasting baseline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class ForecastAdvice(str, Enum):
    STAY = "stay"
    DEFER = "defer"
    THROTTLE = "throttle"
    MOVE = "move"


@dataclass(frozen=True, slots=True)
class FleetPressureSample:
    host_id: str
    observed_at: datetime
    # Normalized parts per thousand. Unknown stays None and never becomes zero.
    cpu: int | None
    ram: int | None
    gpu: int | None
    vram: int | None
    storage_io: int | None
    network: int | None
    workload_demand: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.host_id, str) or not self.host_id.strip():
            raise ValueError("host_id required")
        if (not isinstance(self.observed_at, datetime)
                or self.observed_at.tzinfo is None
                or self.observed_at.utcoffset() is None):
            raise ValueError("observed_at must be timezone-aware")
        for field in ("cpu", "ram", "gpu", "vram", "storage_io", "network",
                      "workload_demand"):
            value = getattr(self, field)
            if value is not None and (type(value) is not int or not 0 <= value <= 1000):
                raise ValueError(f"{field} must be 0..1000 or None")


@dataclass(frozen=True, slots=True)
class PressureProjection:
    resource: str
    observed: int | None
    projected: int | None
    delta: int | None


@dataclass(frozen=True, slots=True)
class FleetForecast:
    host_id: str
    generated_at: datetime
    horizon: timedelta
    advice: ForecastAdvice
    projections: tuple[PressureProjection, ...]
    reasons: tuple[str, ...]
    authoritative: bool = False


def deterministic_fleet_forecast(
    samples: tuple[FleetPressureSample, ...], *, now: datetime,
    horizon: timedelta = timedelta(minutes=5),
    max_sample_age: timedelta = timedelta(minutes=2),
) -> FleetForecast:
    """Project a bounded linear trend; this advice never admits a workload."""
    if type(samples) is not tuple or len(samples) < 2:
        raise ValueError("at least two pressure samples are required")
    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None):
        raise ValueError("now must be timezone-aware")
    if not isinstance(horizon, timedelta) or not timedelta(seconds=1) <= horizon <= timedelta(hours=1):
        raise ValueError("forecast horizon must be in 1 second..1 hour")
    if not isinstance(max_sample_age, timedelta) or max_sample_age <= timedelta(0):
        raise ValueError("max_sample_age must be positive")
    ordered = tuple(sorted(samples, key=lambda item: item.observed_at))
    host_id = ordered[0].host_id
    if any(item.host_id != host_id for item in ordered):
        raise ValueError("forecast samples must belong to one host")
    if len({item.observed_at for item in ordered}) != len(ordered):
        raise ValueError("forecast sample timestamps must be unique")
    moment = now.astimezone(timezone.utc)
    newest = ordered[-1].observed_at.astimezone(timezone.utc)
    age = moment - newest
    if age < -timedelta(seconds=5) or age > max_sample_age:
        raise RuntimeError("latest pressure sample is stale or from the future")
    elapsed = (newest - ordered[0].observed_at.astimezone(timezone.utc)).total_seconds()
    if elapsed <= 0:
        raise ValueError("forecast sample window must advance")
    resources = ("cpu", "ram", "gpu", "vram", "storage_io", "network",
                 "workload_demand")
    projections: list[PressureProjection] = []
    reasons: list[str] = []
    known: list[int] = []
    for resource in resources:
        first = getattr(ordered[0], resource)
        current = getattr(ordered[-1], resource)
        if first is None or current is None:
            projections.append(PressureProjection(resource, current, None, None))
            reasons.append(f"{resource} pressure is unobserved")
            continue
        projected = max(0, min(1000, round(
            current + (current - first) / elapsed * horizon.total_seconds()
        )))
        projections.append(PressureProjection(
            resource, current, projected, projected - current,
        ))
        known.append(projected)
    if not known:
        advice = ForecastAdvice.DEFER
        reasons.append("no measured pressure supports placement")
    else:
        peak = max(known)
        if peak >= 950:
            advice = ForecastAdvice.MOVE
        elif peak >= 850:
            advice = ForecastAdvice.THROTTLE
        elif peak >= 700:
            advice = ForecastAdvice.DEFER
        else:
            advice = ForecastAdvice.STAY
        reasons.append(f"deterministic projected peak is {peak}/1000")
    return FleetForecast(
        host_id, moment, horizon, advice, tuple(projections), tuple(reasons), False,
    )
