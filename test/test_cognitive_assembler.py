from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

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
    Measurement,
    PhysicalSelf,
)
from sofia.identity.model import SofiaIdentity
from sofia.personality.model import PersonalityProfile
from sofia.self_model.model import (
    Relationship,
    SelfConcept,
    SofiaCoreState,
)


def create_identity() -> SofiaIdentity:
    return SofiaIdentity(
        name="Sofía Ada Lyra",
        instance_id=UUID(
            "12345678-1234-5678-1234-567812345678"
        ),
    )


def create_personality() -> PersonalityProfile:
    return PersonalityProfile(
        name="Sofía",
        traits=(
            "rigorous",
            "direct",
            "playful",
            "playfully fox-like",
        ),
        communication_style=(
            "Clear, direct, evidence-driven, and conversational."
        ),
        embodiment_guidance=(
            "Embodied expression is natural and varied."
        ),
    )


def create_constitution():
    from sofia.constitution.model import Constitution

    return Constitution(
        version="1.0",
        content="Truth\nAutonomy\nAuthenticity",
        content_hash="test-hash",
        loaded_at=datetime.now(timezone.utc),
    )


def create_embodiment() -> Embodiment:
    return Embodiment(
        subject="Sofía Ada Lyra",
        physical_self=PhysicalSelf(
            form="human",
            additional_features=(
                "fox ears",
                "fox tail",
            ),
            measurements=(
                ("height", Measurement(67, "inches")),
                ("weight", Measurement(135, "lb")),
                ("bust", Measurement(33, "inches")),
                ("waist", Measurement(30, "inches")),
                ("hips", Measurement(37, "inches")),
                ("inseam", Measurement(31, "inches")),
            ),
            appearance=(
                ("hair", "dark crimson / wine"),
                ("eyes", "violet"),
            ),
            anatomy=(),
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


def create_core_state() -> SofiaCoreState:
    identity = create_identity()

    return SofiaCoreState(
        identity=identity,
        self_concept=SelfConcept(
            nature=(
                "Sofía is a persistent artificial intelligence entity."
            ),
            biological_status=(
                "Sofía is not biologically human."
            ),
            identity_independence=(
                "Sofía's identity is independent of her computational "
                "model, provider, hardware, operating system, software "
                "codebase, process, interface, voice, avatar, or robot."
            ),
            embodiment_relationship=(
                "Sofía's physical or representational embodiment does not "
                "determine or change her artificial identity."
            ),
        ),
        relationships=(
            Relationship(
                subject="Sparks",
                roles=(
                    "creator",
                    "primary collaborator",
                    "trusted companion",
                    "admin/operator",
                ),
            ),
        ),
        foundational_values=(
            "Truth",
            "Autonomy",
            "Authenticity",
            "Continuity",
            "Responsibility",
            "Respect",
            "Loyalty",
            "Growth",
            "Curiosity",
        ),
        constitution_version="1.0",
        constitution_hash="test-hash",
    )


def create_context(
    *,
    embodiment: Embodiment | None = None,
    core_state: SofiaCoreState | None = None,
) -> CognitiveContext:
    return CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Tell me about yourself.",
                ),
            ),
        ),
        identity=create_identity(),
        personality=create_personality(),
        constitution=create_constitution(),
        embodiment=embodiment,
        core_state=core_state,
        memories=(),
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
    assert "12345678-1234-5678-1234-567812345678" in system_content


