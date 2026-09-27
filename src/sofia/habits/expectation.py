"""Expectation creation/evaluation for established recurring habits."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from zoneinfo import ZoneInfo

from .model import (
    CoverageState,
    ExpectationStatus,
    HabitCadence,
    HabitExpectation,
    HabitPattern,
    HabitStatus,
)
from .store import HabitStore


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return value


def _expectation_id(habit_id: str, start: datetime) -> str:
    raw = f"{habit_id}\x1f{start.astimezone(timezone.utc).isoformat()}"
    return "habit-exp:" + sha256(raw.encode("utf-8")).hexdigest()[:32]


def _bucket_hour(raw: str) -> int:
    bucket = int(raw)
    if not 0 <= bucket <= 11:
        raise ValueError("stored hour bucket context is invalid")
    return bucket * 2


def _valid_local_window(
    *,
    day: date,
    hour: int,
    zone: ZoneInfo,
) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, hour, 0, tzinfo=zone)
    end = start + timedelta(hours=2)
    return start, end


def _next_daily(
    pattern: HabitPattern,
    *,
    local_now: datetime,
    zone: ZoneInfo,
) -> tuple[datetime, datetime]:
    assert pattern.context_value is not None
    hour = _bucket_hour(pattern.context_value)
    for offset in range(0, 2):
        start, end = _valid_local_window(
            day=(local_now + timedelta(days=offset)).date(),
            hour=hour,
            zone=zone,
        )
        if end > local_now:
            return start, end
    raise RuntimeError("unable to resolve daily expectation window")


def _next_weekly(
    pattern: HabitPattern,
    *,
    local_now: datetime,
    zone: ZoneInfo,
) -> tuple[datetime, datetime]:
    assert pattern.context_value is not None
    weekday_raw, bucket_raw = pattern.context_value.split("|", 1)
    weekday = int(weekday_raw)
    if not 0 <= weekday <= 6:
        raise ValueError("stored weekday context is invalid")
    hour = _bucket_hour(bucket_raw)
    for offset in range(0, 8):
        day = (local_now + timedelta(days=offset)).date()
        if day.weekday() != weekday:
            continue
        start, end = _valid_local_window(day=day, hour=hour, zone=zone)
        if end > local_now:
            return start, end
    raise RuntimeError("unable to resolve weekly expectation window")


def _month_sequence(year: int, month: int):
    for offset in range(0, 15):
        absolute = year * 12 + (month - 1) + offset
        yield absolute // 12, (absolute % 12) + 1


def _next_monthly(
    pattern: HabitPattern,
    *,
    local_now: datetime,
    zone: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    assert pattern.context_value is not None
    day_raw, bucket_raw = pattern.context_value.split("|", 1)
    desired_day = int(day_raw)
    if not 1 <= desired_day <= 31:
        raise ValueError("stored day-of-month context is invalid")
    hour = _bucket_hour(bucket_raw)
    for year, month in _month_sequence(local_now.year, local_now.month):
        last_day = calendar.monthrange(year, month)[1]
        if desired_day > last_day:
            continue
        day = date(year, month, desired_day)
        start, end = _valid_local_window(day=day, hour=hour, zone=zone)
        if end > local_now:
            return start, end
    return None


def _next_yearly(
    pattern: HabitPattern,
    *,
    local_now: datetime,
    zone: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    assert pattern.context_value is not None
    month_day, bucket_raw = pattern.context_value.split("|", 1)
    month_raw, day_raw = month_day.split("-", 1)
    month = int(month_raw)
    day_number = int(day_raw)
    if not 1 <= month <= 12 or not 1 <= day_number <= 31:
        raise ValueError("stored month-day context is invalid")
    hour = _bucket_hour(bucket_raw)
    for year in range(local_now.year, local_now.year + 9):
        try:
            day = date(year, month, day_number)
        except ValueError:
            continue
        start, end = _valid_local_window(day=day, hour=hour, zone=zone)
        if end > local_now:
            return start, end
    return None


def _next_window(
    pattern: HabitPattern,
    *,
    now: datetime,
    timezone_name: str,
) -> tuple[datetime, datetime] | None:
    zone = ZoneInfo(timezone_name)
    local_now = _aware(now).astimezone(zone)
    window: tuple[datetime, datetime] | None
    if (
        pattern.cadence is HabitCadence.DAILY
        and pattern.context_key == "daily_window"
    ):
        window = _next_daily(pattern, local_now=local_now, zone=zone)
    elif (
        pattern.cadence is HabitCadence.WEEKLY
        and pattern.context_key == "weekly_window"
    ):
        window = _next_weekly(pattern, local_now=local_now, zone=zone)
    elif (
        pattern.cadence is HabitCadence.MONTHLY
        and pattern.context_key == "monthly_window"
    ):
        window = _next_monthly(pattern, local_now=local_now, zone=zone)
    elif (
        pattern.cadence is HabitCadence.YEARLY
        and pattern.context_key == "yearly_window"
    ):
        window = _next_yearly(pattern, local_now=local_now, zone=zone)
    else:
        return None
    if window is None:
        return None
    start, end = window
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


class HabitExpectationEngine:
    """Create bounded expectations and resolve them from evidence coverage."""

    def __init__(self, store: HabitStore) -> None:
        if not isinstance(store, HabitStore):
            raise TypeError("store must be HabitStore")
        self.store = store

    def ensure_time_expectations(
        self,
        *,
        principal_id: str,
        timezone_name: str | None,
        now: datetime,
    ) -> tuple[HabitExpectation, ...]:
        moment = _aware(now).astimezone(timezone.utc)
        if timezone_name is None:
            return ()
        try:
            ZoneInfo(timezone_name)
        except Exception as exc:
            raise ValueError("invalid habit timezone") from exc

        created: list[HabitExpectation] = []
        patterns = self.store.patterns(
            principal_id=principal_id,
            statuses=(HabitStatus.ESTABLISHED, HabitStatus.TRUSTED),
        )
        for pattern in patterns:
            if pattern.cadence is HabitCadence.IRREGULAR:
                continue
            window = _next_window(
                pattern,
                now=moment,
                timezone_name=timezone_name,
            )
            if window is None:
                continue
            start, end = window
            item = HabitExpectation(
                expectation_id=_expectation_id(pattern.habit_id, start),
                habit_id=pattern.habit_id,
                principal_id=pattern.principal_id,
                window_start=start,
                window_end=end,
                created_at=moment,
                status=ExpectationStatus.PENDING,
                evidence_id=pattern.habit_id,
            )
            if self.store.save_expectation(item):
                created.append(item)
        return tuple(created)

    def evaluate_pending(
        self,
        *,
        principal_id: str,
        now: datetime,
    ) -> tuple[HabitExpectation, ...]:
        moment = _aware(now).astimezone(timezone.utc)
        changed: list[HabitExpectation] = []
        patterns = {
            pattern.habit_id: pattern
            for pattern in self.store.patterns(principal_id=principal_id)
        }
        observations = self.store.observations(
            principal_id=principal_id,
            since=moment - timedelta(days=370),
            limit=5000,
        )
        for item in self.store.pending_expectations(principal_id=principal_id):
            pattern = patterns.get(item.habit_id)
            if pattern is None or pattern.status in {
                HabitStatus.SUPPRESSED,
                HabitStatus.RETIRED,
            }:
                if moment >= item.window_start:
                    changed.append(
                        self.store.transition_expectation(
                            item.expectation_id,
                            expected=ExpectationStatus.PENDING,
                            target=ExpectationStatus.EXPIRED,
                            at=moment,
                        )
                    )
                continue

            matching = tuple(
                obs
                for obs in observations
                if obs.kind == pattern.kind
                and obs.value == pattern.value
                and item.window_start
                <= obs.observed_at.astimezone(timezone.utc)
                < item.window_end
            )
            if matching:
                changed.append(
                    self.store.transition_expectation(
                        item.expectation_id,
                        expected=ExpectationStatus.PENDING,
                        target=ExpectationStatus.FULFILLED,
                        at=moment,
                        evidence_id=matching[0].observation_id,
                    )
                )
                continue

            if moment < item.window_end:
                continue

            coverage = self.store.coverage_state(
                principal_id=principal_id,
                kind=pattern.kind,
                start=item.window_start,
                end=item.window_end,
            )
            target = (
                ExpectationStatus.MISSED
                if coverage is CoverageState.COVERED
                else ExpectationStatus.UNCERTAIN
            )
            changed.append(
                self.store.transition_expectation(
                    item.expectation_id,
                    expected=ExpectationStatus.PENDING,
                    target=target,
                    at=moment,
                )
            )
        return tuple(changed)
