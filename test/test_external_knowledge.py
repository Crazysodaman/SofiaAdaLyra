from datetime import datetime, timezone

import pytest

from sofia.external import (
    ExternalObservationState,
    ExternalSystem,
    ExternalSystemKnowledge,
    ExternalSystemObservation,
    ExternalSystemType,
)


def _system(
    system_id: str = "github",
) -> ExternalSystem:
    return ExternalSystem(
        system_id=system_id,
        name="GitHub",
        system_type=ExternalSystemType.PLATFORM,
        description="Source control platform.",
    )


def _observation(
    system_id: str = "github",
    *,
    state: ExternalObservationState = (
        ExternalObservationState.VERIFIED
    ),
    evidence: dict | None = None,
    observed_at: datetime | None = None,
) -> ExternalSystemObservation:
    if observed_at is None:
        observed_at = datetime(
            2026,
            9,
            19,
            12,
            0,
            tzinfo=timezone.utc,
        )

    if evidence is None and state is ExternalObservationState.VERIFIED:
        evidence = {
            "status": "available",
            "version": "1",
        }

    return ExternalSystemObservation(
        system=_system(system_id),
        observed_at=observed_at,
        state=state,
        evidence=evidence,
    )


def test_register_known_external_system():
    knowledge = ExternalSystemKnowledge()
    system = _system()

    registered = knowledge.register(system)

    assert registered == system
    assert knowledge.get_system("github") == system
    assert knowledge.system_ids() == ("github",)


def test_registering_same_identity_is_idempotent():
    knowledge = ExternalSystemKnowledge()

    first = knowledge.register(_system())
    second = knowledge.register(_system())

    assert second is first
    assert knowledge.systems() == (first,)


def test_conflicting_identity_cannot_replace_registered_system():
    knowledge = ExternalSystemKnowledge()

    knowledge.register(_system())

    conflicting = ExternalSystem(
        system_id="github",
        name="Different Name",
        system_type=ExternalSystemType.APPLICATION,
    )

    with pytest.raises(ValueError):
        knowledge.register(conflicting)

    assert knowledge.get_system("github") == _system()


def test_unknown_system_observation_is_rejected():
    knowledge = ExternalSystemKnowledge()

    with pytest.raises(KeyError):
        knowledge.record(_observation())


def test_record_creates_current_knowledge_and_history():
    knowledge = ExternalSystemKnowledge()
    knowledge.register(_system())

    observation = _observation()

    update = knowledge.record(observation)

    assert update.previous is None
    assert update.changed is True
    assert update.current.system == _system()
    assert update.current.observation == observation
    assert knowledge.current("github") == update.current
    assert knowledge.history("github") == (update.current,)


def test_new_observation_replaces_current_and_preserves_history():
    knowledge = ExternalSystemKnowledge()
    knowledge.register(_system())

    first = knowledge.record(_observation()).current

    second_observation = _observation(
        observed_at=datetime(
            2026,
            9,
            19,
            13,
            0,
            tzinfo=timezone.utc,
        ),
        evidence={
            "status": "available",
            "version": "2",
        },
    )

    second = knowledge.record(second_observation)

    assert second.previous == first
    assert second.changed is True
    assert knowledge.current("github") == second.current
    assert knowledge.history("github") == (
        first,
        second.current,
    )


def test_stale_transition_updates_current():
    knowledge = ExternalSystemKnowledge()
    knowledge.register(_system())
    knowledge.record(_observation())

    update = knowledge.mark_stale("github")

    assert update is not None
    assert (
        update.current.state
        is ExternalObservationState.STALE
    )
    assert update.current.evidence is None
    assert knowledge.current("github") == update.current
    assert len(knowledge.history("github")) == 2


def test_invalidation_updates_current_to_unknown():
    knowledge = ExternalSystemKnowledge()
    knowledge.register(_system())
    knowledge.record(_observation())

    update = knowledge.invalidate("github")

    assert update is not None
    assert (
        update.current.state
        is ExternalObservationState.UNKNOWN
    )
    assert update.current.evidence is None
    assert knowledge.current("github") == update.current


def test_contradiction_is_preserved_without_replacing_current():
    knowledge = ExternalSystemKnowledge()
    knowledge.register(_system())

    current = knowledge.record(_observation()).current

    contradictory = _observation(
        state=ExternalObservationState.CONTRADICTED,
        evidence=None,
        observed_at=datetime(
            2026,
            9,
            19,
            14,
            0,
            tzinfo=timezone.utc,
        ),
    )

    contradiction = knowledge.record_contradiction(
        contradictory
    )

    assert contradiction.observation.state is (
        ExternalObservationState.CONTRADICTED
    )
    assert knowledge.current("github") == current
    assert knowledge.history("github") == (
        current,
        contradiction,
    )


