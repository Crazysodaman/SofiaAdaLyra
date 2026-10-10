from datetime import datetime, timezone

import pytest

from sofia.interaction.world_preferences import WorldPreferencePolicy
from sofia.personality.preferences import (
    PreferenceDisposition, PreferenceRegistry, PreferenceSubject,
)


NOW = datetime(2026, 10, 10, 15, tzinfo=timezone.utc)
pytestmark = [pytest.mark.pkg_interact, pytest.mark.pkg_core]


def test_preferences_rank_only_prevalidated_world_choices(tmp_path):
    registry = PreferenceRegistry(tmp_path / "sofia.db")
    for target, disposition in (
        ("violet-chair", PreferenceDisposition.FAVORITE),
        ("orange-chair", PreferenceDisposition.STRONG_AVERSION),
        ("invented-chair", PreferenceDisposition.FAVORITE),
    ):
        registry.revise(
            subject=PreferenceSubject.SOFIA, category="decor.furniture",
            target_id=target, context="studio", disposition=disposition,
            strength=.9, confidence=.9, reason="Reviewed decorating choice.",
            evidence_ref=f"decor:{target}", audience_id="local:text",
            expected_revision=None, now=NOW,
        )
    ranked = WorldPreferencePolicy(registry).rank(
        ("plain-chair", "orange-chair", "violet-chair"),
        category="decor.furniture", context="studio", audience_id="local:text",
    )
    assert [(item.target_id, item.score) for item in ranked] == [
        ("violet-chair", 2), ("plain-chair", 0), ("orange-chair", -2),
    ]
    assert "invented-chair" not in {item.target_id for item in ranked}


def test_world_preference_ranking_is_audience_scoped(tmp_path):
    registry = PreferenceRegistry(tmp_path / "sofia.db")
    registry.revise(
        subject=PreferenceSubject.SOFIA, category="decor.art", target_id="fox-art",
        context="studio", disposition=PreferenceDisposition.FAVORITE,
        strength=1, confidence=1, reason="Reviewed.", evidence_ref="decor:fox-art",
        audience_id="local:text", expected_revision=None, now=NOW,
    )
    ranked = WorldPreferencePolicy(registry).rank(
        ("fox-art",), category="decor.art", context="studio", audience_id="public",
    )
    assert ranked[0].score == 0 and ranked[0].evidence_refs == ()
