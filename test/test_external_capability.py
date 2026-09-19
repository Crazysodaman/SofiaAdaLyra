from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sofia.capability import (
    CapabilityRequest,
    CapabilityResultKind,
    CapabilitySystem,
)
from sofia.external import (
    CredentialReference,
    ExternalAuthentication,
    ExternalAuthenticationMethod,
    ExternalAuthenticationState,
    ExternalCapabilityRegistration,
    ExternalIntegrationAdapter,
    ExternalIntegrationCapability,
    ExternalObservationState,
    ExternalSystem,
    ExternalSystemObservation,
    ExternalSystemType,
    create_external_observation_capability,
)


class FakeAdapter(ExternalIntegrationAdapter):
    def __init__(
        self,
        system: ExternalSystem,
        observation: ExternalSystemObservation,
    ) -> None:
        self._system = system
        self._observation = observation
        self.observe_calls = 0

    @property
    def name(self) -> str:
        return "fake-adapter"

    @property
    def system(self) -> ExternalSystem:
        return self._system

    def observe(self) -> ExternalSystemObservation:
        self.observe_calls += 1
        return self._observation


def _system(system_id: str = "github") -> ExternalSystem:
    return ExternalSystem(
        system_id=system_id,
        name="GitHub",
        system_type=ExternalSystemType.PLATFORM,
    )


def _service_system(system_id: str = "plex") -> ExternalSystem:
    return ExternalSystem(
        system_id=system_id,
        name="Plex",
        system_type=ExternalSystemType.SERVICE,
    )


def _observation(
    system: ExternalSystem,
    state: ExternalObservationState = ExternalObservationState.VERIFIED,
) -> ExternalSystemObservation:
    evidence = (
        {
            "status": "available",
            "system_id": system.system_id,
        }
        if state is ExternalObservationState.VERIFIED
        else None
    )

    return ExternalSystemObservation(
        system=system,
        observed_at=datetime.now(timezone.utc),
        state=state,
        evidence=evidence,
        source_name="fake-adapter",
    )


def _verified_auth(system_id: str) -> ExternalAuthentication:
    return ExternalAuthentication(
        system_id=system_id,
        method=ExternalAuthenticationMethod.API_KEY,
        state=ExternalAuthenticationState.VERIFIED,
        credential_reference=CredentialReference(
            reference_id=f"secret-ref-{system_id}",
            provider="test-provider",
        ),
        observed_at=datetime.now(timezone.utc),
    )


def _capability_system(
    authorization_checker=lambda request: True,
) -> CapabilitySystem:
    return CapabilitySystem(
        authorization_checker=authorization_checker,
    )


def _registration(
    integration: ExternalIntegrationCapability,
    capability_system: CapabilitySystem,
    adapter: ExternalIntegrationAdapter,
    authentication: ExternalAuthentication | None = None,
) -> ExternalCapabilityRegistration:
    return ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=authentication,
    )


def test_factory_creates_observation_capability() -> None:
    system = _system()
    adapter = FakeAdapter(system, _observation(system))

    integration = create_external_observation_capability(
        system=system,
        adapter=adapter,
    )

    assert isinstance(integration, ExternalIntegrationCapability)
    assert integration.system == system
    assert integration.adapter_name == adapter.name
    assert integration.kind.value == "observe"
    assert integration.authentication_required is True
    assert integration.capability.name == "external.observe.github"


def test_factory_rejects_adapter_for_different_system() -> None:
    system = _system("github")
    other_system = _service_system("plex")
    adapter = FakeAdapter(other_system, _observation(other_system))

    with pytest.raises(ValueError, match="adapter"):
        create_external_observation_capability(
            system=system,
            adapter=adapter,
        )


def test_registration_requires_adapter_for_matching_system() -> None:
    system = _system()
    other_system = _service_system("plex")

    integration = create_external_observation_capability(
        system=system,
        adapter=FakeAdapter(
            system,
            _observation(system),
        ),
    )

    different_system_adapter = FakeAdapter(
        other_system,
        _observation(other_system),
    )

    with pytest.raises(ValueError, match="adapter"):
        _registration(
            integration=integration,
            capability_system=_capability_system(),
            adapter=different_system_adapter,
        )


