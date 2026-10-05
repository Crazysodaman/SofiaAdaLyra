"""Behavior policy tests for the Contextual Influence Matrix."""
from __future__ import annotations

from dataclasses import replace

import pytest

from sofia.cognition.matrix import (
    ContextualInfluenceMatrix,
    InfluenceMode,
    InfluenceSignal,
    InfluenceSurface,
)
from sofia.personality.influence import ContinuityInfluence


def influence() -> ContinuityInfluence:
    return ContinuityInfluence(
        daypart="evening",
        season="autumn",
        daylight="night",
        weather_condition="rainy",
        temperature_c=12.0,
        weather_freshness="current",
        location_freshness="current",
        primary_emotion_evidence_refs=("emotion:event-1",),
        emotional_tone="warm",
        primary_emotion="fondness",
        primary_intensity=0.62,
        active_emotions=("fondness", "curiosity"),
        foreground_emotion_evidence_refs=("emotion:event-2",),
        foreground_emotion="curiosity",
        foreground_intensity=0.55,
        daypart_evidence_refs=("runtime.clock", "environment.location:configured"),
        season_evidence_refs=("runtime.clock", "environment.location:configured"),
        weather_evidence_refs=("environment.weather:matrix-weather",),
    )


def test_auto_outfit_uses_all_four_signals_with_bounded_strengths():
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.AUTO_OUTFIT,
        influence(),
    )

    assert plan.mode_for(InfluenceSignal.EMOTION) is InfluenceMode.BOUNDED_BIAS
    assert plan.mode_for(InfluenceSignal.WEATHER) is InfluenceMode.STRONG_PREFERENCE
    assert plan.mode_for(InfluenceSignal.DAYPART) is InfluenceMode.STRONG_PREFERENCE
    assert plan.mode_for(InfluenceSignal.SEASON) is InfluenceMode.HARD_COMPATIBILITY


def test_requested_wardrobe_change_is_contextual_but_not_user_authority():
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.WARDROBE_REQUEST_AUTONOMY,
        influence(),
    )

    assert plan.mode_for(InfluenceSignal.EMOTION) is InfluenceMode.BOUNDED_BIAS
    assert plan.mode_for(InfluenceSignal.WEATHER) is InfluenceMode.STRONG_PREFERENCE
    assert plan.mode_for(InfluenceSignal.DAYPART) is InfluenceMode.BOUNDED_BIAS
    assert plan.mode_for(InfluenceSignal.SEASON) is InfluenceMode.HARD_COMPATIBILITY


def test_interaction_willingness_only_allows_modeled_emotion_to_bias_choice():
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.INTERACTION_WILLINGNESS,
        influence(),
    )

    assert plan.mode_for(InfluenceSignal.EMOTION) is InfluenceMode.BOUNDED_BIAS
    assert plan.mode_for(InfluenceSignal.WEATHER) is InfluenceMode.NONE
    assert plan.mode_for(InfluenceSignal.DAYPART) is InfluenceMode.NONE
    assert plan.mode_for(InfluenceSignal.SEASON) is InfluenceMode.NONE


def test_interaction_expression_may_use_ambient_context_without_changing_willingness():
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.INTERACTION_EXPRESSION,
        influence(),
    )

    assert plan.mode_for(InfluenceSignal.EMOTION) is InfluenceMode.BOUNDED_BIAS
    assert plan.mode_for(InfluenceSignal.WEATHER) is InfluenceMode.EXPRESSION_ONLY
    assert plan.mode_for(InfluenceSignal.DAYPART) is InfluenceMode.EXPRESSION_ONLY
    assert plan.mode_for(InfluenceSignal.SEASON) is InfluenceMode.EXPRESSION_ONLY


@pytest.mark.parametrize(
    "surface",
    (
        InfluenceSurface.TOOL_AUTHORITY,
        InfluenceSurface.SAFE_POLICY,
        InfluenceSurface.RELEASE_VERIFY,
        InfluenceSurface.FLEET_AUTHORITY,
        InfluenceSurface.BODY_SAFETY,
    ),
)
def test_truth_authority_and_safety_surfaces_ignore_all_contextual_signals(surface):
    plan = ContextualInfluenceMatrix().plan(surface, influence())

    assert {
        decision.signal: decision.mode
        for decision in plan.decisions
    } == {
        signal: InfluenceMode.NONE
        for signal in InfluenceSignal
    }


def test_stale_weather_is_removed_even_when_surface_would_allow_it():
    stale = replace(
        influence(),
        weather_condition=None,
        temperature_c=None,
        weather_freshness="stale",
    )
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.REFLECTION,
        stale,
    )

    assert plan.mode_for(InfluenceSignal.WEATHER) is InfluenceMode.NONE
    assert "not fresh" in plan.decision_for(InfluenceSignal.WEATHER).reason


