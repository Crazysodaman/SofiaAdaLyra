"""Expectation creation/evaluation for established time-based habits."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from zoneinfo import ZoneInfo

from .model import (
    CoverageState,
    ExpectationStatus,
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


def _next_window(
    pattern: HabitPattern,
    *,
    now: datetime,
    timezone_name: str,
) -> tuple[datetime, datetime] | None:
    if pattern.context_key not in {"hour_bucket", "weekday_hour"}:
        return None
    zone = ZoneInfo(timezone_name)
    local_now = _aware(now).astimezone(zone)

    if pattern.context_key == "hour_bucket":
        weekday: int | None = None
        bucket_raw = pattern.context_value
    else:
        assert pattern.context_value is not None
        weekday_raw, bucket_raw = pattern.context_value.split("|", 1)
        weekday = int(weekday_raw)
        if not 0 <= weekday <= 6:
            raise ValueError("stored weekday context is invalid")

    assert bucket_raw is not None
    bucket = int(bucket_raw)
    if not 0 <= bucket <= 11:
        raise ValueError("stored hour bucket context is invalid")
    hour = bucket * 2

    for offset in range(0, 8):
        day = (local_now + timedelta(days=offset)).date()
        if weekday is not None and day.weekday() != weekday:
            continue
        start = datetime(
            day.year,
            day.month,
            day.day,
            hour,
            0,
            tzinfo=zone,
        )
        end = start + timedelta(hours=2)
        if end <= local_now:
            continue
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    return None


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
            since=moment - timedelta(days=8),
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
                and item.window_start <= obs.observed_at.astimezone(timezone.utc) < item.window_end
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
