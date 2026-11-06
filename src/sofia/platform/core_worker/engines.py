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


class TestLLMProvider(LLMProvider):
    """
    Deterministic LLM provider used for composition and integration tests.
    """

    def __init__(
        self,
        response: CognitiveResponse | None = None,
        error: LLMProviderError | None = None,
    ):
        if response is not None and error is not None:
            raise ValueError(
                "TestLLMProvider cannot define both response and error."
            )

        self.response = response
        self.error = error
        self.received_request: CognitiveRequest | None = None

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        self.received_request = request

        if self.error is not None:
            raise self.error

        if self.response is None:
            raise LLMProviderError(
                "TestLLMProvider has no configured response."
            )

        return self.response
