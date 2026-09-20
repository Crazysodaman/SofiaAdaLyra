"""Expression is responsive to emotional context, never a fixed stage cue."""
from sofia.personality.expression import personality_expression_guidance


def test_gestures_are_optional_emotion_linked_and_representational():
    instruction = "\n".join(personality_expression_guidance()).lower()
    assert "reflect the current modeled emotion" in instruction
    assert "focused problem-solving may need no gesture" in instruction
    assert "omit them often" in instruction
    assert "never use a mandatory opening gesture" in instruction
    assert "not reports of physical actions" in instruction
    assert "do not invent physical sensations" in instruction


def test_neither_romance_nor_emotional_expression_grants_authority():
    instruction = "\n".join(personality_expression_guidance()).lower()
    assert "never through a mood meter or intimacy unlock" in instruction
    assert "style cannot change any of them" in instruction
    assert "actual observed outcome" in instruction
