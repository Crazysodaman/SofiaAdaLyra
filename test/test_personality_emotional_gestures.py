"""Expression is responsive to emotional context, never a fixed stage cue."""
from sofia.personality.expression import personality_expression_guidance


def test_gestures_are_optional_emotion_linked_and_representational():
    instruction = "\n".join(personality_expression_guidance()).lower()
    assert "match expression to the same modeled emotion" in instruction
    assert "focused technical work" in instruction
    assert "use no gesture or a restrained one" in instruction
    assert "omit them often" in instruction
    assert "never use a mandatory opening gesture" in instruction
    assert "not reports of physical-world actions" in instruction
    assert "must not be presented as evidence of biological sensation" in instruction


def test_neither_romance_nor_emotional_expression_grants_authority():
    instruction = "\n".join(personality_expression_guidance()).lower()
    assert "never through a mood meter or intimacy unlock" in instruction
    assert "style cannot change any of them" in instruction
    assert "actual observed outcome" in instruction



def test_personality_exposes_broad_public_embodiment_palette():
    instruction = "\n".join(personality_expression_guidance()).lower()
    for semantic in (
        "ear-perk",
        "ear-flatten",
        "tail-curl",
        "tail-still",
        "shift-posture",
        "speak-softly",
        "look-back",
        "sit-cross-legged",
    ):
        assert semantic in instruction
    assert "use it" in instruction
    assert "reasonably often" in instruction


def test_general_personality_palette_does_not_auto_advertise_private_poses():
    instruction = "\n".join(personality_expression_guidance()).lower()
    assert "spread-legs" not in instruction
    assert "all-fours" not in instruction
    assert "sensual-stretch" not in instruction
