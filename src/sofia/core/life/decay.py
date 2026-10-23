"""Deterministic, read-only decay projections for LIFE interests and hobbies.

Interest and hobby revisions stay immutable in their canonical tables.
Decay is a pure derived view anchored at each record's own revision time,
so reinforced records (newest revision) are automatically the least
decayed. Nothing here mutates canonical state, and no decay result is
treated as evidence; host-written expression keeps its separate floor.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .hobby import HobbyRecord
from .model import InterestRecord, aware


INTEREST_HALF_LIFE_DAYS = 30.0
HOBBY_HALF_LIFE_DAYS = 45.0


@dataclass(frozen=True, slots=True)
class DecayedInterest:
    record: InterestRecord
    original_strength: float
    effective_strength: float
    days_idle: float


@dataclass(frozen=True, slots=True)
class DecayedHobby:
    record: HobbyRecord
    original_strength: float
    effective_strength: float
    anchored_at: datetime
    days_idle: float


def _idle_days(anchor: datetime, now: datetime) -> float:
    return max(0.0, (now - anchor).total_seconds() / 86400.0)


def _decayed(base: float, idle_days: float, half_life_days: float) -> float:
    value = base * 2.0 ** (-idle_days / half_life_days)
    return round(value, 6)


def effective_interest_strength(
    record: InterestRecord, *, now: datetime,
    half_life_days: float = INTEREST_HALF_LIFE_DAYS,
) -> float:
    """Decay one interest revision toward zero with its stable identity kept.

    Future-recorded revisions are not punished: until their revision time
    arrives the projection simply reports the recorded strength.
    """
    aware(now, "now")
    if not half_life_days > 0:
        raise ValueError("half_life_days must be positive")
    return _decayed(record.strength, _idle_days(record.recorded_at, now), half_life_days)


def effective_hobby_strength(
    record: HobbyRecord, *, now: datetime, last_engaged_at: datetime | None = None,
    half_life_days: float = HOBBY_HALF_LIFE_DAYS,
) -> float:
    """Decay hobby attachment from the last evidence-backed engagement."""
    aware(now, "now")
    if not half_life_days > 0:
        raise ValueError("half_life_days must be positive")
    anchor = record.recorded_at if last_engaged_at is None else last_engaged_at
    aware(anchor, "hobby decay anchor")
    return _decayed(record.strength, _idle_days(anchor, now), half_life_days)


def interest_decay_report(
    records: tuple[InterestRecord, ...], *, now: datetime,
    half_life_days: float = INTEREST_HALF_LIFE_DAYS,
) -> tuple[DecayedInterest, ...]:
    """Deterministic projection: strongest effective first, name as tiebreak."""
    entries = tuple(
        DecayedInterest(
            record=record,
            original_strength=record.strength,
            effective_strength=effective_interest_strength(
                record, now=now, half_life_days=half_life_days,
            ),
            days_idle=_idle_days(record.recorded_at, now),
        )
        for record in records
    )
    return tuple(sorted(
        entries,
        key=lambda item: (-item.effective_strength, item.record.name, item.record.context),
    ))


def hobby_decay_report(
    records: tuple[HobbyRecord, ...], *, now: datetime,
    last_engaged_by: Mapping[str, datetime] | None = None,
    half_life_days: float = HOBBY_HALF_LIFE_DAYS,
) -> tuple[DecayedHobby, ...]:
    """Deterministic projection with engagement-recency reinforcement."""
    engagement_map = last_engaged_by or {}
    entries = tuple(
        DecayedHobby(
            record=record,
            original_strength=record.strength,
            effective_strength=effective_hobby_strength(
                record, now=now,
                last_engaged_at=engagement_map.get(record.name),
                half_life_days=half_life_days,
            ),
            anchored_at=(
                record.recorded_at if engagement_map.get(record.name) is None
                else engagement_map[record.name]
            ),
            days_idle=_idle_days(
                record.recorded_at if engagement_map.get(record.name) is None
                else engagement_map[record.name],
                now,
            ),
        )
        for record in records
    )
    return tuple(sorted(
        entries,
        key=lambda item: (-item.effective_strength, item.record.name),
    ))
