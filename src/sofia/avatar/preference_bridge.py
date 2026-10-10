"""Adapt general reviewed taste records into existing wardrobe evidence."""
from __future__ import annotations

from hashlib import sha256

from sofia.personality.preferences import (
    PreferenceDisposition, PreferenceRegistry, PreferenceSubject,
)

from .wardrobe_planner import (
    Preference, PreferenceActor, PreferenceTarget, Sentiment,
)


_CATEGORY_TARGET = {
    "wardrobe.outfit": PreferenceTarget.OUTFIT,
    "wardrobe.item": PreferenceTarget.ITEM,
}


def wardrobe_preferences_from_registry(
    registry: PreferenceRegistry, *, audience_id: str, context: str,
) -> tuple[Preference, ...]:
    values = []
    sentiment = {
        PreferenceDisposition.LIKE: Sentiment.LIKE,
        PreferenceDisposition.FAVORITE: Sentiment.LOVE,
        PreferenceDisposition.DISLIKE: Sentiment.DISLIKE,
        PreferenceDisposition.STRONG_AVERSION: Sentiment.HATE,
    }
    for subject, actor in (
        (PreferenceSubject.SOFIA, PreferenceActor.SOFIA),
        (PreferenceSubject.SPARKS, PreferenceActor.SPARKS),
    ):
        for category, target in _CATEGORY_TARGET.items():
            records = registry.latest_for_category(
                subject=subject, category=category, context=context,
                audience_id=audience_id,
            )
            for record in records:
                mapped = sentiment.get(record.disposition)
                if mapped is None or record.confidence < 0.6:
                    continue
                source_id = "pref:" + sha256(
                    record.preference_id.encode("utf-8")
                ).hexdigest()[:24]
                values.append(Preference(
                    actor, target, (record.target_id,), mapped, source_id, True,
                ))
    return tuple(values)
