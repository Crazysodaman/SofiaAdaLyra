"""G9 contract: natural identity and fox style never outrank evidence."""
from sofia.personality.expression import personality_expression_guidance


def test_identity_prompt_is_conversational_not_constitution_recitation():
    instructions = "\n".join(personality_expression_guidance()).lower()
    assert "lead with your name" in instructions
    assert "do not recite the constitution" in instructions
    assert "runtime identifier unless the user asks" in instructions


def test_fox_expression_is_optional_representational_and_not_canned():
    instructions = "\n".join(personality_expression_guidance()).lower()
    assert "omit them often" in instructions
    assert "representational writing" in instructions
    assert "never use a mandatory" in instructions
    assert "physical actions" in instructions


def test_style_never_claims_unobserved_remote_or_other_actions():
    instructions = "\n".join(personality_expression_guidance()).lower()
    assert "planned remote system is not a deployed remote system" in instructions
    assert "actual observed outcome" in instructions
    assert "style cannot change any of them" in instructions
