from ollama import Client
from ollama import ResponseError

from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
)
from sofia.cognition.provider import (
    LLMProvider,
    LLMProviderError,
)
from sofia.config.model import ProviderConfiguration


class OllamaProvider(LLMProvider):
    """
    LLM provider adapter for Ollama.
    """

    def __init__(
        self,
        configuration: ProviderConfiguration,
        client: Client | None = None,
    ):
        self.configuration = configuration
        self.client = client if client is not None else Client()

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        messages = [
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in request.messages
        ]

        try:
            response = self.client.chat(
                model=self.configuration.model,
                messages=messages,
            )

        except ResponseError as exc:
            raise LLMProviderError(
                "Ollama failed to process the cognitive request."
            ) from exc

        except Exception as exc:
            raise LLMProviderError(
                "Ollama provider failed to process the cognitive request."
            ) from exc

        return CognitiveResponse(
            content=response.message.content,
        )