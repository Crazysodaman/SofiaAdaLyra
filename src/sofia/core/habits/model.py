from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping


class ObservationCoverage(str, Enum):
    OBSERVED = "observed"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    SOURCE_OFFLINE = "source_offline"
    SOFIA_OFFLINE = "sofia_offline"
    NOT_APPLICABLE = "not_applicable"


class SourceQuality(str, Enum):
    VERIFIED = "verified"
    TRUSTED = "trusted"
    USER_REPORTED = "user_reported"
    INFERRED = "inferred"


@dataclass(frozen=True, slots=True)
class HabitObservation:
    observation_id: str
    principal_id: str
    audience_id: str
    kind: str
    occurred_at_utc: datetime
    local_timestamp: datetime
    timezone: str
    context: Mapping[str, str]
    evidence_ref: str
    source_quality: SourceQuality
    coverage: ObservationCoverage
    sensitive: bool = False
    explicit_user_evidence: bool = False

    def __post_init__(self) -> None:
        for name in (
            "observation_id", "principal_id", "audience_id", "kind",
            "timezone", "evidence_ref",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        for name in ("occurred_at_utc", "local_timestamp"):
            value = getattr(self, name)
            if not isinstance(value, datetime):
                raise TypeError(f"{name} must be a datetime")
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if not isinstance(self.source_quality, SourceQuality):
            raise TypeError("source_quality must be SourceQuality")
        if not isinstance(self.coverage, ObservationCoverage):
            raise TypeError("coverage must be ObservationCoverage")
        if type(self.sensitive) is not bool:
            raise TypeError("sensitive must be boolean")
        if type(self.explicit_user_evidence) is not bool:
            raise TypeError("explicit_user_evidence must be boolean")
        if self.sensitive and not self.explicit_user_evidence:
            raise ValueError(
                "sensitive habit observations require explicit user evidence"
            )
        if not isinstance(self.context, Mapping):
            raise TypeError("context must be a mapping")
        for key, value in self.context.items():
            if (
                not isinstance(key, str)
                or not key.strip()
                or not isinstance(value, str)
            ):
                raise ValueError("context must contain string keys and values")


@dataclass(frozen=True, slots=True)
class CoverageWindow:
    coverage_id: str
    principal_id: str
    audience_id: str
    source_id: str
    started_at_utc: datetime
    ended_at_utc: datetime
    status: ObservationCoverage
    quality: SourceQuality
    reason: str

    def __post_init__(self) -> None:
        for name in (
            "coverage_id", "principal_id", "audience_id", "source_id", "reason",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        for name in ("started_at_utc", "ended_at_utc"):
            value = getattr(self, name)
            if not isinstance(value, datetime):
                raise TypeError(f"{name} must be a datetime")
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.ended_at_utc < self.started_at_utc:
            raise ValueError("coverage window end cannot precede start")
        if not isinstance(self.status, ObservationCoverage):
            raise TypeError("status must be ObservationCoverage")
        if not isinstance(self.quality, SourceQuality):
            raise TypeError("quality must be SourceQuality")
