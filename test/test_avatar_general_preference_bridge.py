from datetime import datetime, timezone

import pytest

from sofia.avatar.preference_bridge import wardrobe_preferences_from_registry
from sofia.avatar.wardrobe_planner import PreferenceActor, Sentiment
from sofia.personality.preferences import (
    PreferenceDisposition, PreferenceRegistry, PreferenceSubject,
)


NOW = datetime(2026, 10, 10, 14, tzinfo=timezone.utc)
pytestmark = [pytest.mark.pkg_avatar, pytest.mark.pkg_core]


def record(registry, *, subject, target, disposition, confidence=.9):
    registry.revise(
        subject=subject, category="wardrobe.outfit", target_id=target,
        context="conversation", disposition=disposition, strength=.8,
        confidence=confidence, reason="Reviewed outfit choice history.",
        evidence_ref=f"wardrobe:{subject.value}:{target}",
        audience_id="local:text", expected_revision=None, now=NOW,
    )


def test_general_preferences_influence_wardrobe_only_when_reviewed_and_confident(tmp_path):
    registry = PreferenceRegistry(tmp_path / "sofia.db")
    record(
        registry, subject=PreferenceSubject.SOFIA, target="engineer",
        disposition=PreferenceDisposition.FAVORITE,
    )
    record(
        registry, subject=PreferenceSubject.SPARKS, target="formal",
        disposition=PreferenceDisposition.DISLIKE,
    )
    record(
        registry, subject=PreferenceSubject.SOFIA, target="casual",
        disposition=PreferenceDisposition.LIKE, confidence=.2,
    )
    values = wardrobe_preferences_from_registry(
        registry, audience_id="local:text", context="conversation",
    )
    assert {(item.actor, item.ids, item.sentiment) for item in values} == {
        (PreferenceActor.SOFIA, ("engineer",), Sentiment.LOVE),
        (PreferenceActor.SPARKS, ("formal",), Sentiment.DISLIKE),
    }
    assert all(item.reviewed for item in values)


def test_general_preferences_do_not_cross_audience_or_context(tmp_path):
    registry = PreferenceRegistry(tmp_path / "sofia.db")
    record(
        registry, subject=PreferenceSubject.SOFIA, target="engineer",
        disposition=PreferenceDisposition.FAVORITE,
    )
    assert wardrobe_preferences_from_registry(
        registry, audience_id="public", context="conversation",
    ) == ()
    assert wardrobe_preferences_from_registry(
        registry, audience_id="local:text", context="formal",
    ) == ()
