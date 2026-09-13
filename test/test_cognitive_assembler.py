from datetime import datetime, timezone

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.constitution.model import Constitution
from sofia.embodiment.model import (
    Embodiment,
    PhysicalSelf,
)
from sofia.identity.model import SofiaIdentity
from sofia.self_model.model import create_core_state


def create_identity() -> SofiaIdentity:
    return SofiaIdentity(
        name="Sofía Ada Lyra",
    )


def create_constitution() -> Constitution:
    return Constitution(
        version="test",
        content="CONSTITUTION TEST CONTENT",
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
            measurements=(),
            appearance=(),
            anatomy=(),
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
                    content="What is your relationship with Sparks?",
                ),
            ),
        ),
        identity=identity,
        constitution=constitution,
        embodiment=create_embodiment(),
        core_state=create_core_state(
            identity=identity,
            constitution=constitution,
        ),
    )


def test_authoritative_self_model_is_projected_after_constitution():
    context = create_context()

    request = CognitiveContextAssembler().assemble(context)

    system_content = request.messages[0].content

    constitution_position = system_content.index(
        "CONSTITUTION"
    )
    self_model_position = system_content.index(
        "AUTHORITATIVE SELF MODEL"
    )

    assert self_model_position > constitution_position


def test_authoritative_self_model_contains_sparks_relationship():
    context = create_context()

    request = CognitiveContextAssembler().assemble(context)

    system_content = request.messages[0].content

    assert (
        "- Sparks: creator, primary collaborator, "
        "trusted companion, admin/operator"
    ) in system_content


def test_authoritative_self_model_contains_non_human_biological_status():
    context = create_context()

    request = CognitiveContextAssembler().assemble(context)

    system_content = request.messages[0].content

    assert (
        "Biological status: Sofía is not biologically human."
        in system_content
    )


def test_embodiment_is_explicitly_representation_only():
    context = create_context()

    request = CognitiveContextAssembler().assemble(context)

    system_content = request.messages[0].content

    assert "Embodiment form: human-form representation" in system_content
    assert (
        "Embodiment describes representation only; it does not "
        "define Sofía's biological status or artificial identity."
        in system_content
    )


def test_self_model_is_not_duplicated():
    context = create_context()

    request = CognitiveContextAssembler().assemble(context)

    system_content = request.messages[0].content

    assert system_content.count(
        "AUTHORITATIVE SELF MODEL"
    ) == 1