def test_unverified_authentication_blocks_execution() -> None:
    system = _system()
    adapter = FakeAdapter(system, _observation(system))
    capability_system = _capability_system()

    integration = create_external_observation_capability(
        system=system,
        adapter=adapter,
    )

    registration = _registration(
        integration=integration,
        capability_system=capability_system,
        adapter=adapter,
        authentication=ExternalAuthentication(
            system_id=system.system_id,
            method=ExternalAuthenticationMethod.API_KEY,
            state=ExternalAuthenticationState.AVAILABLE,
            credential_reference=CredentialReference(
                reference_id="available-but-not-verified",
                provider="test-provider",
            ),
            observed_at=datetime.now(timezone.utc),
        ),
    )

    registration.register()

    request = CapabilityRequest(
        capability=integration.capability,
        parameters={},
        requested_scope=None,
        rationale="Inspect the external system.",
    )

    result = capability_system.execute(request)

    assert result.kind is CapabilityResultKind.FAILED
    assert adapter.observe_calls == 0


def test_verified_authentication_allows_authorized_observation() -> None:
    system = _system()
    observation = _observation(system)
    adapter = FakeAdapter(system, observation)
    capability_system = _capability_system()

    integration = create_external_observation_capability(
        system=system,
        adapter=adapter,
    )

    registration = _registration(
        integration=integration,
        capability_system=capability_system,
        adapter=adapter,
        authentication=_verified_auth(system.system_id),
    )

    registration.register()

    request = CapabilityRequest(
        capability=integration.capability,
        parameters={},
        requested_scope=None,
        rationale="Inspect the external system.",
    )

    result = capability_system.execute(request)

    assert result.kind is CapabilityResultKind.SUCCESS
    assert isinstance(result.evidence, ExternalSystemObservation)
    assert result.evidence.system == system
    assert result.evidence.state is ExternalObservationState.VERIFIED
    assert adapter.observe_calls == 1


def test_authentication_does_not_bypass_capability_authorization() -> None:
    system = _system()
    adapter = FakeAdapter(system, _observation(system))

    capability_system = CapabilitySystem(
        authorization_checker=lambda request: False,
    )

    integration = create_external_observation_capability(
        system=system,
        adapter=adapter,
    )

    registration = _registration(
        integration=integration,
        capability_system=capability_system,
        adapter=adapter,
        authentication=_verified_auth(system.system_id),
    )

    registration.register()

    request = CapabilityRequest(
        capability=integration.capability,
        parameters={},
        requested_scope=None,
        rationale="Inspect the external system.",
    )

    result = capability_system.execute(request)

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert adapter.observe_calls == 0


def test_registration_does_not_authenticate_by_itself() -> None:
    system = _system()
    adapter = FakeAdapter(system, _observation(system))
    capability_system = _capability_system()

    integration = create_external_observation_capability(
        system=system,
        adapter=adapter,
    )

    registration = _registration(
        integration=integration,
        capability_system=capability_system,
        adapter=adapter,
    )

    registration.register()

    request = CapabilityRequest(
        capability=integration.capability,
        parameters={},
        requested_scope=None,
        rationale="Inspect the external system.",
    )

    result = capability_system.execute(request)

    assert result.kind is CapabilityResultKind.FAILED
    assert adapter.observe_calls == 0


def test_external_capability_has_no_action_or_arbitrary_execution_api() -> None:
    system = _system()
    adapter = FakeAdapter(system, _observation(system))

    integration = create_external_observation_capability(
        system=system,
        adapter=adapter,
    )

    public_names = {
        name
        for name in dir(integration)
        if not name.startswith("_")
    }

    forbidden = {
        "execute",
        "run",
        "command",
        "shell",
        "script",
        "write",
        "delete",
        "update",
        "mutate",
        "send",
    }

    assert public_names.isdisjoint(forbidden)


def test_adapter_result_system_is_validated() -> None:
    system = _system()
    wrong_system = _service_system("plex")

    adapter = FakeAdapter(
        system,
        _observation(wrong_system),
    )

    capability_system = _capability_system()

    integration = create_external_observation_capability(
        system=system,
        adapter=adapter,
    )

    registration = _registration(
        integration=integration,
        capability_system=capability_system,
        adapter=adapter,
        authentication=_verified_auth(system.system_id),
    )

    registration.register()

    request = CapabilityRequest(
        capability=integration.capability,
        parameters={},
        requested_scope=None,
        rationale="Inspect the external system.",
    )

    result = capability_system.execute(request)

    assert result.kind is CapabilityResultKind.FAILED
    assert result.evidence is None
    assert adapter.observe_calls == 1