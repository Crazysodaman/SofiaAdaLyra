from sofia.cognition.engine import (
    CognitiveEngine,
    CognitiveEngineError,
)
from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
)
from sofia.cognition.provider import (
    LLMProvider,
    LLMProviderError,
)
from sofia.config.model import ProviderConfiguration


class LLMCognitiveEngine(CognitiveEngine):
    """
    Cognitive engine backed by an external LLM provider.
    """

    def __init__(
        self,
        configuration: ProviderConfiguration,
        provider: LLMProvider,
    ):
        if not isinstance(provider, LLMProvider):
            raise TypeError(
                "LLMCognitiveEngine requires an LLMProvider."
            )

        self.configuration = configuration
        self.provider = provider

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        try:
            return self.provider.respond(request)

        except LLMProviderError as exc:
            raise CognitiveEngineError(
                "LLM provider failed to process the cognitive request."
            ) from exc