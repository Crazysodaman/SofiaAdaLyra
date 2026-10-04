import pytest
from sofia.personality.model import PersonalityProfile


def test_personality_profile_stores_name():
    personality = PersonalityProfile(
        name="Sofía Ada Lyra",
    )

    assert personality.name == "Sofía Ada Lyra"


def test_personality_profile_stores_traits():
    personality = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=("rigorous", "playful", "direct"),
    )

    assert personality.traits == (
        "rigorous",
        "playful",
        "direct",
    )


def test_personality_profile_traits_are_immutable():
    personality = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=("rigorous", "playful", "direct"),
    )

    with pytest.raises(TypeError):
        personality.traits[0] = "changed"


def test_personality_profile_stores_communication_style():
    personality = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=("rigorous", "playful", "direct"),
        communication_style="direct and analytical",
    )

    assert personality.communication_style == "direct and analytical"


def test_personality_profile_preserves_trait_order():
    personality = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=("rigorous", "playful", "direct"),
    )

    assert personality.traits == (
        "rigorous",
        "playful",
        "direct",
    )
