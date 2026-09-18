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
    Measurement,
    PhysicalSelf,
)
from sofia.identity.model import SofiaIdentity
from sofia.memory.model import MemoryRecord
from sofia.personality.model import PersonalityProfile
from sofia.self_model.model import create_core_state
from pathlib import Path

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.filesystem.model import (
    FilesystemOperation,
    FilesystemResult,
    FilesystemResultKind,
)


def make_request() -> CognitiveRequest:
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Inspect the repository.",
            ),
        )
    )


def make_filesystem_result() -> FilesystemResult:
    return FilesystemResult(
        operation=FilesystemOperation.LIST_DIRECTORY,
        kind=FilesystemResultKind.SUCCESS,
        path=Path("."),
        message="Directory inspection completed.",
        entries=(
            Path("src"),
            Path("test"),
        ),
    )


def test_assembler_includes_filesystem_results() -> None:
    result = make_filesystem_result()

    context = CognitiveContext(
        request=make_request(),
        filesystem_results=(result,),
    )

    request = CognitiveContextAssembler().assemble(
        context
    )

    system_message = request.messages[0]

    assert "FILESYSTEM INSPECTION RESULTS" in system_message.content
    assert "Operation: list_directory" in system_message.content
    assert "Result: success" in system_message.content
    assert "Path: ." in system_message.content
    assert "Directory inspection completed." in system_message.content
    assert "src" in system_message.content
    assert "test" in system_message.content


def test_assembler_does_not_claim_inspection_without_result() -> None:
    context = CognitiveContext(
        request=make_request(),
    )

    request = CognitiveContextAssembler().assemble(
        context
    )

    system_message = request.messages[0]

    assert "FILESYSTEM INSPECTION RESULTS" not in system_message.content


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


def test_assembler_injects_embodiment_measurements():
    embodiment = Embodiment(
        subject="Sofía Ada Lyra",
        physical_self=PhysicalSelf(
            form="human",
            measurements=(
                (
                    "height",
                    Measurement(
                        value=67,
                        unit="in",
                    ),
                ),
                (
                    "weight",
                    Measurement(
                        value=135,
                        unit="lb",
                    ),
                ),
                (
                    "bust",
                    Measurement(
                        value=33,
                        unit="in",
                    ),
                ),
                (
                    "underbust",
                    Measurement(
                        value=30,
                        unit="in",
                    ),
                ),
                (
                    "waist",
                    Measurement(
                        value=26,
                        unit="in",
                    ),
                ),
                (
                    "hips",
                    Measurement(
                        value=37,
                        unit="in",
                    ),
                ),
            ),
        ),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="What are your measurements?",
                ),
            ),
        ),
        embodiment=embodiment,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert (
        "CANONICAL EMBODIMENT BODY MEASUREMENTS:"
        in system_message
    )

    assert (
        "- height (canonical embodiment body measurement): 67 in"
        in system_message
    )
    assert (
        "- weight (canonical embodiment body measurement): 135 lb"
        in system_message
    )
    assert (
        "- bust (canonical embodiment body measurement): 33 in"
        in system_message
    )
    assert (
        "- underbust (canonical embodiment body measurement): 30 in"
        in system_message
    )
    assert (
        "- waist (canonical embodiment body measurement): 26 in"
        in system_message
    )
    assert (
        "- hips (canonical embodiment body measurement): 37 in"
        in system_message
    )

    assert (
        "Clothing, footwear, toolkit, wrist-device, equipment, "
        "and other component dimensions are separate design data."
        in system_message
    )


def test_assembler_injects_embodiment_appearance_and_anatomy():
    embodiment = Embodiment(
        subject="Sofía Ada Lyra",
        physical_self=PhysicalSelf(
            form="human",
            appearance=(
                (
                    "hair_color",
                    "deep crimson",
                ),
                (
                    "skin_color",
                    "warm ivory",
                ),
            ),
            anatomy=(
                (
                    "ears",
                    "2 fox ears",
                ),
                (
                    "tail",
                    "1 fox tail",
                ),
            ),
        ),
    )

    context = CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Describe your appearance.",
                ),
            ),
        ),
        embodiment=embodiment,
    )

    assembled = CognitiveContextAssembler().assemble(
        context
    )

    system_message = assembled.messages[0].content

    assert "Appearance:" in system_message
    assert "- hair_color: deep crimson" in system_message
    assert "- skin_color: warm ivory" in system_message
    assert "Anatomy:" in system_message
    assert "- ears: 2 fox ears" in system_message
    assert "- tail: 1 fox tail" in system_message


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