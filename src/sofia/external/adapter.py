from __future__ import annotations

from abc import ABC, abstractmethod

from sofia.external.model import (
    ExternalSystem,
    ExternalSystemAction,
    ExternalSystemObservation,
    ExternalSystemResult,
)


class ExternalIntegrationAdapter(ABC):
    """
    Integration boundary for one external system.

    An adapter knows how to communicate with an external system and
    convert responses into Sofía's structured models.

    The adapter does not:
    - grant authority,
    - evaluate authorization,
    - interpret natural-language requests,
    - register capabilities,
    - execute arbitrary commands,
    - own credentials,
    - or mutate external-system identity.

    Authentication and credential handling belong to the separate
    authentication boundary.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the stable adapter identifier.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def system(self) -> ExternalSystem:
        """
        Return the external system represented by this adapter.
        """
        raise NotImplementedError

    @abstractmethod
    def observe(self) -> ExternalSystemObservation:
        """
        Obtain structured observational evidence from the external
        system.
        """
        raise NotImplementedError

    def execute_action(
        self,
        action: ExternalSystemAction,
    ) -> ExternalSystemResult:
        """
        Execute one registered, structured external action.

        This method is deliberately non-abstract so observation-only
        adapters remain valid. Action-capable integrations must
        explicitly override it.

        Implementations must not interpret the action as a shell
        command, script, executable, or arbitrary code request.
        """
        raise NotImplementedError(
            "This external integration adapter does not support "
            "external actions."
        )