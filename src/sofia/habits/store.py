from __future__ import annotations

from datetime import datetime
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


def _iso(value: datetime) -> str:
    return value.isoformat()


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
            "occurred_at_utc": _iso(item.occurred_at_utc),
            "local_timestamp": _iso(item.local_timestamp),
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
            "started_at_utc": _iso(item.started_at_utc),
            "ended_at_utc": _iso(item.ended_at_utc),
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
