"""Representative AVATAR/OUTFIT behavior matrix over shared context."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.avatar.wardrobe_planner import wardrobe_emotion_influences
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_planner import (
    Activity, OutfitPlanner, Season, WardrobeContext, Weather, WeatherObservation,
)
from sofia.emotion.journal import ActiveEmotion, CurrentEmotionalState
from sofia.personality.influence import ContinuityInfluence


UTC = timezone.utc
DAY = datetime(2026, 7, 15, 14, 0, tzinfo=UTC)
NIGHT = datetime(2026, 7, 15, 22, 30, tzinfo=UTC)


def planner():
    catalog = build_starter_wardrobe()
    return OutfitPlanner(catalog.wardrobe, catalog.presets)


def influence(emotion: str | None = None, intensity: float = 0.0):
    active = () if emotion is None else (
        ActiveEmotion(
            name=emotion,
            intensity=intensity,
            evidence_refs=("matrix:emotion",),
            event_ids=("matrix:event",),
        ),
    )
    state = CurrentEmotionalState(
        as_of=DAY,
        subject="Sparks",
        tone="positive" if active else "neutral",
        active=active,
    )
    return ContinuityInfluence.from_state(emotion=state, environment=None)


def test_daytime_without_weather_keeps_canonical_engineer_outfit():
    result = planner().suggest(
        WardrobeContext(DAY, Season.SUMMER, Activity.CONVERSATION)
    )
    assert result.outfit_id == "engineer.signature"


def test_current_hot_weather_selects_lighter_engineer_outfit():
    weather = WeatherObservation(
        Weather.HOT, DAY - timedelta(minutes=5), "matrix.weather"
    )
    result = planner().suggest(
        WardrobeContext(
            DAY, Season.SUMMER, Activity.CONVERSATION, weather=weather
        )
    )
    assert result.outfit_id == "engineer.light"


def test_stale_hot_weather_cannot_select_weather_specialized_outfit():
    weather = WeatherObservation(
        Weather.HOT, DAY - timedelta(hours=7), "matrix.weather"
    )
    result = planner().suggest(
        WardrobeContext(
            DAY, Season.SUMMER, Activity.CONVERSATION, weather=weather
        )
    )
    assert result.outfit_id == "engineer.signature"
    assert "weather_missing_or_stale" in result.reasons


def test_late_night_context_selects_lounge_even_in_summer():
    result = planner().suggest(
        WardrobeContext(NIGHT, Season.SUMMER, Activity.CONVERSATION)
    )
    assert result.outfit_id == "lounge.relaxed"


def test_grounded_fondness_can_nudge_lounge_without_overriding_activity():
    emotion = wardrobe_emotion_influences(influence("fondness", 1.0))
    conversation = planner().suggest(
        WardrobeContext(
            DAY, Season.AUTUMN, Activity.CONVERSATION,
            emotion_influences=emotion,
        )
    )
    engineering = planner().suggest(
        WardrobeContext(
            DAY, Season.AUTUMN, Activity.ENGINEERING,
            emotion_influences=emotion,
        )
    )

    assert conversation.outfit_id == "lounge.relaxed"
    assert "modeled_emotion_influence" in conversation.reasons
    assert engineering.outfit_id == "engineer.signature"



def test_season_is_a_hard_compatibility_constraint_not_an_emotion_score():
    catalog = build_starter_wardrobe()
    spring_only = (
        catalog.preset("seasonal.spring.normal.01"),
    )
    planner = OutfitPlanner(catalog.wardrobe, spring_only)

    with pytest.raises(WardrobeError, match="season"):
        planner.suggest(
            WardrobeContext(
                DAY,
                Season.WINTER,
                Activity.CONVERSATION,
                emotion_influences=wardrobe_emotion_influences(
                    influence("fondness", 1.0)
                ),
            )
        )


def test_private_outfits_are_never_automatic_even_at_night_with_emotion():
    catalog = build_starter_wardrobe()
    result = OutfitPlanner(
        catalog.wardrobe,
        catalog.presets,
    ).suggest(
        WardrobeContext(
            NIGHT,
            Season.WINTER,
            Activity.CONVERSATION,
            emotion_influences=wardrobe_emotion_influences(
                influence("fondness", 1.0)
            ),
        )
    )
    selected = catalog.preset(result.outfit_id)
    assert selected.private_only is False
    assert not catalog.wardrobe.selection(selected.item_ids).private_only
