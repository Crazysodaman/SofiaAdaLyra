from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5
from typing import Any

from sofia.habits.model import (
    CoverageWindow,
    HabitObservation,
    ObservationCoverage,
    SourceQuality,
)
from sofia.state.json_repository import JsonStateRepository
from sofia.state.namespaces import HABIT_COVERAGE, HABIT_OBSERVATION
from sofia.state.plane import StatePlane, StatePlaneConflictError


class HabitObservationStore:
    """Append-only HABIT evidence on the shared State Plane."""

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self._observations = JsonStateRepository(
            state_plane,
            HABIT_OBSERVATION,
        )
        self._coverage = JsonStateRepository(
            state_plane,
            HABIT_COVERAGE,
        )

    @staticmethod
    def _observation_value(item: HabitObservation) -> dict[str, Any]:
        return {
            "observation_id": item.observation_id,
            "principal_id": item.principal_id,
            "audience_id": item.audience_id,
            "kind": item.kind,
            "occurred_at_utc": item.occurred_at_utc.isoformat(),
            "local_timestamp": item.local_timestamp.isoformat(),
            "timezone": item.timezone,
            "context": dict(sorted(item.context.items())),
            "evidence_ref": item.evidence_ref,
            "source_quality": item.source_quality.value,
            "coverage": item.coverage.value,
            "sensitive": item.sensitive,
            "explicit_user_evidence": item.explicit_user_evidence,
        }

    @staticmethod
    def _coverage_value(item: CoverageWindow) -> dict[str, Any]:
        return {
            "coverage_id": item.coverage_id,
            "principal_id": item.principal_id,
            "audience_id": item.audience_id,
            "source_id": item.source_id,
            "started_at_utc": item.started_at_utc.isoformat(),
            "ended_at_utc": item.ended_at_utc.isoformat(),
            "status": item.status.value,
            "quality": item.quality.value,
            "reason": item.reason,
        }

    @staticmethod
    def _decode_observation(value: dict[str, Any]) -> HabitObservation:
        return HabitObservation(
            observation_id=value["observation_id"],
            principal_id=value["principal_id"],
            audience_id=value["audience_id"],
            kind=value["kind"],
            occurred_at_utc=datetime.fromisoformat(value["occurred_at_utc"]),
            local_timestamp=datetime.fromisoformat(value["local_timestamp"]),
            timezone=value["timezone"],
            context=dict(value.get("context", {})),
            evidence_ref=value["evidence_ref"],
            source_quality=SourceQuality(value["source_quality"]),
            coverage=ObservationCoverage(value["coverage"]),
            sensitive=bool(value.get("sensitive", False)),
            explicit_user_evidence=bool(
                value.get("explicit_user_evidence", False)
            ),
        )

    @staticmethod
    def _decode_coverage(value: dict[str, Any]) -> CoverageWindow:
        return CoverageWindow(
            coverage_id=value["coverage_id"],
            principal_id=value["principal_id"],
            audience_id=value["audience_id"],
            source_id=value["source_id"],
            started_at_utc=datetime.fromisoformat(value["started_at_utc"]),
            ended_at_utc=datetime.fromisoformat(value["ended_at_utc"]),
            status=ObservationCoverage(value["status"]),
            quality=SourceQuality(value["quality"]),
            reason=value["reason"],
        )

    def append_observation(self, item: HabitObservation) -> HabitObservation:
        if not isinstance(item, HabitObservation):
            raise TypeError("item must be HabitObservation")
        value = self._observation_value(item)
        try:
            self._observations.create(
                item.observation_id,
                value,
                principal_id=item.principal_id,
                audience=item.audience_id,
                updated_at=item.occurred_at_utc,
                source=item.evidence_ref,
            )
        except StatePlaneConflictError:
            existing = self._observations.get(
                item.observation_id,
                principal_id=item.principal_id,
                audience=item.audience_id,
            )
            if existing is None or existing[0] != value:
                raise ValueError(
                    "observation ID already belongs to different evidence"
                )
        return item

    def append_coverage(self, item: CoverageWindow) -> CoverageWindow:
        if not isinstance(item, CoverageWindow):
            raise TypeError("item must be CoverageWindow")
        value = self._coverage_value(item)
        try:
            self._coverage.create(
                item.coverage_id,
                value,
                principal_id=item.principal_id,
                audience=item.audience_id,
                updated_at=item.ended_at_utc,
                source=item.source_id,
            )
        except StatePlaneConflictError:
            existing = self._coverage.get(
                item.coverage_id,
                principal_id=item.principal_id,
                audience=item.audience_id,
            )
            if existing is None or existing[0] != value:
                raise ValueError(
                    "coverage ID already belongs to different evidence"
                )
        return item

    def observations(
        self,
        *,
        principal_id: str,
        audience_id: str,
    ) -> tuple[HabitObservation, ...]:
        rows = self._observations.list(
            principal_id=principal_id,
            audience=audience_id,
        )
        items = [self._decode_observation(value) for value, _ in rows]
        return tuple(sorted(
            items,
            key=lambda item: (
                item.occurred_at_utc,
                item.observation_id,
            ),
        ))

    def coverage_windows(
        self,
        *,
        principal_id: str,
        audience_id: str,
    ) -> tuple[CoverageWindow, ...]:
        rows = self._coverage.list(
            principal_id=principal_id,
            audience=audience_id,
        )
        items = [self._decode_coverage(value) for value, _ in rows]
        return tuple(sorted(
            items,
            key=lambda item: (
                item.started_at_utc,
                item.ended_at_utc,
                item.coverage_id,
            ),
        ))


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
