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
    ExternalSystemResult,
    ExternalSystemResultKind,
    ExternalSystemType,
    create_external_action_capability,
)


class FakeActionAdapter(ExternalIntegrationAdapter):
    def __init__(
        self,
        system: ExternalSystem,
        *,
        result: ExternalSystemResult | None = None,
    ) -> None:
        self._system = system
        self._result = result
        self.actions: list[ExternalSystemAction] = []

    @property
    def name(self) -> str:
        return "fake-action-adapter"

    @property
    def system(self) -> ExternalSystem:
        return self._system

    def observe(self):
        raise AssertionError(
            "Action tests must not invoke observation."
        )

    def execute_action(
        self,
        action: ExternalSystemAction,
    ) -> ExternalSystemResult:
        self.actions.append(action)

        if self._result is None:
            return ExternalSystemResult(
                system_id=self._system.system_id,
                kind=ExternalSystemResultKind.SUCCESS,
                evidence={"action": action.action_name},
                observed_at=datetime.now(timezone.utc),
                adapter_name=self.name,
            )

        return self._result


def _system() -> ExternalSystem:
    return ExternalSystem(
        system_id="home-assistant",
        name="Home Assistant",
        system_type=ExternalSystemType.PLATFORM,
    )


def _authentication(
    system: ExternalSystem,
) -> ExternalAuthentication:
    return ExternalAuthentication(
        system_id=system.system_id,
        method=ExternalAuthenticationMethod.BEARER_TOKEN,
        state=ExternalAuthenticationState.VERIFIED,
        credential_reference=CredentialReference(
            reference_id="credential-ref",
            provider="test-vault",
        ),
    )


def _capability_system(
    authorized: bool = True,
) -> CapabilitySystem:
    return CapabilitySystem(
        authorization_checker=lambda request: authorized,
    )


def _request(
    capability,
    *,
    parameters: dict[str, object] | None = None,
) -> CapabilityRequest:
    return CapabilityRequest(
        capability=capability,
        parameters=parameters or {},
        requested_scope=None,
        rationale="test external action",
    )


def test_action_model_is_structured_and_immutable() -> None:
    action = ExternalSystemAction(
        system_id="home-assistant",
        action_name="light.turn_on",
        parameters={
            "entity_id": "light.office",
            "brightness": 50,
        },
    )

    assert action.system_id == "home-assistant"
    assert action.action_name == "light.turn_on"
    assert action.parameters["brightness"] == 50

    with pytest.raises(TypeError):
        action.parameters["brightness"] = 100  # type: ignore[index]


def test_action_capability_has_fixed_action_name() -> None:
    system = _system()
    adapter = FakeActionAdapter(system)

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    assert integration.kind is ExternalCapabilityKind.ACTION
    assert integration.action_name == "light.turn_on"


def test_action_capability_requires_action_name() -> None:
    system = _system()
    adapter = FakeActionAdapter(system)

    with pytest.raises(ValueError, match="action_name"):
        create_external_action_capability(
            system=system,
            adapter=adapter,
            action_name="",
        )


def test_observation_capability_cannot_define_action_name() -> None:
    system = _system()
    adapter = FakeActionAdapter(system)

    with pytest.raises(ValueError, match="action_name"):
        from sofia.capability.model import Capability
        from sofia.external.capability import (
            ExternalIntegrationCapability,
        )

        ExternalIntegrationCapability(
            capability=Capability(
                name="external.observe.home-assistant",
                description="observe",
            ),
            system=system,
            kind=ExternalCapabilityKind.OBSERVE,
            adapter_name=adapter.name,
            action_name="light.turn_on",
        )


def test_action_capability_requires_authentication() -> None:
    system = _system()
    adapter = FakeActionAdapter(system)

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = _capability_system()

    registration = ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=None,
    )
    registration.register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.FAILED
    assert not adapter.actions


