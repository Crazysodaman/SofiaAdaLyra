"""Bounded taste influence for already eligible world/decorating choices."""
from __future__ import annotations

from dataclasses import dataclass

from sofia.personality.preferences import (
    PreferenceDisposition, PreferenceRegistry, PreferenceSubject,
)


@dataclass(frozen=True, slots=True)
class RankedWorldChoice:
    target_id: str
    score: int
    evidence_refs: tuple[str, ...]


class WorldPreferencePolicy:
    _SCORES = {
        PreferenceDisposition.FAVORITE: 2,
        PreferenceDisposition.LIKE: 1,
        PreferenceDisposition.INDIFFERENT: 0,
        PreferenceDisposition.UNKNOWN: 0,
        PreferenceDisposition.DISLIKE: -1,
        PreferenceDisposition.STRONG_AVERSION: -2,
    }

    def __init__(self, registry: PreferenceRegistry) -> None:
        if not isinstance(registry, PreferenceRegistry):
            raise TypeError("registry must be PreferenceRegistry")
        self.registry = registry

    def rank(
        self, candidates: tuple[str, ...], *, category: str, context: str,
        audience_id: str,
    ) -> tuple[RankedWorldChoice, ...]:
        """Rank only caller-eligible IDs; taste never creates authority."""
        if not isinstance(candidates, tuple) or len(set(candidates)) != len(candidates):
            raise ValueError("eligible candidates must be a unique tuple")
        records = self.registry.latest_for_category(
            subject=PreferenceSubject.SOFIA, category=category,
            context=context, audience_id=audience_id,
        )
        by_target = {
            item.target_id: item for item in records if item.confidence >= 0.6
        }
        ranked = []
        for target in candidates:
            record = by_target.get(target)
            ranked.append(RankedWorldChoice(
                target, 0 if record is None else self._SCORES[record.disposition],
                () if record is None else (record.evidence_ref,),
            ))
        return tuple(sorted(ranked, key=lambda item: (-item.score, item.target_id)))
