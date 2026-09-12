from abc import ABC, abstractmethod

from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
)


class LLMProviderError(Exception):
    """Raised when an LLM provider fails."""


class LLMProvider(ABC):
    """
    Provider boundary for an external large language model.

    Implementations translate Sofía's provider-neutral cognitive
    contract into provider-specific operations.
    """

    @abstractmethod
    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        """
        Send a cognitive request to the provider and return its response.
        """
        raise NotImplementedError