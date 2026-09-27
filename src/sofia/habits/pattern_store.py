from __future__ import annotations

from datetime import datetime
from typing import Any

from sofia.habits.patterns import (
    CadenceKind,
    HabitCategory,
    HabitLifecycle,
    HabitPattern,
    HabitSuppression,
)
from sofia.state.json_repository import JsonStateRepository
from sofia.state.namespaces import HABIT_PATTERN, HABIT_SUPPRESSION
from sofia.state.plane import StatePlane, StatePlaneConflictError


class HabitPatternStore:
    """State Plane persistence for current patterns and append-only suppressions."""

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self._patterns = JsonStateRepository(state_plane, HABIT_PATTERN)
        self._suppressions = JsonStateRepository(state_plane, HABIT_SUPPRESSION)

    @staticmethod
    def _pattern_value(item: HabitPattern) -> dict[str, Any]:
        return {
            "pattern_id": item.pattern_id,
            "principal_id": item.principal_id,
            "audience_id": item.audience_id,
            "category": item.category.value,
            "cadence": item.cadence.value,
            "context": dict(sorted(item.context.items())),
            "support_count": item.support_count,
            "contradiction_count": item.contradiction_count,
            "observable_count": item.observable_count,
            "first_seen": item.first_seen.isoformat(),
            "last_seen": item.last_seen.isoformat(),
            "confidence": item.confidence,
            "lifecycle": item.lifecycle.value,
            "evidence_refs": list(item.evidence_refs),
        }

    @staticmethod
    def _decode_pattern(value: dict[str, Any]) -> HabitPattern:
        return HabitPattern(
            pattern_id=value["pattern_id"],
            principal_id=value["principal_id"],
            audience_id=value["audience_id"],
            category=HabitCategory(value["category"]),
            cadence=CadenceKind(value["cadence"]),
            context=dict(value.get("context", {})),
            support_count=int(value["support_count"]),
            contradiction_count=int(value["contradiction_count"]),
            observable_count=int(value["observable_count"]),
            first_seen=datetime.fromisoformat(value["first_seen"]),
            last_seen=datetime.fromisoformat(value["last_seen"]),
            confidence=float(value["confidence"]),
            lifecycle=HabitLifecycle(value["lifecycle"]),
            evidence_refs=tuple(value.get("evidence_refs", ())),
        )

    def get(
        self,
        pattern_id: str,
        *,
        principal_id: str,
        audience_id: str,
    ) -> HabitPattern | None:
        item = self._patterns.get(
            pattern_id,
            principal_id=principal_id,
            audience=audience_id,
        )
        return None if item is None else self._decode_pattern(item[0])

    def put(self, item: HabitPattern, *, source: str) -> HabitPattern:
        if not isinstance(item, HabitPattern):
            raise TypeError("item must be HabitPattern")
        self._patterns.put(
            item.pattern_id,
            self._pattern_value(item),
            principal_id=item.principal_id,
            audience=item.audience_id,
            updated_at=item.last_seen,
            source=source,
        )
        return item

    def patterns(
        self,
        *,
        principal_id: str,
        audience_id: str,
    ) -> tuple[HabitPattern, ...]:
        rows = self._patterns.list(
            principal_id=principal_id,
            audience=audience_id,
        )
        return tuple(
            sorted(
                (self._decode_pattern(value) for value, _ in rows),
                key=lambda item: item.pattern_id,
            )
        )

    @staticmethod
    def _suppression_value(item: HabitSuppression) -> dict[str, Any]:
        return {
            "suppression_id": item.suppression_id,
            "principal_id": item.principal_id,
            "audience_id": item.audience_id,
            "signature": item.signature,
            "reason": item.reason,
            "evidence_ref": item.evidence_ref,
            "created_at": item.created_at.isoformat(),
        }

    def suppress(self, item: HabitSuppression) -> HabitSuppression:
        if not isinstance(item, HabitSuppression):
            raise TypeError("item must be HabitSuppression")
        value = self._suppression_value(item)
        try:
            self._suppressions.create(
                item.suppression_id,
                value,
                principal_id=item.principal_id,
                audience=item.audience_id,
                updated_at=item.created_at,
                source=item.evidence_ref,
            )
        except StatePlaneConflictError:
            existing = self._suppressions.get(
                item.suppression_id,
                principal_id=item.principal_id,
                audience=item.audience_id,
            )
            if existing is None or existing[0] != value:
                raise ValueError(
                    "suppression ID already belongs to different evidence"
                )
        return item

    def is_suppressed(
        self,
        *,
        principal_id: str,
        audience_id: str,
        signature: str,
    ) -> bool:
        rows = self._suppressions.list(
            principal_id=principal_id,
            audience=audience_id,
        )
        return any(
            value.get("signature") == signature
            for value, _ in rows
        )
