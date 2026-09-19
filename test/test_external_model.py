from datetime import datetime, timezone

import pytest

from sofia.external import (
    ExternalObservationState,
    ExternalSystem,
    ExternalSystemObservation,
    ExternalSystemResult,
    ExternalSystemResultKind,
    ExternalSystemState,
    ExternalSystemType,
)


def _system() -> ExternalSystem:
    return ExternalSystem(
        system_id="home-assistant",
        name="Home Assistant",
        system_type=ExternalSystemType.PLATFORM,
        description="Home automation platform.",
    )


def test_external_system_represents_stable_identity() -> None:
    system = _system()

    assert system.system_id == "home-assistant"
    assert system.name == "Home Assistant"
    assert system.system_type is ExternalSystemType.PLATFORM
    assert system.description == "Home automation platform."


def test_external_system_is_immutable() -> None:
    system = _system()

    with pytest.raises(AttributeError):
        system.name = "Changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "system_id",
    ("", "   ", None, 123),
)
def test_external_system_rejects_invalid_system_id(
    system_id,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        ExternalSystem(
            system_id=system_id,
            name="Example",
            system_type=ExternalSystemType.SERVICE,
        )


@pytest.mark.parametrize(
    "name",
    ("", "   ", None, 123),
)
def test_external_system_rejects_invalid_name(
    name,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        ExternalSystem(
            system_id="example",
            name=name,
            system_type=ExternalSystemType.SERVICE,
        )


def test_external_system_rejects_invalid_type() -> None:
    with pytest.raises(TypeError):
        ExternalSystem(
            system_id="example",
            name="Example",
            system_type="service",  # type: ignore[arg-type]
        )


def test_external_system_supports_known_types() -> None:
    assert ExternalSystemType.API.value == "api"
    assert ExternalSystemType.APPLICATION.value == "application"
    assert ExternalSystemType.DATABASE.value == "database"
    assert ExternalSystemType.DEVICE.value == "device"
    assert ExternalSystemType.PLATFORM.value == "platform"
    assert ExternalSystemType.SERVICE.value == "service"


def test_external_system_state_is_structured() -> None:
    assert ExternalSystemState.AVAILABLE.value == "available"
    assert ExternalSystemState.UNAVAILABLE.value == "unavailable"
    assert ExternalSystemState.DEGRADED.value == "degraded"
    assert ExternalSystemState.UNKNOWN.value == "unknown"


def test_verified_observation_requires_evidence() -> None:
    with pytest.raises(ValueError):
        ExternalSystemObservation(
            system=_system(),
            observed_at=datetime.now(timezone.utc),
            state=ExternalObservationState.VERIFIED,
        )


def test_verified_observation_records_evidence() -> None:
    observed_at = datetime.now(timezone.utc)

    observation = ExternalSystemObservation(
        system=_system(),
        observed_at=observed_at,
        state=ExternalObservationState.VERIFIED,
        evidence={
            "version": "2026.9",
            "status": "running",
        },
        source_name="test-adapter",
    )

    assert observation.system_id == "home-assistant"
    assert observation.observed_at == observed_at
    assert observation.state is ExternalObservationState.VERIFIED
    assert observation.evidence["version"] == "2026.9"
    assert observation.source_name == "test-adapter"


@pytest.mark.parametrize(
    "state",
    (
        ExternalObservationState.STALE,
        ExternalObservationState.UNKNOWN,
        ExternalObservationState.CONTRADICTED,
    ),
)
def test_non_verified_observation_cannot_claim_evidence(
    state: ExternalObservationState,
) -> None:
    with pytest.raises(ValueError):
        ExternalSystemObservation(
            system=_system(),
            observed_at=datetime.now(timezone.utc),
            state=state,
            evidence={"status": "running"},
        )


def test_observation_evidence_is_recursively_immutable() -> None:
    evidence = {
        "system": {
            "status": "running",
            "items": [
                {"name": "light.kitchen"},
            ],
        }
    }

    observation = ExternalSystemObservation(
        system=_system(),
        observed_at=datetime.now(timezone.utc),
        state=ExternalObservationState.VERIFIED,
        evidence=evidence,
    )

    evidence["system"]["status"] = "changed"
    evidence["system"]["items"][0]["name"] = "changed"

    assert (
        observation.evidence["system"]["status"]
        == "running"
    )
    assert (
        observation.evidence["system"]["items"][0]["name"]
        == "light.kitchen"
    )

    with pytest.raises(TypeError):
        observation.evidence["system"] = {}  # type: ignore[index]


def test_observation_is_immutable() -> None:
    observation = ExternalSystemObservation(
        system=_system(),
        observed_at=datetime.now(timezone.utc),
        state=ExternalObservationState.UNKNOWN,
    )

    with pytest.raises(AttributeError):
        observation.state = ExternalObservationState.VERIFIED


def test_successful_external_result_requires_complete_provenance() -> None:
    with pytest.raises(ValueError):
        ExternalSystemResult(
            system_id="home-assistant",
            kind=ExternalSystemResultKind.SUCCESS,
        )

    with pytest.raises(ValueError):
        ExternalSystemResult(
            system_id="home-assistant",
            kind=ExternalSystemResultKind.SUCCESS,
            evidence={"status": "running"},
        )

    with pytest.raises(ValueError):
        ExternalSystemResult(
            system_id="home-assistant",
            kind=ExternalSystemResultKind.SUCCESS,
            observed_at=datetime.now(timezone.utc),
        )


def test_successful_external_result_records_evidence() -> None:
    observed_at = datetime.now(timezone.utc)

    result = ExternalSystemResult(
        system_id="home-assistant",
        kind=ExternalSystemResultKind.SUCCESS,
        evidence={
            "status": "running",
            "version": "2026.9",
        },
        observed_at=observed_at,
        adapter_name="home-assistant-test",
    )

    assert result.system_id == "home-assistant"
    assert result.kind is ExternalSystemResultKind.SUCCESS
    assert result.observed_at == observed_at
    assert result.adapter_name == "home-assistant-test"
    assert result.evidence["status"] == "running"


@pytest.mark.parametrize(
    "kind",
    (
        ExternalSystemResultKind.UNAVAILABLE,
        ExternalSystemResultKind.FAILED,
    ),
)
def test_non_successful_result_cannot_contain_evidence(
    kind: ExternalSystemResultKind,
) -> None:
    with pytest.raises(ValueError):
        ExternalSystemResult(
            system_id="home-assistant",
            kind=kind,
            evidence={"status": "running"},
            error="test failure",
        )


def test_failed_result_can_record_error_and_adapter() -> None:
    result = ExternalSystemResult(
        system_id="home-assistant",
        kind=ExternalSystemResultKind.FAILED,
        adapter_name="home-assistant-test",
        error="connection failed",
    )

    assert result.kind is ExternalSystemResultKind.FAILED
    assert result.adapter_name == "home-assistant-test"
    assert result.error == "connection failed"
    assert result.evidence is None


def test_unavailable_result_does_not_require_error() -> None:
    result = ExternalSystemResult(
        system_id="home-assistant",
        kind=ExternalSystemResultKind.UNAVAILABLE,
    )

    assert result.kind is ExternalSystemResultKind.UNAVAILABLE
    assert result.evidence is None
    assert result.error is None


def test_result_evidence_is_recursively_immutable() -> None:
    evidence = {
        "response": {
            "items": [
                {"id": 1},
            ],
        }
    }

    result = ExternalSystemResult(
        system_id="example-api",
        kind=ExternalSystemResultKind.SUCCESS,
        evidence=evidence,
        observed_at=datetime.now(timezone.utc),
        adapter_name="test-adapter",
    )

    evidence["response"]["items"][0]["id"] = 99

    assert (
        result.evidence["response"]["items"][0]["id"]
        == 1
    )

    with pytest.raises(TypeError):
        result.evidence["response"] = {}  # type: ignore[index]


def test_external_contracts_do_not_model_credentials() -> None:
    system = _system()

    assert not hasattr(system, "password")
    assert not hasattr(system, "token")
    assert not hasattr(system, "secret")
    assert not hasattr(system, "credential")


def test_external_result_is_immutable() -> None:
    result = ExternalSystemResult(
        system_id="example",
        kind=ExternalSystemResultKind.UNAVAILABLE,
    )

    with pytest.raises(AttributeError):
        result.kind = ExternalSystemResultKind.SUCCESS