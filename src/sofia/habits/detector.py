"""Deterministic pattern extraction over durable habit observations."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import math

from .model import HabitObservation, HabitPattern, HabitStatus
from .store import HabitStore


_CONTEXT_KEYS = ("weekday", "hour_bucket", "season", "daylight", "weather")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(timezone.utc)


def _habit_id(
    principal_id: str,
    audience_id: str | None,
    kind: str,
    value: str,
    context_key: str | None,
    context_value: str | None,
) -> str:
    raw = "\x1f".join((
        principal_id,
        audience_id or "",
        kind,
        value,
        context_key or "",
        context_value or "",
    ))
    return "habit:" + sha256(raw.encode("utf-8")).hexdigest()[:32]


def _confidence(
    *,
    support: int,
    distinct_days: int,
    span_days: float,
    age_days: float,
) -> float:
    """Bounded descriptive confidence, not probability or causality."""
    support_term = 1.0 - math.exp(-support / 5.0)
    day_term = min(1.0, distinct_days / 6.0)
    span_term = min(1.0, span_days / 21.0)
    recency = 0.5 ** (max(0.0, age_days) / 45.0)
    return round(
        max(0.0, min(1.0, support_term * (0.55 + 0.25 * day_term + 0.20 * span_term) * recency)),
        4,
    )


def _status(
    *,
    support: int,
    distinct_days: int,
    span_days: float,
    confidence: float,
) -> HabitStatus:
    if support >= 10 and distinct_days >= 6 and span_days >= 21 and confidence >= 0.70:
        return HabitStatus.TRUSTED
    if support >= 4 and distinct_days >= 3 and span_days >= 7 and confidence >= 0.48:
        return HabitStatus.ESTABLISHED
    return HabitStatus.TENTATIVE


class HabitPatternDetector:
    """Build base and single-context patterns without implying causal links."""

    def __init__(
        self,
        store: HabitStore,
        *,
        lookback_days: int = 120,
        max_evidence: int = 32,
    ) -> None:
        if not isinstance(store, HabitStore):
            raise TypeError("store must be HabitStore")
        if type(lookback_days) is not int or not 7 <= lookback_days <= 730:
            raise ValueError("lookback_days must be in 7..730")
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
            tuple[str, str | None, str, str, str | None, str | None],
            list[HabitObservation],
        ] = defaultdict(list)

        for item in observations:
            groups[
                (
                    item.principal_id,
                    item.audience_id,
                    item.kind,
                    item.value,
                    None,
                    None,
                )
            ].append(item)
            for key in _CONTEXT_KEYS:
                context_value = item.context_value(key)
                if context_value is None:
                    continue
                groups[
                    (
                        item.principal_id,
                        item.audience_id,
                        item.kind,
                        item.value,
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
            distinct_days = len({item.observed_at.astimezone(timezone.utc).date() for item in evidence})
            span_days = max(0.0, (last - first).total_seconds() / 86400.0)
            age_days = max(0.0, (moment - last).total_seconds() / 86400.0)
            confidence = _confidence(
                support=support,
                distinct_days=distinct_days,
                span_days=span_days,
                age_days=age_days,
            )
            status = _status(
                support=support,
                distinct_days=distinct_days,
                span_days=span_days,
                confidence=confidence,
            )
            pattern = HabitPattern(
                habit_id=_habit_id(
                    target_principal,
                    audience_id,
                    kind,
                    value,
                    context_key,
                    context_value,
                ),
                principal_id=target_principal,
                audience_id=audience_id,
                kind=kind,
                value=value,
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
                item.kind,
                item.value,
                item.context_key or "",
                item.context_value or "",
            )
        )
        return tuple(patterns)
