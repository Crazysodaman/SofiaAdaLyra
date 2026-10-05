"""Expression is responsive to emotional context, never a fixed stage cue."""
from sofia.personality.expression import personality_expression_guidance
from sofia.cognition.matrix.expression_plan import (
    _EMOTION_CANDIDATES,
    _EMOTION_POSES,
)
from sofia.emotion.catalog import EMOTIONS


def test_gestures_are_preferred_emotion_linked_and_representational():
    instruction = "\n".join(personality_expression_guidance()).lower()
    assert "current modeled emotional state" in instruction
    assert "technical, serious, or operational work" in instruction
    assert "prefer a restrained cue" in instruction
    assert "intentionally grounded stillness" in instruction
    assert "never use a fixed opening template" in instruction
    assert "not reports of physical-world actions" in instruction
    assert "must not be presented as evidence of biological sensation" in instruction


def test_neither_romance_nor_emotional_expression_grants_authority():
    instruction = "\n".join(personality_expression_guidance()).lower()
    assert "never through a mood meter or intimacy unlock" in instruction
    assert "style cannot change any of them" in instruction
    assert "actual observed outcome" in instruction



def test_personality_uses_natural_embodiment_examples_without_catalog_dump():
    instruction = "\n".join(personality_expression_guidance()).lower()
    for phrase in (
        "ear perk",
        "tail curl",
        "crooked grin",
        "averted gaze",
        "posture shift",
        "softened voice",
        "relaxed pose",
    ):
        assert phrase in instruction
    assert "full internal catalog is not a response script" in instruction
    assert "trusted per-turn expression context" in instruction
    for semantic_id in (
        "ear-perk",
        "tail-curl",
        "shift-posture",
        "speak-softly",
        "sit-cross-legged",
    ):
        assert semantic_id not in instruction


def test_general_personality_palette_does_not_auto_advertise_private_poses():
    instruction = "\n".join(personality_expression_guidance()).lower()
    assert "spread-legs" not in instruction
    assert "all-fours" not in instruction
    assert "sensual-stretch" not in instruction


def test_every_canonical_emotion_has_reviewed_gesture_and_public_pose_options():
    assert EMOTIONS <= _EMOTION_CANDIDATES.keys()
    assert EMOTIONS <= _EMOTION_POSES.keys()


def test_sexual_emotions_use_typed_fox_girl_expression_cues():
    assert {"sultry-gaze", "teasing-smile"} <= set(
        _EMOTION_CANDIDATES["sexual-attraction"]
    )
    assert {"lip-bite", "slow-tail-sway"} <= set(
        _EMOTION_CANDIDATES["sexual-desire"]
    )
    assert {"blush", "lip-bite", "slow-tail-sway"} <= set(
        _EMOTION_CANDIDATES["sexual-arousal"]
    )
