from __future__ import annotations

from abc import ABC, abstractmethod

from sofia.external.model import (
    ExternalSystem,
    ExternalSystemObservation,
)


class ExternalIntegrationAdapter(ABC):
    """
    Integration boundary for one external system.

    An adapter knows how to communicate with an external system and
    convert external responses into Sofía's structured observation
    model.

    The adapter does not:
    - grant authority,
    - evaluate authorization,
    - interpret natural-language requests,
    - register capabilities,
    - execute arbitrary commands,
    - own credentials,
    - or mutate external-system identity.

    Authentication and credential handling belong to the separate
    authentication boundary introduced later in Batch 21D.
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

        Implementations must return an ExternalSystemObservation and
        must not turn observation into an authorization decision.
        """
        raise NotImplementedError