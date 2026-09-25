import pytest

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.model import ProviderConfiguration


class FakeOllamaResponse:
    def __init__(self):
        self.message = type(
            "Message",
            (),
            {
                "content": "ok",
                "tool_calls": (),
            },
        )()


class FakeOllamaClient:
    def __init__(self):
        self.kwargs = None

    def chat(self, **kwargs):
        self.kwargs = kwargs
        return FakeOllamaResponse()


def make_request() -> CognitiveRequest:
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
            ),
        ),
    )


@pytest.mark.parametrize("context_size", [18000, 32768])
def test_ollama_generation_configuration_is_translated(context_size):
    configuration = ProviderConfiguration(
        provider="ollama",
        model="qwen3:14b",
        temperature=0.2,
        seed=42,
        context_size=context_size,
        thinking=True,
    )

    client = FakeOllamaClient()

    provider = OllamaProvider(
        configuration=configuration,
        client=client,
    )

    provider.respond(make_request())

    assert client.kwargs["model"] == "qwen3:14b"
    assert client.kwargs["options"] == {
        "temperature": 0.2,
        "seed": 42,
        "num_ctx": context_size,
    }
    assert client.kwargs["think"] is True


def test_ollama_generation_options_are_omitted_when_unconfigured():
    configuration = ProviderConfiguration(
        provider="ollama",
        model="qwen3:14b",
    )

    client = FakeOllamaClient()

    provider = OllamaProvider(
        configuration=configuration,
        client=client,
    )

    provider.respond(make_request())

    assert "options" not in client.kwargs
    assert "think" not in client.kwargs