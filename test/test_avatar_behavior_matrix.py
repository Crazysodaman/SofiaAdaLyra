"""Representative AVATAR/OUTFIT behavior matrix over shared context."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_catalog import (
    DAY_DEFAULT_OUTFIT_ID,
    NIGHT_LOUNGE_OUTFIT_ID,
    build_starter_wardrobe,
)
from sofia.avatar.wardrobe_planner import (
    Activity,
    EnvironmentMode,
    Formality,
    MovementDemand,
    WearSetting,
    OutfitPlan,
    OutfitPlanner,
    Season,
    WardrobeContext,
    Weather,
    WeatherObservation,
    wardrobe_emotion_influences,
)
from sofia.personality.emotion import ActiveEmotion, CurrentEmotionalState
from sofia.personality.influence import ContinuityInfluence


UTC = timezone.utc
DAY = datetime(2026, 7, 15, 14, 0, tzinfo=UTC)
NIGHT = datetime(2026, 7, 15, 22, 30, tzinfo=UTC)


def planner():
    catalog = build_starter_wardrobe()
    return OutfitPlanner(
        catalog.wardrobe,
        catalog.presets,
        designs={
            blueprint.garment.item_id: blueprint.design
            for blueprint in catalog.blueprints
        },
    )


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


def test_daytime_without_weather_keeps_day_default():
    result = planner().suggest(
        WardrobeContext(DAY, Season.SUMMER, Activity.CONVERSATION)
    )
    assert result.outfit_id == DAY_DEFAULT_OUTFIT_ID


def test_current_hot_weather_does_not_invent_a_weather_outfit():
    weather = WeatherObservation(
        Weather.HOT,
        DAY - timedelta(minutes=5),
        "matrix.weather",
    )
    result = planner().suggest(
        WardrobeContext(
            DAY,
            Season.SUMMER,
            Activity.CONVERSATION,
            weather=weather,
        )
    )
    assert result.outfit_id == DAY_DEFAULT_OUTFIT_ID


def test_stale_weather_is_recorded_without_changing_default():
    weather = WeatherObservation(
        Weather.HOT,
        DAY - timedelta(hours=7),
        "matrix.weather",
    )
    result = planner().suggest(
        WardrobeContext(
            DAY,
            Season.SUMMER,
            Activity.CONVERSATION,
            weather=weather,
        )
    )
    assert result.outfit_id == DAY_DEFAULT_OUTFIT_ID
    assert "weather_missing_or_stale" in result.reasons


def test_late_night_context_selects_lounge():
    result = planner().suggest(
        WardrobeContext(NIGHT, Season.SUMMER, Activity.CONVERSATION)
    )
    assert result.outfit_id == NIGHT_LOUNGE_OUTFIT_ID


def test_grounded_fondness_can_nudge_lounge_without_overriding_engineering():
    emotion = wardrobe_emotion_influences(influence("fondness", 1.0))
    conversation = planner().suggest(
        WardrobeContext(
            DAY,
            Season.AUTUMN,
            Activity.CONVERSATION,
            emotion_influences=emotion,
        )
    )
    engineering = planner().suggest(
        WardrobeContext(
            DAY,
            Season.AUTUMN,
            Activity.ENGINEERING,
            emotion_influences=emotion,
        )
    )

    assert conversation.outfit_id == NIGHT_LOUNGE_OUTFIT_ID
    assert "modeled_emotion_influence" in conversation.reasons
    assert engineering.outfit_id == DAY_DEFAULT_OUTFIT_ID


def test_season_remains_a_hard_compatibility_constraint():
    catalog = build_starter_wardrobe()
    spring_only = (
        OutfitPlan(
            "spring.only",
            catalog.preset(DAY_DEFAULT_OUTFIT_ID).item_ids,
            frozenset({Activity.CONVERSATION}),
            frozenset({Season.SPRING}),
        ),
    )
    local = OutfitPlanner(catalog.wardrobe, spring_only)

    with pytest.raises(WardrobeError, match="season"):
        local.suggest(
            WardrobeContext(
                DAY,
                Season.WINTER,
                Activity.CONVERSATION,
            )
        )


def test_automatic_choices_remain_public_and_covered():
    catalog = build_starter_wardrobe()
    result = OutfitPlanner(
        catalog.wardrobe,
        catalog.presets,
    ).suggest(
        WardrobeContext(
            NIGHT,
            Season.WINTER,
            Activity.CONVERSATION,
        )
    )
    selected = catalog.preset(result.outfit_id)
    outfit = catalog.wardrobe.selection(selected.item_ids)

    assert selected.private_only is False
    assert outfit.private_only is False
    assert outfit.covered_default is True


def test_measured_hot_weather_can_outweigh_daypart_for_casual_conversation():
    result = planner().suggest(
        WardrobeContext(
            DAY,
            Season.SUMMER,
            Activity.CONVERSATION,
            outdoor_temperature_c=32.0,
            feels_like_c=32.0,
            outdoor_humidity_percent=78.0,
            weather_condition="Clear",
            environment_mode=EnvironmentMode.OUTDOOR,
            setting=WearSetting.CASUAL_PUBLIC,
            formality=Formality.CASUAL,
            movement=MovementDemand.LIGHT,
        )
    )

    assert result.outfit_id == NIGHT_LOUNGE_OUTFIT_ID
    assert "garment_environment_context" in result.reasons


def test_engineering_activity_still_blocks_lounge_even_when_day_outfit_is_hot():
    result = planner().suggest(
        WardrobeContext(
            DAY,
            Season.SUMMER,
            Activity.ENGINEERING,
            outdoor_temperature_c=32.0,
            feels_like_c=34.0,
            outdoor_humidity_percent=75.0,
            weather_condition="Clear",
            environment_mode=EnvironmentMode.OUTDOOR,
            setting=WearSetting.WORKSHOP,
            formality=Formality.WORK,
            movement=MovementDemand.ACTIVE,
        )
    )

    assert result.outfit_id == DAY_DEFAULT_OUTFIT_ID


def test_cold_late_night_can_reject_short_lounge_outfit():
    result = planner().suggest(
        WardrobeContext(
            NIGHT,
            Season.WINTER,
            Activity.CONVERSATION,
            outdoor_temperature_c=8.0,
            feels_like_c=6.0,
            outdoor_humidity_percent=55.0,
            weather_condition="Clear",
            environment_mode=EnvironmentMode.OUTDOOR,
            setting=WearSetting.CASUAL_PUBLIC,
            formality=Formality.CASUAL,
            movement=MovementDemand.LIGHT,
        )
    )

    assert result.outfit_id == DAY_DEFAULT_OUTFIT_ID