def test_contradiction_requires_contradicted_state():
    knowledge = ExternalSystemKnowledge()
    knowledge.register(_system())
    knowledge.record(_observation())

    with pytest.raises(ValueError):
        knowledge.record_contradiction(
            _observation(
                state=ExternalObservationState.VERIFIED,
            )
        )


def test_identical_contradiction_is_rejected():
    knowledge = ExternalSystemKnowledge()
    knowledge.register(_system())
    knowledge.record(_observation())

    with pytest.raises(ValueError):
        knowledge.record_contradiction(
            knowledge.current("github").observation
        )


def test_unknown_system_cannot_receive_contradiction():
    knowledge = ExternalSystemKnowledge()

    with pytest.raises(KeyError):
        knowledge.record_contradiction(
            _observation(
                state=ExternalObservationState.CONTRADICTED,
                evidence=None,
            )
        )


def test_evidence_is_detached_and_recursively_frozen():
    knowledge = ExternalSystemKnowledge()
    knowledge.register(_system())

    nested = {
        "status": "available",
        "details": {
            "version": "1",
            "tags": ["api", "external"],
        },
    }

    observation = _observation(
        evidence=nested,
    )

    record = knowledge.record(observation).current

    nested["status"] = "changed"
    nested["details"]["version"] = "2"
    nested["details"]["tags"].append("mutated")

    assert record.evidence["status"] == "available"
    assert record.evidence["details"]["version"] == "1"
    assert record.evidence["details"]["tags"] == (
        "api",
        "external",
    )


def test_stable_identity_is_not_changed_by_observation():
    knowledge = ExternalSystemKnowledge()

    system = _system()
    knowledge.register(system)

    knowledge.record(
        _observation(
            evidence={
                "name": "Completely Different Runtime Name",
                "type": "database",
            }
        )
    )

    assert knowledge.get_system("github") == system
    assert knowledge.get_system("github").name == "GitHub"
    assert (
        knowledge.get_system("github").system_type
        is ExternalSystemType.PLATFORM
    )


def test_observation_identity_must_match_registered_identity():
    knowledge = ExternalSystemKnowledge()

    registered = _system()
    knowledge.register(registered)

    conflicting_system = ExternalSystem(
        system_id="github",
        name="Different GitHub Identity",
        system_type=ExternalSystemType.PLATFORM,
    )

    observation = ExternalSystemObservation(
        system=conflicting_system,
        observed_at=datetime(
            2026,
            9,
            19,
            15,
            0,
            tzinfo=timezone.utc,
        ),
        state=ExternalObservationState.VERIFIED,
        evidence={"status": "available"},
    )

    with pytest.raises(ValueError):
        knowledge.record(observation)

    assert knowledge.current("github") is None


def test_systems_are_isolated():
    knowledge = ExternalSystemKnowledge()

    github = _system("github")

    home_assistant = ExternalSystem(
        system_id="home-assistant",
        name="Home Assistant",
        system_type=ExternalSystemType.SERVICE,
    )

    knowledge.register(github)
    knowledge.register(home_assistant)

    knowledge.record(_observation("github"))

    assert knowledge.current("github") is not None
    assert knowledge.current("home-assistant") is None
    assert knowledge.history("home-assistant") == ()


def test_missing_current_returns_none_for_stale_transition():
    knowledge = ExternalSystemKnowledge()
    knowledge.register(_system())

    assert knowledge.mark_stale("github") is None
    assert knowledge.invalidate("github") is None


def test_clear_removes_dynamic_knowledge_but_not_identity():
    knowledge = ExternalSystemKnowledge()
    system = _system()

    knowledge.register(system)
    knowledge.record(_observation())

    knowledge.clear("github")

    assert knowledge.current("github") is None
    assert knowledge.history("github") == ()
    assert knowledge.get_system("github") == system


def test_clear_does_not_remove_other_systems():
    knowledge = ExternalSystemKnowledge()

    github = _system("github")
    home_assistant = ExternalSystem(
        system_id="home-assistant",
        name="Home Assistant",
        system_type=ExternalSystemType.SERVICE,
    )

    knowledge.register(github)
    knowledge.register(home_assistant)

    knowledge.record(_observation("github"))

    knowledge.clear("github")

    assert knowledge.get_system("github") == github
    assert knowledge.get_system("home-assistant") == home_assistant
    assert knowledge.current("home-assistant") is None


def test_invalid_system_id_is_rejected():
    knowledge = ExternalSystemKnowledge()

    with pytest.raises(TypeError):
        knowledge.get_system(123)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        knowledge.get_system("")


def test_knowledge_exposes_no_authority_or_execution_api():
    knowledge = ExternalSystemKnowledge()

    forbidden = (
        "authorize",
        "execute",
        "authenticate",
        "credentials",
        "register_capability",
        "interpret",
    )

    for name in forbidden:
        assert not hasattr(knowledge, name)