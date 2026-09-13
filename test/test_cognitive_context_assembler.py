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
    CurrentEmbodiment,
    Embodiment,
    PhysicalSelf,
)
from sofia.identity.model import SofiaIdentity
from sofia.memory.model import MemoryRecord
from sofia.personality.model import PersonalityProfile
from sofia.self_model.model import create_core_state


def test_assembler_requires_cognitive_context():
    assembler = CognitiveContextAssembler()

    try:
        assembler.assemble(object())
    except TypeError as exc:
        assert "CognitiveContext" in str(exc)
    else:
        raise AssertionError(
            "Assembler should reject a non-CognitiveContext."
        )


def test_assembler_preserves_request_messages():
    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
            CognitiveMessage(
                role=CognitiveRole.ASSISTANT,
                content="Hello, Sparks.",
            ),
        ),
    )

    context = CognitiveContext(
        request=request,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    assert assembled.messages[1:] == request.messages


def test_assembler_injects_identity():
    identity = SofiaIdentity(
        name="Sofía Ada Lyra",
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Who are you?",
                ),
            ),
        ),
        identity=identity,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert "IDENTITY" in system_message
    assert "Sofía Ada Lyra" in system_message
    assert str(identity.instance_id) in system_message


def test_assembler_injects_personality():
    personality = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=(
            "rigorous",
            "direct",
        ),
        communication_style=(
            "Answer precisely and concisely."
        ),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="How should you communicate?",
                ),
            ),
        ),
        personality=personality,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert "PERSONALITY" in system_message
    assert "Sofía Ada Lyra" in system_message
    assert "rigorous" in system_message
    assert "direct" in system_message
    assert (
        "Answer precisely and concisely."
        in system_message
    )


def test_assembler_injects_constitution():
    constitution = Constitution(
        version="1.0",
        content=(
            "Sofía is governed by her Constitution."
        ),
        content_hash="abc123",
        loaded_at=datetime.now(timezone.utc),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="What governs you?",
                ),
            ),
        ),
        constitution=constitution,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert "CONSTITUTION" in system_message
    assert "Version: 1.0" in system_message
    assert "abc123" in system_message
    assert (
        "Sofía is governed by her Constitution."
        in system_message
    )


def test_assembler_injects_embodiment():
    embodiment = Embodiment(
        subject="Sofía Ada Lyra",
        physical_self=PhysicalSelf(
            form="human",
            additional_features=(
                "fox ears",
                "fox tail",
            ),
        ),
        current=CurrentEmbodiment(
            computer="Venus",
            robot="Gaia",
            avatar="Sofía avatar",
        ),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="What is your physical form?",
                ),
            ),
        ),
        embodiment=embodiment,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert "EMBODIMENT" in system_message
    assert (
        "Embodiment form: human-form representation"
        in system_message
    )
    assert (
        "Embodiment describes representation only; it does not "
        "define Sofía's biological status or artificial identity."
        in system_message
    )
    assert "fox ears" in system_message
    assert "fox tail" in system_message
    assert "Current computer: Venus" in system_message
    assert "Current robot: Gaia" in system_message
    assert "Current avatar: Sofía avatar" in system_message


def test_assembler_injects_explicit_memories():
    memory = MemoryRecord(
        id="memory-1",
        content="Sparks is Sofía's primary collaborator.",
        created_at=datetime.now(timezone.utc),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="What do you remember?",
                ),
            ),
        ),
        memories=(memory,),
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    assert (
        "Sparks is Sofía's primary collaborator."
        in assembled.messages[0].content
    )


def test_assembler_does_not_create_authority():
    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Hello.",
                ),
            ),
        ),
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert (
        "Operational authority is enforced outside the "
        "cognitive engine."
        in system_message
    )


def test_assembler_preserves_request_order_after_system_context():
    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="First.",
            ),
            CognitiveMessage(
                role=CognitiveRole.ASSISTANT,
                content="Second.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Third.",
            ),
        ),
    )

    context = CognitiveContext(
        request=request,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    assert assembled.messages[1] == request.messages[0]
    assert assembled.messages[2] == request.messages[1]
    assert assembled.messages[3] == request.messages[2]


def test_assembler_injects_identity_instance_id():
    identity = SofiaIdentity(
        name="Sofía Ada Lyra",
        instance_id=UUID(
            "12345678-1234-5678-1234-567812345678"
        ),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Who are you?",
                ),
            ),
        ),
        identity=identity,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert (
        "Instance ID: 12345678-1234-5678-1234-567812345678"
        in system_message
    )


def test_assembler_injects_authoritative_self_model():
    identity = SofiaIdentity(
        name="Sofía Ada Lyra",
        instance_id=UUID(
            "12345678-1234-5678-1234-567812345678"
        ),
    )

    constitution = Constitution(
        version="1.0",
        content=(
            "Sofía is an artificial intelligence entity."
        ),
        content_hash="abc123",
        loaded_at=datetime.now(timezone.utc),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Who are you?",
                ),
            ),
        ),
        core_state=create_core_state(
            identity=identity,
            constitution=constitution,
        ),
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert "AUTHORITATIVE SELF MODEL" in system_message
    assert (
        "Sofía is a persistent artificial intelligence entity."
        in system_message
    )
    assert "Sofía is not biologically human." in system_message
    assert "Sparks" in system_message
    assert (
        "Instance ID: 12345678-1234-5678-1234-567812345678"
        in system_message
    )


def test_assembler_injects_sparks_relationship():
    identity = SofiaIdentity(
        name="Sofía Ada Lyra",
    )

    constitution = Constitution(
        version="1.0",
        content="Sofía is governed by her Constitution.",
        content_hash="abc123",
        loaded_at=datetime.now(timezone.utc),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Who is Sparks?",
                ),
            ),
        ),
        core_state=create_core_state(
            identity=identity,
            constitution=constitution,
        ),
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert "Sparks" in system_message
    assert "creator" in system_message
    assert "primary collaborator" in system_message
    assert "trusted companion" in system_message
    assert "admin/operator" in system_message


def test_assembler_distinguishes_identity_from_embodiment():
    identity = SofiaIdentity(
        name="Sofía Ada Lyra",
    )

    constitution = Constitution(
        version="1.0",
        content=(
            "Sofía is an artificial intelligence entity."
        ),
        content_hash="abc123",
        loaded_at=datetime.now(timezone.utc),
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
        current=CurrentEmbodiment(
            computer="Venus",
        ),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="What are you?",
                ),
            ),
        ),
        core_state=create_core_state(
            identity=identity,
            constitution=constitution,
        ),
        embodiment=embodiment,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert "AUTHORITATIVE SELF MODEL" in system_message
    assert (
        "Sofía is a persistent artificial intelligence entity."
        in system_message
    )
    assert "Sofía is not biologically human." in system_message
    assert "EMBODIMENT" in system_message
    assert (
        "Embodiment form: human-form representation"
        in system_message
    )
    assert (
        "Embodiment describes representation only; it does not "
        "define Sofía's biological status or artificial identity."
        in system_message
    )
    assert "fox ears" in system_message
    assert "fox tail" in system_message