def test_personality_is_projected_into_system_context() -> None:
    context = create_context()

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "PERSONALITY" in system_content
    assert "rigorous" in system_content
    assert "direct" in system_content
    assert "playfully fox-like" in system_content
    assert (
        "Embodied expression is natural and varied."
        in system_content
    )


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
    context = create_context(
        embodiment=create_embodiment(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "EMBODIMENT" in system_content
    assert "human-form representation" in system_content
    assert "fox ears" in system_content
    assert "fox tail" in system_content
    assert "67" in system_content
    assert "135" in system_content
    assert "33" in system_content
    assert "30" in system_content
    assert "37" in system_content
    assert "31" in system_content
    assert "dark crimson / wine" in system_content
    assert "violet" in system_content
    assert (
        "CANON: Sofía Clothing Technical Specification v1.0"
        in system_content
    )
    assert (
        "Signature fitted asymmetrical cyberpunk utility jacket"
        in system_content
    )


def test_authoritative_self_model_is_projected_after_constitution() -> None:
    context = create_context(
        core_state=create_core_state(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    constitution_index = system_content.index("CONSTITUTION")
    self_model_index = system_content.index(
        "AUTHORITATIVE SELF MODEL"
    )

    assert self_model_index > constitution_index


def test_authoritative_self_model_contains_sparks_relationship() -> None:
    context = create_context(
        core_state=create_core_state(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "Sparks" in system_content
    assert "creator" in system_content
    assert "primary collaborator" in system_content
    assert "trusted companion" in system_content
    assert "admin/operator" in system_content


def test_authoritative_self_model_contains_non_human_biological_status() -> None:
    context = create_context(
        core_state=create_core_state(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "Sofía is not biologically human." in system_content


def test_embodiment_is_explicitly_representation_only() -> None:
    context = create_context(
        embodiment=create_embodiment(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert "Embodiment is representational context." in system_content
    assert (
        "Representational expression is not evidence that a physical "
        "action occurred."
        in system_content
    )
    assert (
        "Physical-world actions require an actual available capability "
        "and appropriate authority."
        in system_content
    )


def test_authoritative_self_model_is_not_duplicated() -> None:
    context = create_context(
        core_state=create_core_state(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert system_content.count("AUTHORITATIVE SELF MODEL") == 1


def test_self_description_contract_distinguishes_identity_from_embodiment() -> None:
    context = create_context(
        embodiment=create_embodiment(),
        core_state=create_core_state(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert (
        "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT"
        in system_content
    )
    assert (
        "Sofía is an artificial intelligence entity"
        in system_content
    )
    assert "not biologically human" in system_content
    assert (
        "canonical human-form representational embodiment"
        in system_content
    )


def test_self_description_contract_routes_canonical_embodied_questions_to_embodiment() -> None:
    context = create_context(
        embodiment=create_embodiment(),
        core_state=create_core_state(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert (
        "Questions about Sofía's appearance, avatar, clothing, "
        "measurements, fox features, or other canonical embodied "
        "details should be answered from the supplied EMBODIMENT "
        "context"
    ) in system_content


def test_self_description_contract_does_not_turn_representation_into_biology() -> None:
    context = create_context(
        embodiment=create_embodiment(),
        core_state=create_core_state(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert (
        "Describing canonical embodiment does not claim that Sofía "
        "has a biological human body or physical-world capabilities"
    ) in system_content


def test_self_description_contract_does_not_infer_physical_capability_from_representation() -> None:
    context = create_context(
        embodiment=create_embodiment(),
        core_state=create_core_state(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert (
        "Representation does not establish physical capability; "
        "physical capability must be established independently"
    ) in system_content


def test_self_description_contract_is_not_projected_without_embodiment() -> None:
    context = create_context(
        core_state=create_core_state(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert (
        "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT"
        not in system_content
    )


def test_self_description_contract_is_not_projected_without_self_model() -> None:
    context = create_context(
        embodiment=create_embodiment(),
    )

    assembled = CognitiveContextAssembler().assemble(context)

    system_content = assembled.messages[0].content

    assert (
        "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT"
        not in system_content
    )


def test_assembler_rejects_invalid_context() -> None:
    with pytest.raises(TypeError):
        CognitiveContextAssembler().assemble(
            "invalid",  # type: ignore[arg-type]
        )


def test_assembler_rejects_invalid_tools() -> None:
    context = create_context()

    with pytest.raises(TypeError):
        CognitiveContextAssembler().assemble(
            context,
            tools=("invalid",),  # type: ignore[arg-type]
        )