def test_authenticated_and_authorized_action_executes() -> None:
    system = _system()
    adapter = FakeActionAdapter(system)

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = _capability_system()

    registration = ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_authentication(system),
    )
    registration.register()

    result = capability_system.execute(
        _request(
            integration.capability,
            parameters={
                "entity_id": "light.office",
                "brightness": 50,
            },
        )
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert len(adapter.actions) == 1

    action = adapter.actions[0]
    assert action.action_name == "light.turn_on"
    assert action.parameters["entity_id"] == "light.office"


def test_authentication_does_not_bypass_authorization() -> None:
    system = _system()
    adapter = FakeActionAdapter(system)

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = _capability_system(
        authorized=False,
    )

    registration = ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_authentication(system),
    )
    registration.register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.UNAUTHORIZED
    assert not adapter.actions


def test_runtime_parameters_cannot_replace_canonical_action() -> None:
    system = _system()
    adapter = FakeActionAdapter(system)

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = _capability_system()

    ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_authentication(system),
    ).register()

    result = capability_system.execute(
        _request(
            integration.capability,
            parameters={
                "action_name": "light.turn_off",
            },
        )
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert adapter.actions[0].action_name == "light.turn_on"
    assert adapter.actions[0].parameters["action_name"] == "light.turn_off"


def test_failed_external_result_remains_explicit() -> None:
    system = _system()

    failed_result = ExternalSystemResult(
        system_id=system.system_id,
        kind=ExternalSystemResultKind.FAILED,
        error="External device rejected the operation.",
    )

    adapter = FakeActionAdapter(
        system,
        result=failed_result,
    )

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = _capability_system()

    ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_authentication(system),
    ).register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert isinstance(result.evidence, ExternalSystemResult)
    assert result.evidence.kind is ExternalSystemResultKind.FAILED
    assert result.evidence.error == (
        "External device rejected the operation."
    )


def test_unavailable_external_result_remains_explicit() -> None:
    system = _system()

    unavailable_result = ExternalSystemResult(
        system_id=system.system_id,
        kind=ExternalSystemResultKind.UNAVAILABLE,
        error="External system is offline.",
    )

    adapter = FakeActionAdapter(
        system,
        result=unavailable_result,
    )

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = _capability_system()

    ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_authentication(system),
    ).register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.SUCCESS
    assert isinstance(result.evidence, ExternalSystemResult)
    assert result.evidence.kind is ExternalSystemResultKind.UNAVAILABLE


def test_wrong_result_system_is_rejected() -> None:
    system = _system()

    other_system = ExternalSystem(
        system_id="plex",
        name="Plex",
        system_type=ExternalSystemType.SERVICE,
    )

    adapter = FakeActionAdapter(
        system,
        result=ExternalSystemResult(
            system_id=other_system.system_id,
            kind=ExternalSystemResultKind.SUCCESS,
            evidence={"unexpected": True},
            observed_at=datetime.now(timezone.utc),
            adapter_name="fake-action-adapter",
        ),
    )

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = _capability_system()

    ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_authentication(system),
    ).register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.FAILED
    assert result.evidence is None


def test_result_adapter_identity_is_validated() -> None:
    system = _system()

    adapter = FakeActionAdapter(
        system,
        result=ExternalSystemResult(
            system_id=system.system_id,
            kind=ExternalSystemResultKind.SUCCESS,
            evidence={"ok": True},
            observed_at=datetime.now(timezone.utc),
            adapter_name="different-adapter",
        ),
    )

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    capability_system = _capability_system()

    ExternalCapabilityRegistration(
        capability_system=capability_system,
        integration=integration,
        adapter=adapter,
        authentication=_authentication(system),
    ).register()

    result = capability_system.execute(
        _request(integration.capability)
    )

    assert result.kind is CapabilityResultKind.FAILED


def test_action_capability_does_not_expose_arbitrary_execution_api() -> None:
    system = _system()
    adapter = FakeActionAdapter(system)

    integration = create_external_action_capability(
        system=system,
        adapter=adapter,
        action_name="light.turn_on",
    )

    assert not hasattr(integration, "execute")
    assert not hasattr(integration, "run")
    assert not hasattr(integration, "command")
    assert not hasattr(integration, "shell")
    assert not hasattr(integration, "script")