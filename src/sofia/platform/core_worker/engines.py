"""Generic worker computation, with no personal Core imports or state owners."""
from sofia.sdk.cognition_engine import (
    CognitiveEngine, CognitiveEngineError, LLMProvider, LLMProviderError,
)
from sofia.sdk.cognition_model import CognitiveRequest, CognitiveResponse
from sofia.platform.config.model import ProviderConfiguration


class LLMCognitiveEngine(CognitiveEngine):
    """Delegate a request to a separately configured model provider."""

    def __init__(self, configuration: ProviderConfiguration, provider: LLMProvider):
        if not isinstance(provider, LLMProvider):
            raise TypeError('LLMCognitiveEngine requires an LLMProvider.')
        self.configuration = configuration
        self.provider = provider

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        try:
            return self.provider.respond(request)
        except LLMProviderError as exc:
            raise CognitiveEngineError('LLM provider failed to process the cognitive request.') from exc


class TestCognitiveEngine(CognitiveEngine):
    """Deterministic computation for explicit disposable test workers."""

    def __init__(self, configuration: ProviderConfiguration):
        self.configuration = configuration

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        return CognitiveResponse(content='Test cognitive response.')
