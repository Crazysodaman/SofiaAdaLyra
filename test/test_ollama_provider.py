import pytest

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.cognition.provider import LLMProviderError
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.model import ProviderConfiguration


class FakeOllamaMessage:
    def __init__(self, content: str):
        self.content = content


class FakeOllamaResponse:
    def __init__(self, content: str):
        self.message = FakeOllamaMessage(content)


class FakeOllamaClient:
    def __init__(
        self,
        response: FakeOllamaResponse | None = None,
        error: Exception | None = None,
    ):
        self.response = response
        self.error = error
        self.model = None
        self.messages = None

    def chat(
        self,
        model,
        messages,
    ):
        self.model = model
        self.messages = messages

        if self.error is not None:
            raise self.error

        return self.response


def create_configuration() -> ProviderConfiguration:
    return ProviderConfiguration(
        provider="ollama",
        model="test-model",
    )


def test_ollama_provider_translates_request_and_response():
    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "Hello from Ollama."
        ),
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="You are Sofía.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
            ),
        ),
    )

    response = provider.respond(request)

    assert response.content == "Hello from Ollama."
    assert client.model == "test-model"
    assert client.messages == [
        {
            "role": "system",
            "content": "You are Sofía.",
        },
        {
            "role": "user",
            "content": "Hello.",
        },
    ]


def test_ollama_provider_preserves_assistant_messages():
    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "Continuation."
        ),
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
            ),
            CognitiveMessage(
                role=CognitiveRole.ASSISTANT,
                content="Hi, Sparks.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Continue.",
            ),
        ),
    )

    provider.respond(request)

    assert client.messages == [
        {
            "role": "user",
            "content": "Hello.",
        },
        {
            "role": "assistant",
            "content": "Hi, Sparks.",
        },
        {
            "role": "user",
            "content": "Continue.",
        },
    ]


def test_ollama_provider_translates_response_error():
    original_error = Exception(
        "Ollama connection failed."
    )

    client = FakeOllamaClient(
        error=original_error,
    )

    provider = OllamaProvider(
        configuration=create_configuration(),
        client=client,
    )

    with pytest.raises(
        LLMProviderError,
        match="Ollama provider failed to process the cognitive request.",
    ) as exc_info:
        provider.respond(
            CognitiveRequest(messages=()),
        )

    assert exc_info.value.__cause__ is original_error


def test_ollama_provider_requires_provider_configuration():
    configuration = create_configuration()

    client = FakeOllamaClient(
        response=FakeOllamaResponse(
            "Response."
        ),
    )

    provider = OllamaProvider(
        configuration=configuration,
        client=client,
    )

    assert provider.configuration is configuration
    assert provider.client is client