def test_future_weather_is_removed_even_when_a_condition_string_is_present():
    future = replace(
        influence(),
        weather_freshness="future",
    )
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.UI_THEME,
        future,
    )

    assert plan.mode_for(InfluenceSignal.WEATHER) is InfluenceMode.NONE


def test_missing_grounded_season_is_not_guessed():
    unknown = replace(influence(), season=None)
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.AUTO_OUTFIT,
        unknown,
    )

    assert plan.mode_for(InfluenceSignal.SEASON) is InfluenceMode.NONE
    assert "unavailable" in plan.decision_for(InfluenceSignal.SEASON).reason


def test_unknown_daypart_is_not_inferred_by_the_matrix():
    unknown = replace(influence(), daypart="unknown")
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.CONVERSATION_EXPRESSION,
        unknown,
    )

    assert plan.mode_for(InfluenceSignal.DAYPART) is InfluenceMode.NONE


def test_emotion_requires_evidence_linkage_before_it_can_influence_behavior():
    unsupported = replace(
        influence(),
        primary_emotion_evidence_refs=(),
    )
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.INTERACTION_WILLINGNESS,
        unsupported,
    )

    assert plan.mode_for(InfluenceSignal.EMOTION) is InfluenceMode.NONE
    assert "evidence-linked" in plan.decision_for(InfluenceSignal.EMOTION).reason


def test_background_relational_emotion_can_subtly_influence_expression():
    relational = replace(
        influence(),
        foreground_emotion=None,
        foreground_intensity=0.0,
        foreground_emotion_evidence_refs=(),
    )
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.CONVERSATION_EXPRESSION,
        relational,
    )

    decision = plan.decision_for(InfluenceSignal.EMOTION)
    assert decision.mode is InfluenceMode.BOUNDED_BIAS
    assert decision.evidence_refs == ("emotion:event-1",)
    assert "subtle expression" in decision.reason


def test_habit_learning_never_uses_sofias_transient_emotion_as_user_habit_evidence():
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.HABIT_LEARNING,
        influence(),
    )

    assert plan.mode_for(InfluenceSignal.EMOTION) is InfluenceMode.NONE
    assert plan.mode_for(InfluenceSignal.WEATHER) is InfluenceMode.BOUNDED_BIAS
    assert plan.mode_for(InfluenceSignal.DAYPART) is InfluenceMode.BOUNDED_BIAS
    assert plan.mode_for(InfluenceSignal.SEASON) is InfluenceMode.BOUNDED_BIAS


def test_outreach_salience_does_not_gain_direct_seasonal_pressure():
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.OUTREACH_SALIENCE,
        influence(),
    )

    assert plan.mode_for(InfluenceSignal.SEASON) is InfluenceMode.NONE
    assert plan.mode_for(InfluenceSignal.WEATHER) is InfluenceMode.BOUNDED_BIAS


def test_active_influences_expose_provenance_and_freshness_diagnostics():
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.AUTO_OUTFIT,
        influence(),
    )

    weather = plan.decision_for(InfluenceSignal.WEATHER)
    assert weather.evidence_refs == ("environment.weather:matrix-weather",)
    assert weather.freshness == "current"

    daypart_decision = plan.decision_for(InfluenceSignal.DAYPART)
    assert "runtime.clock" in daypart_decision.evidence_refs
    assert daypart_decision.freshness == "current"

    season_decision = plan.decision_for(InfluenceSignal.SEASON)
    assert "environment.location:configured" in season_decision.evidence_refs
    assert season_decision.freshness == "grounded"


@pytest.mark.parametrize(
    ("signal", "field"),
    (
        (InfluenceSignal.WEATHER, "weather_evidence_refs"),
        (InfluenceSignal.DAYPART, "daypart_evidence_refs"),
        (InfluenceSignal.SEASON, "season_evidence_refs"),
    ),
)
def test_environment_influence_fails_closed_without_provenance(signal, field):
    unsupported = replace(influence(), **{field: ()})
    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.AUTO_OUTFIT,
        unsupported,
    )

    assert plan.mode_for(signal) is InfluenceMode.NONE



def test_background_relational_emotion_styles_outfit_and_subtly_colors_expression():
    background_only = replace(
        influence(),
        active_emotions=("fondness",),
        foreground_emotion_evidence_refs=(),
        foreground_emotion=None,
        foreground_intensity=0.0,
    )

    conversation = ContextualInfluenceMatrix().plan(
        InfluenceSurface.CONVERSATION_EXPRESSION,
        background_only,
    )
    outfit = ContextualInfluenceMatrix().plan(
        InfluenceSurface.AUTO_OUTFIT,
        background_only,
    )

    assert conversation.mode_for(InfluenceSignal.EMOTION) is InfluenceMode.BOUNDED_BIAS
    assert "subtle expression" in conversation.decision_for(
        InfluenceSignal.EMOTION
    ).reason
    assert outfit.mode_for(InfluenceSignal.EMOTION) is InfluenceMode.BOUNDED_BIAS
