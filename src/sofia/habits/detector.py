"""Deterministic cadence-aware pattern extraction over habit observations."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import math

from .model import (
    HabitCadence,
    HabitObservation,
    HabitPattern,
    HabitStatus,
)
from .store import HabitStore


_CORRELATION_CONTEXT_KEYS = ("season", "daylight", "weather", "location_label", "activity_mode")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(timezone.utc)


def _habit_id(
    principal_id: str,
    audience_id: str | None,
    kind: str,
    value: str,
    cadence: HabitCadence,
    context_key: str | None,
    context_value: str | None,
) -> str:
    raw = "\x1f".join((
        principal_id,
        audience_id or "",
        kind,
        value,
        cadence.value,
        context_key or "",
        context_value or "",
    ))
    return "habit:" + sha256(raw.encode("utf-8")).hexdigest()[:32]


def _distinct_periods(
    evidence: list[HabitObservation],
    cadence: HabitCadence,
) -> int:
    if cadence in (HabitCadence.IRREGULAR, HabitCadence.DAILY):
        return len({item.observed_at.astimezone(timezone.utc).date() for item in evidence})
    if cadence is HabitCadence.WEEKLY:
        return len({
            item.observed_at.astimezone(timezone.utc).date().isocalendar()[:2]
            for item in evidence
        })
    if cadence is HabitCadence.MONTHLY:
        return len({
            (
                item.observed_at.astimezone(timezone.utc).year,
                item.observed_at.astimezone(timezone.utc).month,
            )
            for item in evidence
        })
    return len({item.observed_at.astimezone(timezone.utc).year for item in evidence})


def _confidence(
    *,
    cadence: HabitCadence,
    support: int,
    distinct_periods: int,
    span_days: float,
    age_days: float,
) -> float:
    """Descriptive confidence calibrated to cadence, never causal probability."""
    scale = {
        HabitCadence.IRREGULAR: 5.0,
        HabitCadence.DAILY: 5.0,
        HabitCadence.WEEKLY: 4.0,
        HabitCadence.MONTHLY: 3.0,
        HabitCadence.YEARLY: 2.0,
    }[cadence]
    expected_span = {
        HabitCadence.IRREGULAR: 21.0,
        HabitCadence.DAILY: 21.0,
        HabitCadence.WEEKLY: 42.0,
        HabitCadence.MONTHLY: 180.0,
        HabitCadence.YEARLY: 730.0,
    }[cadence]
    expected_periods = {
        HabitCadence.IRREGULAR: 6.0,
        HabitCadence.DAILY: 6.0,
        HabitCadence.WEEKLY: 6.0,
        HabitCadence.MONTHLY: 6.0,
        HabitCadence.YEARLY: 3.0,
    }[cadence]
    half_life_days = {
        HabitCadence.IRREGULAR: 45.0,
        HabitCadence.DAILY: 45.0,
        HabitCadence.WEEKLY: 90.0,
        HabitCadence.MONTHLY: 240.0,
        HabitCadence.YEARLY: 730.0,
    }[cadence]
    support_term = 1.0 - math.exp(-support / scale)
    period_term = min(1.0, distinct_periods / expected_periods)
    span_term = min(1.0, span_days / expected_span)
    recency = 0.5 ** (max(0.0, age_days) / half_life_days)
    return round(
        max(
            0.0,
            min(
                1.0,
                support_term
                * (0.50 + 0.30 * period_term + 0.20 * span_term)
                * recency,
            ),
        ),
        4,
    )


def _status(
    *,
    cadence: HabitCadence,
    support: int,
    distinct_periods: int,
    span_days: float,
    confidence: float,
) -> HabitStatus:
    established = {
        HabitCadence.IRREGULAR: (4, 3, 7.0, 0.48),
        HabitCadence.DAILY: (4, 3, 7.0, 0.48),
        HabitCadence.WEEKLY: (3, 3, 14.0, 0.45),
        HabitCadence.MONTHLY: (3, 3, 55.0, 0.42),
        HabitCadence.YEARLY: (2, 2, 300.0, 0.38),
    }[cadence]
    trusted = {
        HabitCadence.IRREGULAR: (10, 6, 21.0, 0.70),
        HabitCadence.DAILY: (10, 6, 21.0, 0.70),
        HabitCadence.WEEKLY: (6, 6, 35.0, 0.68),
        HabitCadence.MONTHLY: (6, 6, 150.0, 0.65),
        HabitCadence.YEARLY: (3, 3, 700.0, 0.60),
    }[cadence]
    if (
        support >= trusted[0]
        and distinct_periods >= trusted[1]
        and span_days >= trusted[2]
        and confidence >= trusted[3]
    ):
        return HabitStatus.TRUSTED
    if (
        support >= established[0]
        and distinct_periods >= established[1]
        and span_days >= established[2]
        and confidence >= established[3]
    ):
        return HabitStatus.ESTABLISHED
    return HabitStatus.TENTATIVE


class HabitPatternDetector:
    """Build cadence and contextual patterns without implying causal links."""

    def __init__(
        self,
        store: HabitStore,
        *,
        lookback_days: int = 1095,
        max_evidence: int = 32,
    ) -> None:
        if not isinstance(store, HabitStore):
            raise TypeError("store must be HabitStore")
        if type(lookback_days) is not int or not 30 <= lookback_days <= 3650:
            raise ValueError("lookback_days must be in 30..3650")
        if type(max_evidence) is not int or not 4 <= max_evidence <= 32:
            raise ValueError("max_evidence must be in 4..32")
        self.store = store
        self.lookback_days = lookback_days
        self.max_evidence = max_evidence

    def analyze(
        self,
        *,
        principal_id: str,
        now: datetime,
    ) -> tuple[HabitPattern, ...]:
        moment = _utc(now)
        since = moment - timedelta(days=self.lookback_days)
        observations = self.store.observations(
            principal_id=principal_id,
            since=since,
            limit=5000,
        )
        groups: dict[
            tuple[
                str,
                str | None,
                str,
                str,
                HabitCadence,
                str | None,
                str | None,
            ],
            list[HabitObservation],
        ] = defaultdict(list)

        for item in observations:
            base = (
                item.principal_id,
                item.audience_id,
                item.kind,
                item.value,
            )
            groups[(*base, HabitCadence.IRREGULAR, None, None)].append(item)

            hour_bucket = item.context_value("hour_bucket")
            weekday = item.context_value("weekday")
            day_of_month = item.context_value("day_of_month")
            month_day = item.context_value("month_day")

            if hour_bucket is not None:
                groups[
                    (*base, HabitCadence.DAILY, "daily_window", hour_bucket)
                ].append(item)
            if weekday is not None and hour_bucket is not None:
                groups[
                    (
                        *base,
                        HabitCadence.WEEKLY,
                        "weekly_window",
                        f"{weekday}|{hour_bucket}",
                    )
                ].append(item)
            if day_of_month is not None and hour_bucket is not None:
                groups[
                    (
                        *base,
                        HabitCadence.MONTHLY,
                        "monthly_window",
                        f"{day_of_month}|{hour_bucket}",
                    )
                ].append(item)
            if month_day is not None and hour_bucket is not None:
                groups[
                    (
                        *base,
                        HabitCadence.YEARLY,
                        "yearly_window",
                        f"{month_day}|{hour_bucket}",
                    )
                ].append(item)

            for key in _CORRELATION_CONTEXT_KEYS:
                context_value = item.context_value(key)
                if context_value is not None:
                    groups[
                        (
                            *base,
                            HabitCadence.IRREGULAR,
                            key,
                            context_value,
                        )
                    ].append(item)

        patterns: list[HabitPattern] = []
        for (
            target_principal,
            audience_id,
            kind,
            value,
            cadence,
            context_key,
            context_value,
        ), evidence in groups.items():
            if self.store.suppressed(
                principal_id=target_principal,
                kind=kind,
                value=value,
                context_key=context_key,
                context_value=context_value,
            ):
                continue
            evidence.sort(key=lambda item: (item.observed_at, item.observation_id))
            first = evidence[0].observed_at.astimezone(timezone.utc)
            last = evidence[-1].observed_at.astimezone(timezone.utc)
            support = len(evidence)
            periods = _distinct_periods(evidence, cadence)
            span_days = max(0.0, (last - first).total_seconds() / 86400.0)
            age_days = max(0.0, (moment - last).total_seconds() / 86400.0)
            confidence = _confidence(
                cadence=cadence,
                support=support,
                distinct_periods=periods,
                span_days=span_days,
                age_days=age_days,
            )
            status = _status(
                cadence=cadence,
                support=support,
                distinct_periods=periods,
                span_days=span_days,
                confidence=confidence,
            )
            pattern = HabitPattern(
                habit_id=_habit_id(
                    target_principal,
                    audience_id,
                    kind,
                    value,
                    cadence,
                    context_key,
                    context_value,
                ),
                principal_id=target_principal,
                audience_id=audience_id,
                kind=kind,
                value=value,
                cadence=cadence,
                context_key=context_key,
                context_value=context_value,
                first_observed_at=first,
                last_observed_at=last,
                support_count=support,
                confidence=confidence,
                status=status,
                evidence_ids=tuple(
                    item.observation_id
                    for item in evidence[-self.max_evidence:]
                ),
            )
            self.store.save_pattern(pattern, at=moment)
            patterns.append(pattern)

        patterns.sort(
            key=lambda item: (
                -item.confidence,
                -item.support_count,
                item.cadence.value,
                item.kind,
                item.value,
                item.context_key or "",
                item.context_value or "",
            )
        )
        return tuple(patterns)
