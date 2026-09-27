from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import NAMESPACE_URL, uuid5

from sofia.habits.model import HabitObservation, ObservationCoverage
from sofia.habits.pattern_store import HabitPatternStore
from sofia.habits.patterns import (
    CadenceKind,
    HabitCategory,
    HabitConfidence,
    HabitLifecycle,
    HabitPattern,
    HabitSuppression,
)


def pattern_signature(
    *,
    category: HabitCategory,
    cadence: CadenceKind,
    kind: str,
    context: dict[str, str],
) -> str:
    payload = {
        "category": category.value,
        "cadence": cadence.value,
        "kind": kind,
        "context": dict(sorted(context.items())),
    }
    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


class HabitPatternEngine:
    """Deterministic evidence-to-pattern reducer.

    Missing/unknown coverage never becomes contradiction evidence. The caller
    must explicitly provide a covered non-occurrence before contradiction
    counts may increase.
    """

    def __init__(self, store: HabitPatternStore) -> None:
        if not isinstance(store, HabitPatternStore):
            raise TypeError("store must be HabitPatternStore")
        self._store = store

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("pattern evaluation time must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _pattern_id(
        *,
        principal_id: str,
        audience_id: str,
        signature: str,
    ) -> str:
        return str(uuid5(
            NAMESPACE_URL,
            f"sofia-habit:{principal_id}:{audience_id}:{signature}",
        ))

    def observe_support(
        self,
        observation: HabitObservation,
        *,
        category: HabitCategory,
        cadence: CadenceKind,
        pattern_context: dict[str, str],
        now: datetime,
    ) -> HabitPattern | None:
        if not isinstance(observation, HabitObservation):
            raise TypeError("observation must be HabitObservation")
        if observation.coverage not in (
            ObservationCoverage.OBSERVED,
            ObservationCoverage.PARTIAL,
        ):
            return None

        current = self._utc(now)
        signature = pattern_signature(
            category=category,
            cadence=cadence,
            kind=observation.kind,
            context=pattern_context,
        )
        if self._store.is_suppressed(
            principal_id=observation.principal_id,
            audience_id=observation.audience_id,
            signature=signature,
        ):
            return None

        pattern_id = self._pattern_id(
            principal_id=observation.principal_id,
            audience_id=observation.audience_id,
            signature=signature,
        )
        existing = self._store.get(
            pattern_id,
            principal_id=observation.principal_id,
            audience_id=observation.audience_id,
        )
        if (
            existing is not None
            and observation.evidence_ref in existing.evidence_refs
        ):
            return existing
        if existing is None:
            support = 1
            observable = 1
            confidence = HabitConfidence.score(
                support_count=support,
                contradiction_count=0,
                observable_count=observable,
                last_seen=observation.occurred_at_utc,
                now=current,
            )
            pattern = HabitPattern(
                pattern_id=pattern_id,
                principal_id=observation.principal_id,
                audience_id=observation.audience_id,
                category=category,
                cadence=cadence,
                context={
                    "observation_kind": observation.kind,
                    **dict(sorted(pattern_context.items())),
                },
                support_count=support,
                contradiction_count=0,
                observable_count=observable,
                first_seen=observation.occurred_at_utc,
                last_seen=observation.occurred_at_utc,
                confidence=confidence,
                lifecycle=HabitConfidence.lifecycle(
                    confidence=confidence,
                    support_count=support,
                ),
                evidence_refs=(observation.evidence_ref,),
            )
        else:
            refs = existing.evidence_refs
            if observation.evidence_ref not in refs:
                refs = (*refs, observation.evidence_ref)[-64:]
            support = existing.support_count + 1
            observable = existing.observable_count + 1
            confidence = HabitConfidence.score(
                support_count=support,
                contradiction_count=existing.contradiction_count,
                observable_count=observable,
                last_seen=observation.occurred_at_utc,
                now=current,
            )
            pattern = replace(
                existing,
                support_count=support,
                observable_count=observable,
                last_seen=max(existing.last_seen, observation.occurred_at_utc),
                confidence=confidence,
                lifecycle=HabitConfidence.lifecycle(
                    confidence=confidence,
                    support_count=support,
                ),
                evidence_refs=refs,
            )
        return self._store.put(
            pattern,
            source=observation.evidence_ref,
        )

    def observe_covered_nonoccurrence(
        self,
        *,
        pattern: HabitPattern,
        evidence_ref: str,
        observed_at: datetime,
        coverage: ObservationCoverage,
    ) -> HabitPattern:
        if coverage not in (
            ObservationCoverage.OBSERVED,
            ObservationCoverage.PARTIAL,
        ):
            return pattern
        current = self._utc(observed_at)
        contradiction = pattern.contradiction_count + 1
        observable = pattern.observable_count + 1
        confidence = HabitConfidence.score(
            support_count=pattern.support_count,
            contradiction_count=contradiction,
            observable_count=observable,
            last_seen=pattern.last_seen,
            now=current,
        )
        refs = pattern.evidence_refs
        if evidence_ref not in refs:
            refs = (*refs, evidence_ref)[-64:]
        lifecycle = HabitConfidence.lifecycle(
            confidence=confidence,
            support_count=pattern.support_count,
        )
        if confidence < 0.15 and pattern.support_count >= 2:
            lifecycle = HabitLifecycle.RETIRED
        updated = replace(
            pattern,
            contradiction_count=contradiction,
            observable_count=observable,
            confidence=confidence,
            lifecycle=lifecycle,
            evidence_refs=refs,
        )
        return self._store.put(updated, source=evidence_ref)

    def decay(
        self,
        pattern: HabitPattern,
        *,
        now: datetime,
    ) -> HabitPattern:
        current = self._utc(now)
        confidence = HabitConfidence.score(
            support_count=pattern.support_count,
            contradiction_count=pattern.contradiction_count,
            observable_count=pattern.observable_count,
            last_seen=pattern.last_seen,
            now=current,
        )
        lifecycle = HabitConfidence.lifecycle(
            confidence=confidence,
            support_count=pattern.support_count,
        )
        if confidence < 0.10 and pattern.support_count:
            lifecycle = HabitLifecycle.RETIRED
        updated = replace(
            pattern,
            confidence=confidence,
            lifecycle=lifecycle,
        )
        return self._store.put(
            updated,
            source=f"habit-decay:{current.isoformat()}",
        )

    def suppress(
        self,
        *,
        pattern: HabitPattern,
        signature: str,
        reason: str,
        evidence_ref: str,
        created_at: datetime,
    ) -> HabitSuppression:
        current = self._utc(created_at)
        suppression = HabitSuppression(
            suppression_id=str(uuid5(
                NAMESPACE_URL,
                f"sofia-habit-suppression:{pattern.principal_id}:"
                f"{pattern.audience_id}:{signature}:{evidence_ref}",
            )),
            principal_id=pattern.principal_id,
            audience_id=pattern.audience_id,
            signature=signature,
            reason=reason,
            evidence_ref=evidence_ref,
            created_at=current,
        )
        self._store.suppress(suppression)
        self._store.put(
            replace(pattern, lifecycle=HabitLifecycle.SUPPRESSED),
            source=evidence_ref,
        )
        return suppression
