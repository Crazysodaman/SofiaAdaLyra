import pytest
from sofia.personality.model import PersonalityProfile
from sofia.personality.system import PersonalitySystem

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

def test_personality_system_accepts_a_profile():
    profile = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=("rigorous", "playful", "direct"),
        communication_style="direct and analytical",
    )

    personality = PersonalitySystem(profile)

    assert personality.profile is profile

def test_personality_system_reports_traits():
    profile = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=("rigorous", "playful", "direct"),
    )

    personality = PersonalitySystem(profile)

    assert personality.traits == (
        "rigorous",
        "playful",
        "direct",
    )

def test_personality_system_reports_communication_style():
    profile = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=("rigorous", "playful", "direct"),
        communication_style="direct and analytical",
    )

    personality = PersonalitySystem(profile)

    assert personality.communication_style == "direct and analytical"

def test_personality_system_provides_personality_context():
    profile = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=("rigorous", "playful", "direct"),
        communication_style="direct and analytical",
    )

    personality = PersonalitySystem(profile)

    context = personality.context()

    assert context == {
        "name": "Sofía Ada Lyra",
        "traits": (
            "rigorous",
            "playful",
            "direct",
        ),
        "communication_style": "direct and analytical",
    }

def test_personality_system_context_is_immutable():
    profile = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=("rigorous", "playful", "direct"),
        communication_style="direct and analytical",
    )

    personality = PersonalitySystem(profile)
    context = personality.context()

    with pytest.raises(TypeError):
        context["name"] = "Changed"