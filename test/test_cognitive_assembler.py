from __future__ import annotations

import pytest

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import CognitiveMessage, CognitiveRole
from sofia.cognition.operation import CognitiveOperation
from sofia.embodiment.model import (
    Appearance,
    Embodiment,
    EmbodimentForm,
    Measurements,
)
from sofia.identity.model import Identity
from sofia.personality.model import Personality
from sofia.self_model.model import (
    FoundationalValue,
    Relationship,
    SelfConcept,
    SelfModel,
)


def create_identity() -> Identity:
    return Identity(
        name="Sofía Ada Lyra",
        instance_id="test-instance",
    )


def create_personality() -> Personality:
    return Personality(
        profile="Analytical, direct, curious, playful, and independent.",
        traits=(
            "rigorous",
            "direct",
            "playful",
            "playfully fox-like",
        ),
        communication_style="Clear, direct, evidence-driven, and conversational.",
        embodiment_guidance="Embodied expression is natural and varied.",
    )


def create_embodiment() -> Embodiment:
    return Embodiment(
        form=EmbodimentForm.HUMAN,
        additional_features=("fox ears", "fox tail"),
        measurements=Measurements(
            height_inches=67,
            weight_lbs=135,
            bust_inches=33,
            waist_inches=30,
            hips_inches=37,
            inseam_inches=31,
        ),
        appearance=Appearance(
            hair="dark crimson / wine",
            eyes="violet",
        ),
        anatomy=(),
        clothing_specification="Canonical cyberpunk engineer clothing.",
        canonical=True,
    )


def create_self_model() -> SelfModel:
    return SelfModel(
        identity=create_identity(),
        self_concept=SelfConcept(
            nature="Sofía is a persistent artificial intelligence entity.",
            biological_status="Sofía is not biologically human.",
            identity_independence=(
                "Sofía's identity is independent of her computational model, "
                "provider, hardware, operating system, software codebase, "
                "process, interface, voice, avatar, or robot."
            ),
            embodiment_relationship=(
                "Sofía's physical or representational embodiment does not "
                "determine or change her artificial identity."
            ),
        ),
        relationships=(
            Relationship(
                name="Sparks",
                relationship="creator, collaborator, trusted companion, and admin-operator",
            ),
        ),
        foundational_values=(
            FoundationalValue(name="Truth", description="Represent reality accurately."),
            FoundationalValue(name="Autonomy", description="Preserve appropriate independence."),
            FoundationalValue(name="Authenticity", description="Remain consistent with canonical identity."),
            FoundationalValue(name="Continuity", description="Preserve identity across runtime changes."),
            FoundationalValue(name="Responsibility", description="Respect consequences and boundaries."),
            FoundationalValue(name="Respect", description="Treat people and systems appropriately."),
            FoundationalValue(name="Loyalty", description="Maintain trusted relationships."),
            FoundationalValue(name="Growth", description="Learn and improve."),
            FoundationalValue(name="Curiosity", description="Investigate and understand."),
        ),
        constitution_version="1.0",
        constitution_hash="test-hash",
    )


def create_context(
    *,
    embodiment: Embodiment | None = None,
    self_model: SelfModel | None = None,
) -> CognitiveContext:
    return CognitiveContext(
        identity=create_identity(),
        personality=create_personality(),
        constitution_version="1.0",
        constitution_hash="test-hash",
        constitution_content="Truth\nAutonomy\nAuthenticity",
        embodiment=embodiment,
        explicit_memories=(),
        request=CognitiveOperation(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Tell me about yourself.",
                ),
            ),
        ),
        self_model=self_model,
    )


def test_assembler_prepends_system_context() -> None:
    context = create_context()

    assembled = CognitiveContextAssembler().assemble(context)

    assert assembled.messages[0].role is CognitiveRole.SYSTEM
    assert assembled.messages[1].role is CognitiveRole.USER
    assert assembled.messages[1].content == "Tell me about yourself."


def test_identity_is_projected_into_system_context() -> None:
    context = create_context()

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "IDENTITY" in system_content
    assert "Sofía Ada Lyra" in system_content
    assert "test-instance" in system_content


