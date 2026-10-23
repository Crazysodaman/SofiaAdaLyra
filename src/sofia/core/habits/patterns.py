from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from math import exp
from typing import Mapping


class HabitLifecycle(str, Enum):
    TENTATIVE = "tentative"
    ESTABLISHED = "established"
    TRUSTED = "trusted"
    RETIRED = "retired"
    SUPPRESSED = "suppressed"


class HabitCategory(str, Enum):
    BEHAVIOR_ROUTINE = "behavior_routine"
    CONVERSATION_ROUTINE = "conversation_routine"
    RELATIONSHIP_ROUTINE = "relationship_routine"
    PREFERENCE_PATTERN = "preference_pattern"
    ENVIRONMENT_CORRELATION = "environment_correlation"
    SYSTEM_PATTERN = "system_pattern"


class CadenceKind(str, Enum):
    TIME_OF_DAY = "time_of_day"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    SEASONAL = "seasonal"
    INTERVAL = "interval"


@dataclass(frozen=True, slots=True)
class HabitPattern:
    pattern_id: str
    principal_id: str
    audience_id: str
    category: HabitCategory
    cadence: CadenceKind
    context: Mapping[str, str]
    support_count: int
    contradiction_count: int
    observable_count: int
    first_seen: datetime
    last_seen: datetime
    confidence: float
    lifecycle: HabitLifecycle
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("pattern_id", "principal_id", "audience_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if not isinstance(self.category, HabitCategory):
            raise TypeError("category must be HabitCategory")
        if not isinstance(self.cadence, CadenceKind):
            raise TypeError("cadence must be CadenceKind")
        if not isinstance(self.context, Mapping):
            raise TypeError("context must be a mapping")
        if any(
            type(value) is not int or value < 0
            for value in (
                self.support_count,
                self.contradiction_count,
                self.observable_count,
            )
        ):
            raise ValueError("habit counts must be nonnegative integers")
        if self.support_count + self.contradiction_count > self.observable_count:
            raise ValueError("support plus contradiction cannot exceed observable count")
        for value in (self.first_seen, self.last_seen):
            if not isinstance(value, datetime):
                raise TypeError("pattern timestamps must be datetimes")
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("pattern timestamps must be timezone-aware")
        if self.last_seen < self.first_seen:
            raise ValueError("last_seen cannot precede first_seen")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if not isinstance(self.lifecycle, HabitLifecycle):
            raise TypeError("lifecycle must be HabitLifecycle")
        if (
            not isinstance(self.evidence_refs, tuple)
            or len(self.evidence_refs) > 64
            or len(set(self.evidence_refs)) != len(self.evidence_refs)
        ):
            raise ValueError("evidence_refs must be a distinct tuple of at most 64 IDs")



@dataclass(frozen=True, slots=True)
class HabitSuppression:
    suppression_id: str
    principal_id: str
    audience_id: str
    signature: str
    reason: str
    evidence_ref: str
    created_at: datetime

    def __post_init__(self) -> None:
        for name in (
            "suppression_id",
            "principal_id",
            "audience_id",
            "signature",
            "reason",
            "evidence_ref",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
        ):
            raise ValueError("created_at must be timezone-aware")


class HabitConfidence:
    """Deterministic, explainable habit confidence with recency decay."""

    HALF_LIFE_DAYS = 45.0

    @classmethod
    def score(
        cls,
        *,
        support_count: int,
        contradiction_count: int,
        observable_count: int,
        last_seen: datetime,
        now: datetime,
    ) -> float:
        if any(
            type(value) is not int or value < 0
            for value in (support_count, contradiction_count, observable_count)
        ):
            raise ValueError("counts must be nonnegative integers")
        if support_count + contradiction_count > observable_count:
            raise ValueError("evidence count exceeds observable coverage")
        for value in (last_seen, now):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("confidence timestamps must be timezone-aware")
        if observable_count == 0:
            return 0.0

        direct = support_count / max(1, support_count + contradiction_count)
        evidence_strength = min(1.0, observable_count / 8.0)
        age_days = max(
            0.0,
            (
                now.astimezone(timezone.utc)
                - last_seen.astimezone(timezone.utc)
            ).total_seconds() / 86400.0,
        )
        decay = exp(-0.6931471805599453 * age_days / cls.HALF_LIFE_DAYS)
        return round(max(0.0, min(1.0, direct * evidence_strength * decay)), 4)

    @staticmethod
    def lifecycle(
        *,
        confidence: float,
        support_count: int,
        suppressed: bool = False,
    ) -> HabitLifecycle:
        if suppressed:
            return HabitLifecycle.SUPPRESSED
        if confidence >= 0.80 and support_count >= 8:
            return HabitLifecycle.TRUSTED
        if confidence >= 0.55 and support_count >= 4:
            return HabitLifecycle.ESTABLISHED
        return HabitLifecycle.TENTATIVE
