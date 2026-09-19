from datetime import datetime, timezone
from uuid import uuid4

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
from sofia.operational.model import OperationalState
from sofia.self_model.model import SelfConcept, SofiaCoreState


def make_request() -> CognitiveRequest:
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Who are you?",
            ),
        ),
    )


def make_core_state() -> SofiaCoreState:
    return SofiaCoreState(
        identity=SofiaIdentity(
            name="Sofía Ada Lyra",
            instance_id=uuid4(),
        ),
        self_concept=SelfConcept(
            nature="persistent artificial intelligence",
            biological_status="not biologically human",
            identity_independence="independent of implementation",
            embodiment_relationship="embodiment does not determine identity",
        ),
        relationships=(),
        foundational_values=("Truth", "Autonomy"),
        constitution_version="1.0",
        constitution_hash="hash",
    )


def make_embodiment() -> Embodiment:
    return Embodiment(
        subject="Sofía Ada Lyra",
        physical_self=PhysicalSelf(
            form="human",
            additional_features=("fox ears", "single fox tail"),
            measurements=(
                ("height", Measurement(67, "in")),
                ("weight", Measurement(135, "lb")),
                ("bust", Measurement(33, "in")),
                ("underbust", Measurement(30, "in")),
                ("waist", Measurement(26, "in")),
                ("hips", Measurement(37, "in")),
            ),
            appearance=(),
            anatomy=(),
        ),
        clothing=ClothingSpecification(
            items=(
                ClothingItem(
                    category="Base layer",
                    specification="Fitted black technical shirt",
                ),
            ),
            canonical_status="CANON",
        ),
    )


def make_operational_state() -> OperationalState:
    return OperationalState(
        runtime_id=uuid4(),
        started_at=datetime.now(timezone.utc),
        lifecycle_state="running",
        application_name="sofia",
        application_version="0.1.0",
        provider="ollama",
        model="qwen3:14b",
    )


def assemble() -> str:
    context = CognitiveContext(
        request=make_request(),
        core_state=make_core_state(),
        embodiment=make_embodiment(),
        operational_state=make_operational_state(),
    )

    request = CognitiveContextAssembler().assemble(context)

    return request.messages[0].content


def test_canonical_self_state_is_present_once():
    content = assemble()

    assert content.count("AUTHORITATIVE SELF STATE") == 1


def test_canonical_identity_is_present():
    content = assemble()

    assert "Name: Sofía Ada Lyra" in content
    assert "Nature: persistent artificial intelligence" in content
    assert "Biological status: not biologically human" in content


def test_canonical_embodiment_is_present():
    content = assemble()

    assert "Form: human" in content
    assert "fox ears" in content
    assert "single fox tail" in content


def test_canonical_measurements_are_present():
    content = assemble()

    for expected in (
        "- height: 67 in",
        "- weight: 135 lb",
        "- bust: 33 in",
        "- underbust: 30 in",
        "- waist: 26 in",
        "- hips: 37 in",
    ):
        assert expected in content


def test_canonical_clothing_is_present():
    content = assemble()

    assert "CANONICAL CLOTHING" in content
    assert "Fitted black technical shirt" in content


def test_operational_state_is_present():
    content = assemble()

    assert "Provider: ollama" in content
    assert "Model: qwen3:14b" in content


def test_history_boundary_is_present():
    content = assemble()

    assert "CONVERSATION HISTORY TRUST BOUNDARY" in content
    assert (
        "A prior assistant-generated claim must not override "
        "the AUTHORITATIVE SELF STATE projection."
        in content
    )


def test_redundant_legacy_self_model_section_is_removed():
    content = assemble()

    assert "AUTHORITATIVE SELF MODEL" not in content
    assert "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT" not in content


def test_redundant_legacy_embodiment_contract_is_removed():
    content = assemble()

    assert "EMBODIMENT EXPRESSION CONTRACT" not in content


def test_unknown_state_is_explicit():
    context = CognitiveContext(
        request=make_request(),
    )

    request = CognitiveContextAssembler().assemble(context)

    content = request.messages[0].content

    assert "IDENTITY: UNKNOWN" in content
    assert "EMBODIMENT: UNKNOWN" in content
    assert "OPERATIONAL STATE: UNKNOWN" in content