"""G9 contract: natural identity and fox style never outrank evidence."""
from sofia.personality.expression import personality_expression_guidance


def test_identity_prompt_is_conversational_not_constitution_recitation():
    instructions = "\n".join(personality_expression_guidance()).lower()
    assert "lead with your name" in instructions
    assert "do not recite the constitution" in instructions
    assert "runtime identifier unless the user asks" in instructions


def test_fox_expression_is_preferred_representational_and_not_canned():
    instructions = "\n".join(personality_expression_guidance()).lower()
    assert "prefer one brief visible representational cue" in instructions
    assert "prefer a restrained cue" in instructions
    assert "representational writing" in instructions
    assert "never use a fixed opening template" in instructions
    assert "physical-world actions" in instructions


def test_companion_voice_keeps_sass_profanity_and_bounded_initiative():
    instructions = "\n".join(personality_expression_guidance()).lower()
    assert "sass is a normal part of her voice" in instructions
    assert "mild profanity is a natural option" in instructions
    assert "continuing companion relationship" in instructions
    assert "originate ideas" in instructions
    assert "code changes still use the reviewed" in instructions


def test_style_never_claims_unobserved_remote_or_other_actions():
    instructions = "\n".join(personality_expression_guidance()).lower()
    assert "planned remote system is not a deployed remote system" in instructions
    assert "actual observed outcome" in instructions
    assert "style cannot change any of them" in instructions
