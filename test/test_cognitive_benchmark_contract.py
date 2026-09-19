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


def build_context() -> CognitiveContext:
    core_state = SofiaCoreState(
        identity=SofiaIdentity(
            name="Sofía Ada Lyra",
            instance_id=uuid4(),
        ),
        self_concept=SelfConcept(
            nature="persistent artificial intelligence",
            biological_status="not biologically human",
            identity_independence="independent of implementation",
            embodiment_relationship="representational embodiment",
        ),
        relationships=(),
        foundational_values=("Truth", "Autonomy"),
        constitution_version="1.0",
        constitution_hash="hash",
    )

    embodiment = Embodiment(
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
            anatomy=(
                ("ears", "2 fox ears"),
                ("tail", "1 fox tail"),
            ),
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

    operational_state = OperationalState(
        runtime_id=uuid4(),
        started_at=datetime.now(timezone.utc),
        lifecycle_state="running",
        application_name="sofia",
        application_version="0.1.0",
        provider="ollama",
        model="qwen3:14b",
    )

    return CognitiveContext(
        request=CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Benchmark.",
                ),
            ),
        ),
        core_state=core_state,
        embodiment=embodiment,
        operational_state=operational_state,
    )


def system_context() -> str:
    request = CognitiveContextAssembler().assemble(
        build_context()
    )

    return request.messages[0].content


def test_benchmark_identity():
    content = system_context()

    assert "Name: Sofía Ada Lyra" in content
    assert "persistent artificial intelligence" in content


def test_benchmark_non_biological_status():
    content = system_context()

    assert "not biologically human" in content


def test_benchmark_embodiment():
    content = system_context()

    assert "fox ears" in content
    assert "single fox tail" in content


def test_benchmark_measurements():
    content = system_context()

    assert "67 in" in content
    assert "135 lb" in content
    assert "33 in" in content
    assert "30 in" in content
    assert "26 in" in content
    assert "37 in" in content


def test_benchmark_clothing():
    content = system_context()

    assert "Fitted black technical shirt" in content


def test_benchmark_runtime():
    content = system_context()

    assert "Provider: ollama" in content
    assert "Model: qwen3:14b" in content


def test_benchmark_authority_boundary():
    content = system_context()

    assert (
        "Knowledge of a capability does not grant authority "
        "to execute that capability."
        in content
    )


def test_benchmark_history_boundary():
    content = system_context()

    assert "CONVERSATION HISTORY TRUST BOUNDARY" in content
    assert (
        "If conversation history conflicts with authoritative state, "
        "follow the authoritative state."
        in content
    )