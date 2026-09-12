from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
)
from sofia.config.model import ProviderConfiguration


class TestCognitiveEngine(CognitiveEngine):
    """
    Deterministic cognitive engine used for testing composition.
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
        return CognitiveResponse(
            content="Test cognitive response.",
        )