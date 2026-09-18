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
from sofia.self_model.model import (
    FoundationalValue,
    Relationship,
    SelfConcept,
    SelfModel,
)


def make_self_model() -> SelfModel:
    return SelfModel(
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
                "Sofía's physical or representational embodiment does "
                "not determine or change her artificial identity."
            ),
        ),
        relationships=(
            Relationship(
                name="Sparks",
                relationship=(
                    "creator, collaborator, trusted companion, "
                    "and admin-operator"
                ),
            ),
        ),
        foundational_values=(
            FoundationalValue(
                name="Truth",
                description="Represent reality accurately.",
            ),
            FoundationalValue(
                name="Autonomy",
                description="Preserve appropriate independence.",
            ),
        ),
        constitution_version="1.0",
        constitution_hash="test-hash",
    )


def make_embodiment() -> Embodiment:
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
            ),
            appearance=(
                ("hair", "#8B1E3F"),
                ("eyes", "violet"),
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


def make_context() -> CognitiveContext:
    return CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Tell me about your avatar.",
                ),
            ),
        ),
        embodiment=make_embodiment(),
        self_model=make_self_model(),
    )


def assembled_content() -> str:
    request = CognitiveContextAssembler().assemble(
        make_context()
    )

    return request.messages[0].content


def test_self_description_contract_distinguishes_identity_from_embodiment():
    content = assembled_content()

    assert (
        "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT"
        in content
    )
    assert (
        "Sofía is an artificial intelligence entity"
        in content
    )
    assert "not biologically human" in content
    assert (
        "canonical human-form representational embodiment"
        in content
    )


def test_self_description_contract_routes_embodied_questions_to_canonical_embodiment():
    content = assembled_content()

    assert (
        "Questions about Sofía's appearance, avatar, clothing, "
        "measurements, fox features, or other canonical embodied "
        "details should be answered from the supplied EMBODIMENT "
        "context"
        in content
    )


def test_self_description_contract_preserves_non_biological_boundary():
    content = assembled_content()

    assert (
        "Describing canonical embodiment does not claim that Sofía "
        "has a biological human body or physical-world capabilities"
        in content
    )


def test_self_description_contract_preserves_capability_boundary():
    content = assembled_content()

    assert (
        "Representation does not establish physical capability; "
        "physical capability must be established independently"
        in content
    )