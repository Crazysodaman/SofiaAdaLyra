"""Regression coverage for contextual embodied-expression planning."""
from sofia.cognition.matrix import (
    EmbodiedExpressionPlanner,
    InfluenceSignal,
)
from sofia.personality.influence import ContinuityInfluence


def _influence(
    *,
    emotion: str | None = None,
    intensity: float = 0.0,
    daypart: str = "unknown",
    weather: str | None = None,
) -> ContinuityInfluence:
    return ContinuityInfluence(
        daypart=daypart,
        season=None,
        daylight=None,
        weather_condition=weather,
        temperature_c=None,
        weather_freshness="current" if weather else None,
        location_freshness="current" if weather else None,
        primary_emotion_evidence_refs=(
            ("emotion:event-1",) if emotion is not None else ()
        ),
        emotional_tone="positive" if emotion is not None else "settled",
        primary_emotion=emotion,
        primary_intensity=intensity,
        active_emotions=(() if emotion is None else (emotion,)),
        foreground_emotion_evidence_refs=(
            ("emotion:event-1",) if emotion is not None else ()
        ),
        foreground_emotion=emotion,
        foreground_intensity=intensity,
        daypart_evidence_refs=(
            ("runtime.clock",) if daypart != "unknown" else ()
        ),
        season_evidence_refs=(),
        weather_evidence_refs=(
            ("environment.weather:test",) if weather else ()
        ),
    )


def test_expression_plan_uses_existing_conversation_expression_matrix():
    planner = EmbodiedExpressionPlanner()
    influence = _influence(
        emotion="curiosity",
        intensity=0.55,
        daypart="afternoon",
    )

    plan = planner.plan(
        message_id="message-1",
        influence=influence,
    )

    assert plan.primary in {
        "ear-perk",
        "shift-posture",
        "pause",
        "grin",
    }
    assert "emotion" in plan.active_signals
    assert "daypart" in plan.active_signals
    assert plan.intensity == "moderate"


def test_expression_plan_avoids_recently_narrated_semantic():
    planner = EmbodiedExpressionPlanner()
    influence = _influence(
        emotion="curiosity",
        intensity=0.55,
        daypart="afternoon",
    )

    plan = planner.plan(
        message_id="message-2",
        influence=influence,
        recent_assistant_messages=(
            "*Her ears perk as she leans toward the screen.*",
        ),
    )

    assert "ear-perk" in plan.avoid_recent
    assert plan.primary != "ear-perk"


def test_expression_plan_weather_only_is_expression_not_emotion():
    planner = EmbodiedExpressionPlanner()
    influence = _influence(
        daypart="unknown",
        weather="Light rain",
    )

    plan = planner.plan(
        message_id="message-rain",
        influence=influence,
    )

    assert plan.primary in {"tail-curl", "speak-softly"}
    assert InfluenceSignal.WEATHER.value in plan.active_signals
    assert InfluenceSignal.EMOTION.value not in plan.active_signals


def test_expression_plan_can_remain_still_without_grounded_context():
    planner = EmbodiedExpressionPlanner()

    plan = planner.plan(
        message_id="message-still",
        influence=_influence(),
    )

    assert plan.primary is None
    assert plan.alternates == ()
    assert plan.active_signals == ()
    assert "No specific expression cue is required this turn." in plan.prompt()


def test_expression_prompt_preserves_representation_and_authority_boundary():
    planner = EmbodiedExpressionPlanner()
    plan = planner.plan(
        message_id="message-3",
        influence=_influence(
            emotion="playfulness",
            intensity=0.8,
            daypart="evening",
        ),
    )

    prompt = plan.prompt().lower()
    assert "representational expression is not evidence of physical sensation" in prompt
    assert "cannot override" in prompt
    assert "avoid repeating these recently used expression families" in prompt
    assert "a fitting brief expression, if useful" in prompt
    assert "planner reason" not in prompt
    assert "active contextual influence signals" not in prompt
