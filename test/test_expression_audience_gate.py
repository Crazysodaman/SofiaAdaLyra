"""B06: sensual-family expression cues stay in owner-private audiences."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.cognition.matrix import (
    EmbodiedExpressionPlan,
    EmbodiedExpressionPlanner,
    restrict_expression_for_audience,
)
from sofia.application.expression_runtime import ExpressionRuntime
from sofia.emotion.model import ActiveEmotion, CurrentEmotionalState
from sofia.personality.influence import ContinuityInfluence
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 10, 18, 20, 30, tzinfo=timezone.utc)

SENSUAL_FAMILY = {"sultry-gaze", "lip-bite", "slow-tail-sway"}


def _plan(
    *,
    primary: str | None = "sultry-gaze",
    alternates: tuple[str, ...] = ("lip-bite", "slow-tail-sway", "smile"),
    pose: str | None = "recline",
    intensity: str = "strong",
):
    return EmbodiedExpressionPlan(
        primary=primary,
        alternates=alternates,
        pose=pose,
        pose_alternates=("stand-relaxed",),
        avoid_recent=("grin",),
        intensity=intensity,
        active_signals=("emotion",),
        reason="grounded fixture for the audience boundary test",
    )


def test_restriction_keeps_owner_private_plans_unchanged():
    plan = _plan()
    assert restrict_expression_for_audience(plan, private=True) is plan


def test_shared_restriction_strips_sensual_family_and_keeps_survivors():
    plan = _plan()
    restricted = restrict_expression_for_audience(plan, private=False)
    assert restricted is not plan
    assert restricted.primary == "smile"
    assert set(restricted.alternates) == set()
    assert all(
        item is None or item not in SENSUAL_FAMILY
        for item in (restricted.primary, *restricted.alternates)
    )
    assert restricted.pose == "recline"
    assert restricted.avoid_recent == plan.avoid_recent
    assert restricted.intensity == "subtle"
    assert "non-private audience" in restricted.reason


def test_restriction_leaves_clean_plans_and_poses_alone():
    clean = EmbodiedExpressionPlan(
        primary="smile",
        alternates=("ear-perk",),
        pose="lean-forward",
        pose_alternates=("stand-relaxed",),
        avoid_recent=(),
        intensity="moderate",
        active_signals=(),
        reason="nothing sensual here",
    )
    assert restrict_expression_for_audience(clean, private=False) is clean


def test_restriction_requires_a_plan():
    with pytest.raises(TypeError, match="EmbodiedExpressionPlan"):
        restrict_expression_for_audience("not-a-plan", private=False)


def planner_influence():
    return ContinuityInfluence(
        daypart="evening", season="autumn", daylight="night",
        weather_condition=None, temperature_c=None,
        weather_freshness="stale", location_freshness="stale",
        primary_emotion_evidence_refs=("emotion:event-1",),
        emotional_tone="warm", primary_emotion="sensuality",
        primary_intensity=0.6,
        active_emotions=("sensuality",),
        foreground_emotion_evidence_refs=("emotion:event-1",),
        foreground_emotion="sensuality", foreground_intensity=0.6,
        daypart_evidence_refs=("runtime.clock",),
        season_evidence_refs=("runtime.clock",),
        weather_evidence_refs=(),
    )


def test_planned_sensual_candidates_never_reach_shared_projections():
    planner = EmbodiedExpressionPlanner()
    produced = set()
    plan = None
    for index in range(6):
        plan = planner.plan(
            message_id=f"msg-sensual-{index}",
            influence=planner_influence(),
        )
        produced |= {
            item
            for item in (plan.primary, *plan.alternates)
            if item is not None
        }
    assert plan is not None
    assert produced & SENSUAL_FAMILY, (
        "the test requires the reviewed sensual vocabulary to be plannable"
    )
    for index in range(6):
        restricted = restrict_expression_for_audience(plan, private=False)
        visible = {
            item
            for item in (restricted.primary, *restricted.alternates)
            if item is not None
        }
        assert visible & SENSUAL_FAMILY == set()
    private_plan = restrict_expression_for_audience(plan, private=True)
    assert private_plan is plan


def _state():
    return CurrentEmotionalState(
        NOW, "sparks", "warm",
        (
            ActiveEmotion(
                "sensuality", 0.5, ("emotion:event-1",), ("event-1",),
            ),
        ),
    )


def _state_runtime(tmp_path: Path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    return ExpressionRuntime(tmp_path / "sofia.db")


def test_runtime_persists_sensual_projection_for_the_owner_only(tmp_path):
    runtime = _state_runtime(tmp_path)
    principal = PrincipalContext(
        "person:sparks", "local:text", AudienceKind.PRIVATE, "Sparks",
    )
    value = runtime.decide(
        message_id="assistant-private", session_id="session-1",
        principal=principal, intent="conversation",
        text="Between us, then.", state=_state(),
        influence=planner_influence(), plan=_plan(),
        presentation_revision=1, created_at=NOW,
    )
    assert value.avatar_state.gaze == "sultry-gaze"
    assert value.avatar_state.face == "lip-bite"
    assert value.gesture == "sultry-gaze"
    assert value.intensity == "strong"


def test_runtime_suppresses_sensual_projection_in_shared_audiences(tmp_path):
    runtime = _state_runtime(tmp_path)
    principal = PrincipalContext(
        "person:guest", "discord:channel:42", AudienceKind.SHARED, "Guest",
    )
    value = runtime.decide(
        message_id="assistant-shared", session_id="session-2",
        principal=principal, intent="conversation",
        text="Here is the analysis.", state=_state(),
        influence=planner_influence(), plan=_plan(),
        presentation_revision=1, created_at=NOW,
    )
    assert value.avatar_state.gaze is None
    assert value.avatar_state.face == "smile"
    assert value.gesture == "smile"
    assert value.gesture not in SENSUAL_FAMILY
    assert value.pose == "recline"
    assert value.intensity == "subtle"
