from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sofia.capability.model import (
    CapabilityRequest,
    CapabilityResultKind,
)
from sofia.capability.system import CapabilitySystem
from sofia.external import (
    CredentialReference,
    ExternalAuthentication,
    ExternalAuthenticationMethod,
    ExternalAuthenticationState,
    ExternalCapabilityKind,
    ExternalCapabilityRegistration,
    ExternalIntegrationAdapter,
    ExternalSystem,
    ExternalSystemAction,
    ExternalSystemKnowledge,
    ExternalSystemObservation,
    ExternalSystemResult,
    ExternalSystemResultKind,
    ExternalSystemType,
    ExternalObservationState,
    create_external_action_capability,
    create_external_observation_capability,
)


class VerificationAdapter(ExternalIntegrationAdapter):
    def __init__(
        self,
        system: ExternalSystem,
    ) -> None:
        self._system = system
        self.observation_calls = 0
        self.action_calls = 0

    @property
    def name(self) -> str:
        return "verification-adapter"

    @property
    def system(self) -> ExternalSystem:
        return self._system

    def observe(self) -> ExternalSystemObservation:
        self.observation_calls += 1

        return ExternalSystemObservation(
            system=self._system,
            observed_at=datetime.now(timezone.utc),
            state=ExternalObservationState.VERIFIED,
            evidence={"status": "available"},
            source_name=self.name,
        )

    def execute_action(
        self,
        action: ExternalSystemAction,
    ) -> ExternalSystemResult:
        self.action_calls += 1

        return ExternalSystemResult(
            system_id=self._system.system_id,
            kind=ExternalSystemResultKind.SUCCESS,
            evidence={
                "action": action.action_name,
                "accepted": True,
            },
            observed_at=datetime.now(timezone.utc),
            adapter_name=self.name,
        )


def _system() -> ExternalSystem:
    return ExternalSystem(
        system_id="home-assistant",
        name="Home Assistant",
        system_type=ExternalSystemType.PLATFORM,
    )


def _auth(
    system: ExternalSystem,
) -> ExternalAuthentication:
    return ExternalAuthentication(
        system_id=system.system_id,
        method=ExternalAuthenticationMethod.BEARER_TOKEN,
        state=ExternalAuthenticationState.VERIFIED,
        credential_reference=CredentialReference(
            reference_id="external-credential",
            provider="test-vault",
        ),
    )


def _request(capability) -> CapabilityRequest:
    return CapabilityRequest(
        capability=capability,
        parameters={"entity_id": "light.office"},
        requested_scope=None,
        rationale="verification test",
    )


def test_successful_action_result_does_not_automatically_become_knowledge() -> None:
    system = _system()
    adapter = VerificationAdapter(system)

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_auth(system),
    ).register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert isinstance(result.evidence, ExternalSystemResult)
    assert result.evidence.kind is ExternalSystemResultKind.SUCCESS

    knowledge = ExternalSystemKnowledge()
    knowledge.register(system)

    assert knowledge.current(system.system_id) is None


def test_verified_observation_can_be_recorded_as_knowledge() -> None:
    system = _system()
    adapter = VerificationAdapter(system)

    observation = adapter.observe()

    knowledge = ExternalSystemKnowledge()
    knowledge.register(system)

    update = knowledge.record(observation)

    assert update.current.system_id == system.system_id
    assert update.current.state is ExternalObservationState.VERIFIED
    assert update.current.evidence == {"status": "available"}


def test_action_and_observation_remain_separate() -> None:
    system = _system()
    adapter = VerificationAdapter(system)

    observation_capability = create_external_observation_capability(
        system=system,
        adapter=adapter,
    )

    action_capability = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    assert (
        observation_capability.kind
        is ExternalCapabilityKind.OBSERVE
    )
    assert (
        action_capability.kind
        is ExternalCapabilityKind.ACTION
    )
    assert observation_capability.action_name is None
    assert action_capability.action_name == "light.turn_on"


def test_observation_capability_never_invokes_action() -> None:
    system = _system()
    adapter = VerificationAdapter(system)

    integration = create_external_observation_capability(
        system=system,
        adapter=adapter,
    )

    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_auth(system),
    ).register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert isinstance(result.evidence, ExternalSystemObservation)
    assert adapter.observation_calls == 1
    assert adapter.action_calls == 0


def test_action_capability_never_invokes_observation() -> None:
    system = _system()
    adapter = VerificationAdapter(system)

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_auth(system),
    ).register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert isinstance(result.evidence, ExternalSystemResult)
    assert adapter.action_calls == 1
    assert adapter.observation_calls == 0


def test_unauthorized_action_never_reaches_adapter() -> None:
    system = _system()
    adapter = VerificationAdapter(system)

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = CapabilitySystem(
        authorization_checker=lambda request: False,
    )

    ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_auth(system),
    ).register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert adapter.action_calls == 0


def test_unverified_authentication_never_reaches_adapter() -> None:
    system = _system()
    adapter = VerificationAdapter(system)

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = CapabilitySystem(
        authorization_checker=lambda request: True,
    )

    authentication = ExternalAuthentication(
        system_id=system.system_id,
        method=ExternalAuthenticationMethod.BEARER_TOKEN,
        state=ExternalAuthenticationState.AVAILABLE,
        credential_reference=CredentialReference(
            reference_id="credential",
        ),
    )

    ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=authentication,
    ).register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.FAILED
    assert adapter.action_calls == 0


def test_external_result_does_not_contain_credentials() -> None:
    system = _system()

    result = ExternalSystemResult(
        system_id=system.system_id,
        kind=ExternalSystemResultKind.SUCCESS,
        evidence={"status": "accepted"},
        observed_at=datetime.now(timezone.utc),
        adapter_name="verification-adapter",
    )

    serialized_repr = repr(result)

    assert "token" not in serialized_repr.lower()
    assert "password" not in serialized_repr.lower()
    assert "secret" not in serialized_repr.lower()
    assert "credential" not in serialized_repr.lower()


def test_external_action_result_is_immutable() -> None:
    system = _system()

    result = ExternalSystemResult(
        system_id=system.system_id,
        kind=ExternalSystemResultKind.SUCCESS,
        evidence={
            "nested": {
                "accepted": True,
            },
        },
        observed_at=datetime.now(timezone.utc),
        adapter_name="verification-adapter",
    )

    with pytest.raises(TypeError):
        result.evidence["nested"]["accepted"] = False  # type: ignore[index]