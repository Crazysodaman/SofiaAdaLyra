from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json

from sofia.habits.engine import HabitPatternEngine, pattern_signature
from sofia.habits.pattern_store import HabitPatternStore
from sofia.habits.patterns import HabitPattern


@dataclass(frozen=True, slots=True)
class HabitExplanation:
    pattern_id: str
    lifecycle: str
    confidence: float
    support_count: int
    contradiction_count: int
    observable_count: int
    context: dict[str, str]
    evidence_refs: tuple[str, ...]


class HabitUserControls:
    """Deterministic user-facing controls over learned habit state."""

    def __init__(
        self,
        *,
        store: HabitPatternStore,
        engine: HabitPatternEngine,
    ) -> None:
        if not isinstance(store, HabitPatternStore):
            raise TypeError("store must be HabitPatternStore")
        if not isinstance(engine, HabitPatternEngine):
            raise TypeError("engine must be HabitPatternEngine")
        self._store = store
        self._engine = engine

    def learned(
        self,
        *,
        principal_id: str,
        audience_id: str,
    ) -> tuple[HabitExplanation, ...]:
        return tuple(
            HabitExplanation(
                pattern_id=item.pattern_id,
                lifecycle=item.lifecycle.value,
                confidence=item.confidence,
                support_count=item.support_count,
                contradiction_count=item.contradiction_count,
                observable_count=item.observable_count,
                context=dict(item.context),
                evidence_refs=item.evidence_refs,
            )
            for item in self._store.patterns(
                principal_id=principal_id,
                audience_id=audience_id,
            )
        )

    def explain(
        self,
        *,
        pattern_id: str,
        principal_id: str,
        audience_id: str,
    ) -> HabitExplanation:
        pattern = self._store.get(
            pattern_id,
            principal_id=principal_id,
            audience_id=audience_id,
        )
        if pattern is None:
            raise KeyError(pattern_id)
        return HabitExplanation(
            pattern_id=pattern.pattern_id,
            lifecycle=pattern.lifecycle.value,
            confidence=pattern.confidence,
            support_count=pattern.support_count,
            contradiction_count=pattern.contradiction_count,
            observable_count=pattern.observable_count,
            context=dict(pattern.context),
            evidence_refs=pattern.evidence_refs,
        )

    def suppress(
        self,
        *,
        pattern: HabitPattern,
        reason: str,
        evidence_ref: str,
        created_at: datetime,
    ):
        signature_payload = {
            "category": pattern.category.value,
            "cadence": pattern.cadence.value,
            "kind": pattern.context.get("observation_kind", ""),
            "context": {
                key: value
                for key, value in pattern.context.items()
                if key != "observation_kind"
            },
        }
        signature = sha256(
            json.dumps(
                signature_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return self._engine.suppress(
            pattern=pattern,
            signature=signature,
            reason=reason,
            evidence_ref=evidence_ref,
            created_at=created_at,
        )

    def invalidate_evidence(
        self,
        *,
        pattern: HabitPattern,
        evidence_ref: str,
        reason: str,
        created_at: datetime,
        observations,
    ) -> HabitPattern:
        self._store.invalidate_evidence(
            principal_id=pattern.principal_id,
            audience_id=pattern.audience_id,
            evidence_ref=evidence_ref,
            reason=reason,
            created_at=created_at,
        )
        return self._engine.rebuild_from_observations(
            pattern=pattern,
            observations=tuple(observations),
            now=created_at,
        )
