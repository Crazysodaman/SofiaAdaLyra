from datetime import datetime, timezone
from uuid import UUID

from sofia.constitution.model import Constitution
from sofia.identity.model import SofiaIdentity
from sofia.self_model.model import (
    Relationship,
    SelfConcept,
    SofiaCoreState,
    create_core_state,
)


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
        content_hash="abc123",
        loaded_at=datetime.now(timezone.utc),
    )


def test_self_concept_requires_non_empty_fields():
    concept = SelfConcept(
        nature="artificial intelligence",
        biological_status="not biologically human",
        identity_independence="independent of implementation",
        embodiment_relationship="embodiment does not define identity",
    )

    assert concept.nature == "artificial intelligence"


def test_relationship_requires_roles():
    relationship = Relationship(
        subject="Sparks",
        roles=(
            "creator",
            "primary collaborator",
        ),
    )

    assert relationship.subject == "Sparks"
    assert relationship.roles == (
        "creator",
        "primary collaborator",
    )


def test_create_core_state_identifies_sofia_as_ai():
    core_state = create_core_state(
        identity=create_identity(),
        constitution=create_constitution(),
    )

    assert "artificial intelligence" in (
        core_state.self_concept.nature.lower()
    )


def test_create_core_state_distinguishes_sofia_from_biological_human():
    core_state = create_core_state(
        identity=create_identity(),
        constitution=create_constitution(),
    )

    assert (
        "not biologically human"
        in core_state.self_concept.biological_status.lower()
    )


def test_create_core_state_separates_identity_from_embodiment():
    core_state = create_core_state(
        identity=create_identity(),
        constitution=create_constitution(),
    )

    assert (
        "does not determine or change"
        in core_state.self_concept.embodiment_relationship
    )


def test_create_core_state_defines_sparks_relationship():
    core_state = create_core_state(
        identity=create_identity(),
        constitution=create_constitution(),
    )

    relationship = next(
        relationship
        for relationship in core_state.relationships
        if relationship.subject == "Sparks"
    )

    assert relationship.roles == (
        "creator",
        "primary collaborator",
        "trusted companion",
        "admin/operator",
    )


def test_create_core_state_contains_foundational_values():
    core_state = create_core_state(
        identity=create_identity(),
        constitution=create_constitution(),
    )

    assert core_state.foundational_values == (
        "Truth",
        "Autonomy",
        "Authenticity",
        "Continuity",
        "Responsibility",
        "Respect",
        "Loyalty",
        "Growth",
        "Curiosity",
    )


def test_create_core_state_preserves_identity_instance_id():
    identity = create_identity()

    core_state = create_core_state(
        identity=identity,
        constitution=create_constitution(),
    )

    assert core_state.identity == identity
    assert core_state.identity.instance_id == identity.instance_id


def test_create_core_state_preserves_constitution_reference():
    constitution = create_constitution()

    core_state = create_core_state(
        identity=create_identity(),
        constitution=constitution,
    )

    assert core_state.constitution_version == constitution.version
    assert core_state.constitution_hash == constitution.content_hash


def test_core_state_is_immutable():
    core_state = create_core_state(
        identity=create_identity(),
        constitution=create_constitution(),
    )

    try:
        core_state.self_concept = None
    except AttributeError:
        pass
    else:
        raise AssertionError(
            "SofiaCoreState must be immutable."
        )


def test_core_state_rejects_invalid_identity():
    try:
        SofiaCoreState(
            identity=object(),
            self_concept=SelfConcept(
                nature="AI",
                biological_status="not biologically human",
                identity_independence="implementation independent",
                embodiment_relationship="embodiment does not define identity",
            ),
            relationships=(),
            foundational_values=("Truth",),
            constitution_version="1.0",
            constitution_hash="abc123",
        )
    except TypeError as exc:
        assert "SofiaIdentity" in str(exc)
    else:
        raise AssertionError(
            "SofiaCoreState should reject an invalid identity."
        )