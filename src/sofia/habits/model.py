"""Typed models for evidence-backed habit learning.

Habits are descriptive correlations over recorded evidence. They never grant
authority, prove causality, establish consent, or convert an emotion into fact.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping


class ObservationSource(str, Enum):
    OBSERVED = "observed"
    USER_REPORTED = "user_reported"
    DERIVED = "derived"


class CoverageState(str, Enum):
    COVERED = "covered"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class HabitCadence(str, Enum):
    IRREGULAR = "irregular"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class HabitStatus(str, Enum):
    TENTATIVE = "tentative"
    ESTABLISHED = "established"
    TRUSTED = "trusted"
    SUPPRESSED = "suppressed"
    RETIRED = "retired"


class ExpectationStatus(str, Enum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    MISSED = "missed"
    UNCERTAIN = "uncertain"
    EXPIRED = "expired"


_ALLOWED_CONTEXT = frozenset({
    "weekday",
    "hour_bucket",
    "day_of_month",
    "month",
    "month_day",
    "season",
    "daylight",
    "weather",
    "location_label",
    "host_id",
    "activity_mode",
    "daily_window",
    "weekly_window",
    "monthly_window",
    "yearly_window",
})


def _text(value: str, label: str, limit: int = 160) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > limit
        or any(ch in value for ch in "\x00\r\n")
    ):
        raise ValueError(f"{label} must be bounded single-line text")
    return value.strip()


def _aware(value: datetime, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value


def _context(value: Mapping[str, str] | None) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise TypeError("context must be a mapping or None")
    items: list[tuple[str, str]] = []
    for key, raw in value.items():
        if key not in _ALLOWED_CONTEXT:
            raise ValueError(f"unsupported habit context key: {key}")
        items.append((_text(key, "context key", 64), _text(raw, "context value", 120)))
    return tuple(sorted(items))


@dataclass(frozen=True, slots=True)
class HabitObservation:
    observation_id: str
    principal_id: str
    audience_id: str | None
    kind: str
    value: str
    observed_at: datetime
    source_id: str
    source: ObservationSource
    context: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", _text(self.observation_id, "observation_id"))
        object.__setattr__(self, "principal_id", _text(self.principal_id, "principal_id"))
        if self.audience_id is not None:
            object.__setattr__(self, "audience_id", _text(self.audience_id, "audience_id"))
        object.__setattr__(self, "kind", _text(self.kind, "kind", 80))
        object.__setattr__(self, "value", _text(self.value, "value", 240))
        _aware(self.observed_at, "observed_at")
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        if not isinstance(self.source, ObservationSource):
            raise TypeError("source must be ObservationSource")
        if not isinstance(self.context, tuple):
            raise TypeError("context must be a tuple")
        object.__setattr__(self, "context", _context(dict(self.context)))

    @classmethod
    def create(
        cls,
        *,
        observation_id: str,
        principal_id: str,
        audience_id: str | None,
        kind: str,
        value: str,
        observed_at: datetime,
        source_id: str,
        source: ObservationSource,
        context: Mapping[str, str] | None = None,
    ) -> "HabitObservation":
        return cls(
            observation_id=observation_id,
            principal_id=principal_id,
            audience_id=audience_id,
            kind=kind,
            value=value,
            observed_at=observed_at,
            source_id=source_id,
            source=source,
            context=_context(context),
        )

    def context_value(self, key: str) -> str | None:
        for name, value in self.context:
            if name == key:
                return value
        return None


@dataclass(frozen=True, slots=True)
class ObservationCoverage:
    coverage_id: str
    principal_id: str
    source_id: str
    kind: str
    started_at: datetime
    ended_at: datetime
    state: CoverageState

    def __post_init__(self) -> None:
        object.__setattr__(self, "coverage_id", _text(self.coverage_id, "coverage_id"))
        object.__setattr__(self, "principal_id", _text(self.principal_id, "principal_id"))
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        object.__setattr__(self, "kind", _text(self.kind, "kind", 80))
        _aware(self.started_at, "started_at")
        _aware(self.ended_at, "ended_at")
        if self.ended_at <= self.started_at:
            raise ValueError("coverage must end after it starts")
        if not isinstance(self.state, CoverageState):
            raise TypeError("state must be CoverageState")


@dataclass(frozen=True, slots=True)
class HabitPattern:
    habit_id: str
    principal_id: str
    audience_id: str | None
    kind: str
    value: str
    cadence: HabitCadence
    context_key: str | None
    context_value: str | None
    first_observed_at: datetime
    last_observed_at: datetime
    support_count: int
    confidence: float
    status: HabitStatus
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("habit_id", "principal_id", "kind", "value"):
            object.__setattr__(self, name, _text(getattr(self, name), name, 240))
        if self.audience_id is not None:
            object.__setattr__(self, "audience_id", _text(self.audience_id, "audience_id"))
        if not isinstance(self.cadence, HabitCadence):
            raise TypeError("cadence must be HabitCadence")
        if (self.context_key is None) != (self.context_value is None):
            raise ValueError("context key/value must both be present or both be absent")
        if self.context_key is not None:
            if self.context_key not in _ALLOWED_CONTEXT:
                raise ValueError("unsupported context key")
            object.__setattr__(self, "context_value", _text(self.context_value, "context_value", 120))
        _aware(self.first_observed_at, "first_observed_at")
        _aware(self.last_observed_at, "last_observed_at")
        if self.last_observed_at < self.first_observed_at:
            raise ValueError("habit observation clock moved backward")
        if type(self.support_count) is not int or self.support_count < 1:
            raise ValueError("support_count must be positive")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise TypeError("confidence must be numeric")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in 0..1")
        if not isinstance(self.status, HabitStatus):
            raise TypeError("status must be HabitStatus")
        if (
            not isinstance(self.evidence_ids, tuple)
            or not self.evidence_ids
            or len(self.evidence_ids) > 32
        ):
            raise ValueError("habit requires 1..32 evidence IDs")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("habit evidence IDs must be unique")


@dataclass(frozen=True, slots=True)
class HabitExpectation:
    expectation_id: str
    habit_id: str
    principal_id: str
    window_start: datetime
    window_end: datetime
    created_at: datetime
    status: ExpectationStatus
    evidence_id: str
    fulfilled_by: str | None = None

    def __post_init__(self) -> None:
        for name in ("expectation_id", "habit_id", "principal_id", "evidence_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("window_start", "window_end", "created_at"):
            _aware(getattr(self, name), name)
        if self.window_end <= self.window_start:
            raise ValueError("expectation window must be positive")
        if self.created_at > self.window_end:
            raise ValueError("expectation cannot be created after its window ends")
        if not isinstance(self.status, ExpectationStatus):
            raise TypeError("status must be ExpectationStatus")
        if self.fulfilled_by is not None:
            object.__setattr__(self, "fulfilled_by", _text(self.fulfilled_by, "fulfilled_by"))
        if self.status is ExpectationStatus.FULFILLED and self.fulfilled_by is None:
            raise ValueError("fulfilled expectation requires evidence")
