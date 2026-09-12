from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
)
from sofia.cognition.provider import (
    LLMProvider,
    LLMProviderError,
)


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