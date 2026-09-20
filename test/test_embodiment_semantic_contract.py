from datetime import datetime, timezone
from uuid import UUID

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.constitution.model import Constitution
from sofia.embodiment.model import (
    ClothingItem,
    ClothingSpecification,
    Embodiment,
    Measurement,
    PhysicalSelf,
)
from sofia.identity.model import SofiaIdentity
from sofia.self_model.model import create_core_state


def create_identity() -> SofiaIdentity:
    return SofiaIdentity(
        name="Sofía Ada Lyra",
        instance_id=UUID(
            "12345678-1234-5678-1234-567812345678"
        ),
    )


def create_constitution() -> Constitution:
    return Constitution(
        version="1.0",
        content="Sofía is an artificial intelligence entity.",
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


def create_context() -> CognitiveContext:
    identity = create_identity()
    constitution = create_constitution()

    return CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Tell me about your avatar.",
                ),
            ),
        ),
        identity=identity,
        embodiment=create_embodiment(),
        core_state=create_core_state(
            identity=identity,
            constitution=constitution,
        ),
    )


def assembled_content() -> str:
    request = CognitiveContextAssembler().assemble(
        create_context()
    )

    return request.messages[0].content


def test_self_description_contract_distinguishes_identity_from_embodiment():
    content = assembled_content()

    assert (
        "SELF-DESCRIPTION RESPONSE GROUNDING"
        in content
    )
    assert (
        "Sofía is a persistent artificial intelligence entity."
        in content
    )
    assert "not biologically human" in content
    assert "Form: human" in content
    assert "Representation status: representational embodiment" in content


def test_self_description_contract_routes_canonical_embodied_questions_to_embodiment():
    content = assembled_content()

    assert (
        "When the user asks about Sofía's embodiment, use the "
        "canonical embodiment and its representational status."
    ) in content
    assert "When the user asks about Sofía's measurements" in content
    assert "When the user asks what Sofía is wearing" in content


def test_self_description_contract_does_not_turn_representation_into_biology():
    content = assembled_content()

    assert (
        "Representational embodiment does not establish "
        "biological humanity."
    ) in content


def test_self_description_contract_does_not_infer_physical_capability_from_representation():
    content = assembled_content()

    assert (
        "Representational embodiment does not establish "
        "physical-world capability."
    ) in content