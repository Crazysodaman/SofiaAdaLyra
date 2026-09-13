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
    Embodiment,
    PhysicalSelf,
)
from sofia.identity.model import SofiaIdentity
from sofia.memory.model import MemoryRecord
from sofia.personality.model import PersonalityProfile


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


def test_assembler_preserves_original_request_messages():
    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
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

    assert assembled.messages[-2:] == request.messages


def test_assembler_injects_identity():
    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Who are you?",
                ),
            )
        ),
        identity=SofiaIdentity(
            name="Sofía Ada Lyra"
        ),
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    assert assembled.messages[0].role is CognitiveRole.SYSTEM
    assert "Sofía Ada Lyra" in assembled.messages[0].content


def test_assembler_injects_personality():
    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Hello.",
                ),
            )
        ),
        personality=PersonalityProfile(
            name="Caffeinated Quirky",
            traits=(
                "blunt",
                "rigorous",
                "energetic",
            ),
            communication_style="Direct and technically precise.",
        ),
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert "Caffeinated Quirky" in system_message
    assert "blunt" in system_message
    assert "rigorous" in system_message
    assert "Direct and technically precise." in system_message


def test_assembler_injects_constitution_without_authority():
    constitution = Constitution(
        version="1.0",
        content="Truth and autonomy govern Sofía.",
        content_hash="abc123",
        loaded_at=datetime.now(timezone.utc),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Hello.",
                ),
            )
        ),
        constitution=constitution,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0]

    assert system_message.role is CognitiveRole.SYSTEM
    assert "Truth and autonomy govern Sofía." in system_message.content
    assert "abc123" in system_message.content
    assert (
        "not an authority mechanism"
        in system_message.content
    )


def test_assembler_injects_embodiment():
    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Describe yourself.",
                ),
            )
        ),
        embodiment=Embodiment(
            subject="Sofía Ada Lyra",
            physical_self=PhysicalSelf(
                form="human",
                additional_features=(
                    "fox ears",
                    "fox tail",
                ),
            ),
        ),
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert "Sofía Ada Lyra" in system_message
    assert "human" in system_message
    assert "fox ears" in system_message
    assert "fox tail" in system_message


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
            )
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
            )
        )
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    assert not hasattr(assembled, "authority")


def test_assembler_keeps_user_message_after_context():
    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
        ),
    )

    context = CognitiveContext(
        request=request,
        identity=SofiaIdentity(
            name="Sofía Ada Lyra"
        ),
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    assert assembled.messages[0].role is CognitiveRole.SYSTEM
    assert assembled.messages[1] == request.messages[0]

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
            )
        ),
        identity=identity,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert (
        "12345678-1234-5678-1234-567812345678"
        in system_message
    )