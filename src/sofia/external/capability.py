from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from sofia.capability.model import (
    Capability,
    CapabilityRequest,
)
from sofia.capability.system import CapabilitySystem
from sofia.external.adapter import ExternalIntegrationAdapter
from sofia.external.authentication import (
    ExternalAuthentication,
)
from sofia.external.model import (
    ExternalSystem,
    ExternalSystemAction,
    ExternalSystemObservation,
    ExternalSystemResult,
)


class ExternalCapabilityKind(str, Enum):
    OBSERVE = "observe"
    ACTION = "action"


@dataclass(frozen=True)
class ExternalIntegrationCapability:
    """
    Canonical capability binding for an external system.

    The capability describes what an adapter-backed integration can
    provide. It does not authorize invocation.
    """

    capability: Capability
    system: ExternalSystem
    kind: ExternalCapabilityKind
    adapter_name: str
    authentication_required: bool = True
    action_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability, Capability):
            raise TypeError(
                "capability must be a Capability."
            )

        if not isinstance(self.system, ExternalSystem):
            raise TypeError(
                "system must be an ExternalSystem."
            )

        if not isinstance(
            self.kind,
            ExternalCapabilityKind,
        ):
            raise TypeError(
                "kind must be an ExternalCapabilityKind."
            )

        if not isinstance(self.adapter_name, str):
            raise TypeError(
                "adapter_name must be a string."
            )

        if not self.adapter_name.strip():
            raise ValueError(
                "adapter_name must not be empty."
            )

        if not isinstance(
            self.authentication_required,
            bool,
        ):
            raise TypeError(
                "authentication_required must be a bool."
            )

        if self.action_name is not None:
            if not isinstance(self.action_name, str):
                raise TypeError(
                    "action_name must be a string or None."
                )

            if not self.action_name.strip():
                raise ValueError(
                    "action_name must not be empty."
                )

        if (
            self.kind is ExternalCapabilityKind.OBSERVE
            and self.action_name is not None
        ):
            raise ValueError(
                "Observation capabilities must not define an "
                "action_name."
            )

        if (
            self.kind is ExternalCapabilityKind.ACTION
            and self.action_name is None
        ):
            raise ValueError(
                "Action capabilities must define an action_name."
            )


class ExternalCapabilityRegistration:
    """
    Registers an adapter-backed external capability with the existing
    CapabilitySystem.

    Authorization remains entirely owned by CapabilitySystem.
    """

    def __init__(
        self,
        capability_system: CapabilitySystem,
        integration: ExternalIntegrationCapability,
        adapter: ExternalIntegrationAdapter,
        authentication: ExternalAuthentication | None = None,
    ) -> None:
        if not isinstance(
            capability_system,
            CapabilitySystem,
        ):
            raise TypeError(
                "capability_system must be a CapabilitySystem."
            )

        if not isinstance(
            integration,
            ExternalIntegrationCapability,
        ):
            raise TypeError(
                "integration must be an "
                "ExternalIntegrationCapability."
            )

        if not isinstance(
            adapter,
            ExternalIntegrationAdapter,
        ):
            raise TypeError(
                "adapter must be an ExternalIntegrationAdapter."
            )

        if adapter.system != integration.system:
            raise ValueError(
                "adapter system must match the integration system."
            )

        if adapter.name != integration.adapter_name:
            raise ValueError(
                "adapter name must match the integration capability."
            )

        if authentication is not None:
            if not isinstance(
                authentication,
                ExternalAuthentication,
            ):
                raise TypeError(
                    "authentication must be an "
                    "ExternalAuthentication or None."
                )

            if (
                authentication.system_id
                != integration.system.system_id
            ):
                raise ValueError(
                    "authentication system_id must match the "
                    "integration system."
                )

        self._capability_system = capability_system
        self._integration = integration
        self._adapter = adapter
        self._authentication = authentication

    @property
    def capability(self) -> Capability:
        return self._integration.capability

    @property
    def integration(self) -> ExternalIntegrationCapability:
        return self._integration

    @property
    def adapter(self) -> ExternalIntegrationAdapter:
        return self._adapter

    @property
    def authentication(self) -> ExternalAuthentication | None:
        return self._authentication

    def register(self) -> None:
        """
        Register the canonical external capability.

        CapabilitySystem remains responsible for resolving the
        canonical capability and evaluating authorization.
        """
        self._capability_system.register(
            self._integration.capability,
            self._execute,
        )

    def _execute(
        self,
        request: CapabilityRequest,
    ) -> ExternalSystemObservation | ExternalSystemResult:
        if request.capability != self._integration.capability:
            raise ValueError(
                "Capability request does not match the "
                "external integration capability."
            )

        if (
            self._integration.authentication_required
            and (
                self._authentication is None
                or not self._authentication.is_authenticated
            )
        ):
            raise PermissionError(
                "External integration authentication is not verified."
            )

        if self._integration.kind is ExternalCapabilityKind.OBSERVE:
            observation = self._adapter.observe()

            if not isinstance(
                observation,
                ExternalSystemObservation,
            ):
                raise TypeError(
                    "External integration adapter must return an "
                    "ExternalSystemObservation."
                )

            if observation.system != self._integration.system:
                raise ValueError(
                    "Adapter returned an observation for a different "
                    "external system."
                )

            return observation

        if self._integration.kind is ExternalCapabilityKind.ACTION:
            action_name = self._integration.action_name

            if action_name is None:
                raise ValueError(
                    "Action capability is missing its action_name."
                )

            action = ExternalSystemAction(
                system_id=self._integration.system.system_id,
                action_name=action_name,
                parameters=request.parameters,
            )

            result = self._adapter.execute_action(action)

            if not isinstance(
                result,
                ExternalSystemResult,
            ):
                raise TypeError(
                    "External integration adapter must return an "
                    "ExternalSystemResult."
                )

            if result.system_id != self._integration.system.system_id:
                raise ValueError(
                    "Adapter returned a result for a different "
                    "external system."
                )

            if result.adapter_name is not None:
                if result.adapter_name != self._adapter.name:
                    raise ValueError(
                        "External system result adapter_name does not "
                        "match the registered adapter."
                    )

            return result

        raise ValueError(
            "Unsupported external integration capability kind."
        )


