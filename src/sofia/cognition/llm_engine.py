from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
)
from sofia.config.model import ProviderConfiguration


class LLMCognitiveEngine(CognitiveEngine):
    """
    Provider-neutral cognitive engine for a real LLM backend.
    """

    def __init__(
        self,
        configuration: ProviderConfiguration,
    ):
        self.configuration = configuration

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        raise NotImplementedError