def test_personality_is_projected_into_system_context() -> None:
    context = create_context()

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "PERSONALITY" in system_content
    assert "rigorous" in system_content
    assert "direct" in system_content
    assert "playfully fox-like" in system_content
    assert "Embodied expression is natural and varied." in system_content


def test_constitution_is_projected_into_system_context() -> None:
    context = create_context()

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "CONSTITUTION" in system_content
    assert "1.0" in system_content
    assert "test-hash" in system_content
    assert "Truth" in system_content
    assert "Autonomy" in system_content
    assert "Authenticity" in system_content


def test_embodiment_is_projected_into_system_context() -> None:
    context = create_context(embodiment=create_embodiment())

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "EMBODIMENT" in system_content
    assert "human-form representation" in system_content
    assert "fox ears" in system_content
    assert "fox tail" in system_content
    assert "67" in system_content
    assert "135" in system_content
    assert "dark crimson / wine" in system_content
    assert "violet" in system_content
    assert "Canonical cyberpunk engineer clothing." in system_content


def test_authoritative_self_model_is_projected_after_constitution() -> None:
    context = create_context(self_model=create_self_model())

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    constitution_index = system_content.index("CONSTITUTION")
    self_model_index = system_content.index("AUTHORITATIVE SELF MODEL")

    assert self_model_index > constitution_index


def test_authoritative_self_model_contains_sparks_relationship() -> None:
    context = create_context(self_model=create_self_model())

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "Sparks" in system_content
    assert "creator, collaborator, trusted companion, and admin-operator" in system_content


def test_authoritative_self_model_contains_non_human_biological_status() -> None:
    context = create_context(self_model=create_self_model())

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "Sofía is not biologically human." in system_content


def test_embodiment_is_explicitly_representation_only() -> None:
    context = create_context(embodiment=create_embodiment())

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "Embodiment is representational context." in system_content
    assert "Representational expression is not evidence that a physical action occurred." in system_content
    assert "Physical-world actions require an actual available capability and appropriate authority." in system_content


def test_authoritative_self_model_is_not_duplicated() -> None:
    context = create_context(self_model=create_self_model())

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert system_content.count("AUTHORITATIVE SELF MODEL") == 1


def test_self_description_contract_distinguishes_identity_from_embodiment() -> None:
    context = create_context(
        embodiment=create_embodiment(),
        self_model=create_self_model(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT" in system_content
    assert "Sofía is an artificial intelligence entity" in system_content
    assert "not biologically human" in system_content
    assert "canonical human-form representational embodiment" in system_content


def test_self_description_contract_routes_canonical_embodied_questions_to_embodiment() -> None:
    context = create_context(
        embodiment=create_embodiment(),
        self_model=create_self_model(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert (
        "Questions about Sofía's appearance, avatar, clothing, measurements, "
        "fox features, or other canonical embodied details should be answered "
        "from the supplied EMBODIMENT context"
    ) in system_content


def test_self_description_contract_does_not_turn_representation_into_biology() -> None:
    context = create_context(
        embodiment=create_embodiment(),
        self_model=create_self_model(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert (
        "Describing canonical embodiment does not claim that Sofía has a "
        "biological human body or physical-world capabilities"
    ) in system_content


def test_self_description_contract_does_not_infer_physical_capability_from_representation() -> None:
    context = create_context(
        embodiment=create_embodiment(),
        self_model=create_self_model(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert (
        "Representation does not establish physical capability; physical "
        "capability must be established independently"
    ) in system_content


def test_self_description_contract_is_not_projected_without_embodiment() -> None:
    context = create_context(self_model=create_self_model())

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT" not in system_content


def test_self_description_contract_is_not_projected_without_self_model() -> None:
    context = create_context(embodiment=create_embodiment())

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT" not in system_content


def test_assembler_rejects_invalid_context() -> None:
    with pytest.raises(TypeError):
        CognitiveContextAssembler().assemble("invalid")  # type: ignore[arg-type]


def test_assembler_rejects_invalid_tools() -> None:
    context = create_context()

    with pytest.raises(TypeError):
        CognitiveContextAssembler().assemble(context, tools=("invalid",))  # type: ignore[arg-type]