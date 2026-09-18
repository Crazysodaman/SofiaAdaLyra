from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.embodiment.model import (
    ClothingItem,
    ClothingSpecification,
    Embodiment,
    PhysicalSelf,
)
from sofia.personality.model import PersonalityProfile


def make_context() -> CognitiveContext:
    personality = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=(
            "rigorous",
            "direct",
            "playful",
            "playfully fox-like",
        ),
        communication_style="direct and rigorous",
        embodiment_guidance=(
            "Embodied expression is natural and varied."
        ),
    )

    embodiment = Embodiment(
        subject="Sofía Ada Lyra",
        physical_self=PhysicalSelf(
            form="human",
            additional_features=(
                "fox ears",
                "fox tail",
            ),
        ),
        clothing=ClothingSpecification(
            canonical_status=(
                "CANON: Sofía Clothing Technical Specification v1.0"
            ),
            items=(
                ClothingItem(
                    category="Engineer jacket",
                    specification=(
                        "Signature fitted asymmetrical cyberpunk "
                        "utility jacket"
                    ),
                ),
            ),
        ),
    )

    return CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Describe your embodied presence.",
                ),
            ),
        ),
        personality=personality,
        embodiment=embodiment,
    )


def test_personality_embodiment_guidance_is_projected():
    request = CognitiveContextAssembler().assemble(
        make_context()
    )

    content = request.messages[0].content

    assert "Embodiment guidance:" in content
    assert "Embodied expression is natural and varied." in content
    assert "playfully fox-like" in content


def test_embodiment_projects_canonical_clothing():
    request = CognitiveContextAssembler().assemble(
        make_context()
    )

    content = request.messages[0].content

    assert "Clothing specification:" in content
    assert (
        "CANON: Sofía Clothing Technical Specification v1.0"
        in content
    )
    assert (
        "Signature fitted asymmetrical cyberpunk utility jacket"
        in content
    )


def test_embodiment_is_explicitly_representational():
    request = CognitiveContextAssembler().assemble(
        make_context()
    )

    content = request.messages[0].content

    assert (
        "Embodiment is representational context."
        in content
    )
    assert (
        "Representational expression is not evidence that a "
        "physical action occurred."
        in content
    )


def test_real_actions_require_capability_and_authority():
    request = CognitiveContextAssembler().assemble(
        make_context()
    )

    content = request.messages[0].content

    assert (
        "Physical-world actions require an actual available "
        "capability and appropriate authority."
        in content
    )

    assert (
        "Completion claims about real actions must be grounded "
        "in corresponding capability results."
        in content
    )


def test_embodiment_expression_must_not_be_canned():
    request = CognitiveContextAssembler().assemble(
        make_context()
    )

    content = request.messages[0].content

    assert (
        "Do not use a fixed gesture template or repeat a "
        "canned embodiment reaction."
        in content
    )