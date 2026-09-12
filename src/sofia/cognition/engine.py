from abc import ABC, abstractmethod

from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
)


class CognitiveEngineError(Exception):
    """Raised when a cognitive engine fails."""


class CognitiveEngine(ABC):
    """
    Provider-neutral contract for Sofía's cognitive engine.
    """

    @abstractmethod
    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        """
        Process a cognitive request and return a response.
        """
        raise NotImplementedError