"""Provider-neutral cognition interfaces; construction grants no authority."""
from abc import ABC, abstractmethod

from sofia.sdk.cognition_model import CognitiveRequest, CognitiveResponse


class CognitiveEngineError(Exception):
    """Raised when a cognitive engine fails."""


class CognitiveEngine(ABC):
    """Portable computation boundary, separate from personal Core identity."""

    @abstractmethod
    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        raise NotImplementedError


class LLMProviderError(Exception):
    """Raised when an LLM provider fails."""


class LLMProvider(ABC):
    """External model adapter; no owner, tool or writer authorization."""

    @abstractmethod
    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        raise NotImplementedError
