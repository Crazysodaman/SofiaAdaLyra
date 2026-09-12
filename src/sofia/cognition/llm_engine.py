from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
)
from sofia.cognition.provider import LLMProvider
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
        return self.provider.respond(request)