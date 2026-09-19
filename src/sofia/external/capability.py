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
    ExternalSystemObservation,
)


class ExternalCapabilityKind(str, Enum):
    OBSERVE = "observe"


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

            if authentication.system_id != integration.system.system_id:
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

        The handler performs only integration-specific preconditions and
        observation. CapabilitySystem remains responsible for resolving
        the canonical capability and evaluating authorization.
        """

        self._capability_system.register(
            self._integration.capability,
            self._execute,
        )

    def _execute(
        self,
        request: CapabilityRequest,
    ) -> ExternalSystemObservation:
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

        if self._integration.kind is not ExternalCapabilityKind.OBSERVE:
            raise ValueError(
                "Unsupported external integration capability kind."
            )

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