def create_external_observation_capability(
    system: ExternalSystem,
    adapter: ExternalIntegrationAdapter,
    *,
    capability_name: str | None = None,
    description: str | None = None,
    authentication_required: bool = True,
) -> ExternalIntegrationCapability:
    """
    Construct the canonical capability descriptor for observing one
    external system.
    """

    if not isinstance(system, ExternalSystem):
        raise TypeError("system must be an ExternalSystem.")

    if not isinstance(
        adapter,
        ExternalIntegrationAdapter,
    ):
        raise TypeError(
            "adapter must be an ExternalIntegrationAdapter."
        )

    if adapter.system != system:
        raise ValueError(
            "adapter system must match the external system."
        )

    name = capability_name or (
        f"external.observe.{system.system_id}"
    )

    text = description or (
        f"Observe external system '{system.name}'."
    )

    capability = Capability(
        name=name,
        description=text,
    )

    return ExternalIntegrationCapability(
        capability=capability,
        system=system,
        kind=ExternalCapabilityKind.OBSERVE,
        adapter_name=adapter.name,
        authentication_required=authentication_required,
    )


def create_external_action_capability(
    system: ExternalSystem,
    adapter: ExternalIntegrationAdapter,
    action_name: str,
    *,
    capability_name: str | None = None,
    description: str | None = None,
    authentication_required: bool = True,
) -> ExternalIntegrationCapability:
    """
    Construct a canonical capability descriptor for one specific
    structured external action.

    The action name is fixed by the registered capability. Runtime
    request parameters cannot replace it.
    """

    if not isinstance(system, ExternalSystem):
        raise TypeError("system must be an ExternalSystem.")

    if not isinstance(
        adapter,
        ExternalIntegrationAdapter,
    ):
        raise TypeError(
            "adapter must be an ExternalIntegrationAdapter."
        )

    if adapter.system != system:
        raise ValueError(
            "adapter system must match the external system."
        )

    if not isinstance(action_name, str):
        raise TypeError(
            "action_name must be a string."
        )

    if not action_name.strip():
        raise ValueError(
            "action_name must not be empty."
        )

    name = capability_name or (
        f"external.action.{system.system_id}.{action_name}"
    )

    text = description or (
        f"Perform external action '{action_name}' on "
        f"'{system.name}'."
    )

    capability = Capability(
        name=name,
        description=text,
    )

    return ExternalIntegrationCapability(
        capability=capability,
        system=system,
        kind=ExternalCapabilityKind.ACTION,
        adapter_name=adapter.name,
        authentication_required=authentication_required,
        action_name=action_name,
    )