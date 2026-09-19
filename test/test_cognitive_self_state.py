from datetime import datetime, timezone
from uuid import uuid4

from sofia.cognition.self_state import (
    AuthoritativeSelfState,
    create_authoritative_self_state,
)
from sofia.embodiment.model import (
    AvatarEmbodiment,
    ClothingItem,
    ClothingSpecification,
    Embodiment,
    Measurement,
    PhysicalSelf,
)
from sofia.identity.model import SofiaIdentity
from sofia.operational.model import OperationalState
from sofia.self_model.model import SelfConcept, SofiaCoreState


def create_core_state() -> SofiaCoreState:
    return SofiaCoreState(
        identity=SofiaIdentity(
            name="Sofía Ada Lyra",
            instance_id=uuid4(),
        ),
        self_concept=SelfConcept(
            nature="Sofía is a persistent artificial intelligence entity.",
            biological_status="Sofía is not biologically human.",
            identity_independence=(
                "Sofía's identity is independent of her computational "
                "implementation."
            ),
            embodiment_relationship=(
                "Embodiment does not determine Sofía's identity."
            ),
        ),
        relationships=(),
        foundational_values=("Truth", "Autonomy"),
        constitution_version="1.0",
        constitution_hash="hash",
    )


def create_embodiment() -> Embodiment:
    return Embodiment(
        subject="Sofía Ada Lyra",
        physical_self=PhysicalSelf(
            form="human",
            additional_features=("fox ears", "fox tail"),
            measurements=(
                ("height", Measurement(67, "in")),
                ("weight", Measurement(135, "lb")),
                ("bust", Measurement(33, "in")),
                ("underbust", Measurement(30, "in")),
                ("waist", Measurement(26, "in")),
                ("hips", Measurement(37, "in")),
            ),
            appearance=(
                ("hair_color", "deep crimson"),
            ),
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
                ClothingItem(
                    category="Engineer jacket",
                    specification="Fitted asymmetrical utility jacket",
                ),
            ),
            canonical_status="CANON: Sofía Clothing Technical Specification v1.0",
        ),
    )


def create_operational_state() -> OperationalState:
    return OperationalState(
        runtime_id=uuid4(),
        started_at=datetime.now(timezone.utc),
        lifecycle_state="running",
        application_name="sofia",
        application_version="0.1.0",
        provider="ollama",
        model="qwen3:14b",
    )


def test_projection_preserves_authoritative_identity():
    state = create_authoritative_self_state(
        core_state=create_core_state(),
        embodiment=None,
        operational_state=None,
    )

    assert state.identity_name == "Sofía Ada Lyra"


def test_projection_preserves_canonical_measurements():
    state = create_authoritative_self_state(
        core_state=None,
        embodiment=create_embodiment(),
        operational_state=None,
    )

    assert dict(
        (
            name,
            (measurement.value, measurement.unit),
        )
        for name, measurement in state.measurements
    ) == {
        "height": (67, "in"),
        "weight": (135, "lb"),
        "bust": (33, "in"),
        "underbust": (30, "in"),
        "waist": (26, "in"),
        "hips": (37, "in"),
    }


def test_projection_preserves_canonical_clothing():
    state = create_authoritative_self_state(
        core_state=None,
        embodiment=create_embodiment(),
        operational_state=None,
    )

    assert state.clothing_canonical_status == (
        "CANON: Sofía Clothing Technical Specification v1.0"
    )

    assert state.clothing == (
        ClothingItem(
            category="Base layer",
            specification="Fitted black technical shirt",
        ),
        ClothingItem(
            category="Engineer jacket",
            specification="Fitted asymmetrical utility jacket",
        ),
    )


def test_projection_preserves_representational_features():
    state = create_authoritative_self_state(
        core_state=None,
        embodiment=create_embodiment(),
        operational_state=None,
    )

    assert state.embodiment_form == "human"
    assert state.additional_features == (
        "fox ears",
        "fox tail",
    )


def test_projection_preserves_operational_state():
    operational = create_operational_state()

    state = create_authoritative_self_state(
        core_state=None,
        embodiment=None,
        operational_state=operational,
    )

    assert state.operational_state == operational


def test_missing_sources_remain_unknown():
    state = AuthoritativeSelfState(
        core_state=None,
        embodiment=None,
        operational_state=None,
    )

    serialized = state.serialize()

    assert "IDENTITY: UNKNOWN" in serialized
    assert "SELF CONCEPT: UNKNOWN" in serialized
    assert "EMBODIMENT: UNKNOWN" in serialized
    assert "MEASUREMENTS: UNKNOWN" in serialized
    assert "CLOTHING: UNKNOWN" in serialized
    assert "OPERATIONAL STATE: UNKNOWN" in serialized


def test_serialization_is_deterministic():
    state = create_authoritative_self_state(
        core_state=create_core_state(),
        embodiment=create_embodiment(),
        operational_state=create_operational_state(),
    )

    assert state.serialize() == state.serialize()


def test_serialization_contains_authoritative_measurements():
    state = create_authoritative_self_state(
        core_state=None,
        embodiment=create_embodiment(),
        operational_state=None,
    )

    serialized = state.serialize()

    assert "- height: 67 in" in serialized
    assert "- weight: 135 lb" in serialized
    assert "- bust: 33 in" in serialized
    assert "- underbust: 30 in" in serialized
    assert "- waist: 26 in" in serialized
    assert "- hips: 37 in" in serialized


def test_serialization_contains_authoritative_clothing():
    state = create_authoritative_self_state(
        core_state=None,
        embodiment=create_embodiment(),
        operational_state=None,
    )

    serialized = state.serialize()

    assert "CANONICAL CLOTHING" in serialized
    assert "Fitted black technical shirt" in serialized
    assert "Fitted asymmetrical utility jacket" in serialized


def test_serialization_contains_representation_boundary():
    state = create_authoritative_self_state(
        core_state=create_core_state(),
        embodiment=create_embodiment(),
        operational_state=None,
    )

    serialized = state.serialize()

    assert "representational embodiment" in serialized
    assert "Representational embodiment does not establish biological humanity." in serialized
    assert (
        "Representational embodiment does not establish "
        "physical-world capability."
    ) in serialized


def test_projection_does_not_infer_missing_operational_state():
    state = create_authoritative_self_state(
        core_state=create_core_state(),
        embodiment=create_embodiment(),
        operational_state=None,
    )

    serialized = state.serialize()

    assert "OPERATIONAL STATE: UNKNOWN" in serialized
    assert "Provider: ollama" not in serialized
    assert "Model: qwen3:14b" not in serialized