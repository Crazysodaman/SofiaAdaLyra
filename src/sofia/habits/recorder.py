from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sofia.habits.model import (
    CoverageWindow,
    HabitObservation,
    ObservationCoverage,
    SourceQuality,
)
from sofia.habits.store import HabitObservationStore


class HabitObservationRecorder:
    """Trusted ingestion boundary for durable habit evidence."""

    def __init__(self, store: HabitObservationStore) -> None:
        if not isinstance(store, HabitObservationStore):
            raise TypeError("store must be HabitObservationStore")
        self._store = store

    @staticmethod
    def _aware(value: datetime, label: str) -> datetime:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(f"{label} must be timezone-aware")
        return value

    @staticmethod
    def _id(prefix: str, *parts: str) -> str:
        payload = ":".join(parts)
        return f"{prefix}:{uuid5(NAMESPACE_URL, payload)}"

    def record(
        self,
        *,
        principal_id: str,
        audience_id: str,
        kind: str,
        occurred_at: datetime,
        local_timestamp: datetime,
        timezone_name: str,
        context: dict[str, str],
        evidence_ref: str,
        source_quality: SourceQuality,
        coverage: ObservationCoverage = ObservationCoverage.OBSERVED,
        sensitive: bool = False,
        explicit_user_evidence: bool = False,
    ) -> HabitObservation:
        occurred = self._aware(occurred_at, "occurred_at").astimezone(timezone.utc)
        local = self._aware(local_timestamp, "local_timestamp")
        item = HabitObservation(
            observation_id=self._id(
                "habit-observation",
                principal_id,
                audience_id,
                kind,
                evidence_ref,
            ),
            principal_id=principal_id,
            audience_id=audience_id,
            kind=kind,
            occurred_at_utc=occurred,
            local_timestamp=local,
            timezone=timezone_name,
            context=context,
            evidence_ref=evidence_ref,
            source_quality=source_quality,
            coverage=coverage,
            sensitive=sensitive,
            explicit_user_evidence=explicit_user_evidence,
        )
        return self._store.append_observation(item)

    def record_coverage(
        self,
        *,
        principal_id: str,
        audience_id: str,
        source_id: str,
        started_at: datetime,
        ended_at: datetime,
        status: ObservationCoverage,
        quality: SourceQuality,
        reason: str,
    ) -> CoverageWindow:
        start = self._aware(started_at, "started_at").astimezone(timezone.utc)
        end = self._aware(ended_at, "ended_at").astimezone(timezone.utc)
        item = CoverageWindow(
            coverage_id=self._id(
                "habit-coverage",
                principal_id,
                audience_id,
                source_id,
                start.isoformat(),
                end.isoformat(),
                status.value,
            ),
            principal_id=principal_id,
            audience_id=audience_id,
            source_id=source_id,
            started_at_utc=start,
            ended_at_utc=end,
            status=status,
            quality=quality,
            reason=reason,
        )
        return self._store.append_coverage(item)
