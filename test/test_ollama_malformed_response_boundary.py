"""CA-1207: malformed model responses must fail closed at the provider boundary."""
from types import SimpleNamespace

import pytest

from sofia.cognition.model import CognitiveRequest
from sofia.cognition.provider import LLMProviderError
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config import create_default_configuration


class MalformedClient:
    def __init__(self, response):
        self.response = response

    def chat(self, **kwargs):
        return self.response


@pytest.mark.parametrize("payload", [
    None,
    SimpleNamespace(message=None),
    SimpleNamespace(message=SimpleNamespace(content=123, tool_calls=())),
    SimpleNamespace(message=SimpleNamespace(content="", tool_calls=(None,))),
])
def test_malformed_ollama_payload_raises_provider_error(payload):
    provider = OllamaProvider(
        create_default_configuration().provider,
        client=MalformedClient(payload),
    )
    with pytest.raises(LLMProviderError):
        provider.respond(CognitiveRequest(messages=()))


def test_invalid_json_tool_arguments_fail_closed():
    tool_call = SimpleNamespace(
        function=SimpleNamespace(name="example", arguments="{not-json"),
        id="call-1",
    )
    response = SimpleNamespace(
        message=SimpleNamespace(content="", tool_calls=(tool_call,)),
    )
    provider = OllamaProvider(
        create_default_configuration().provider,
        client=MalformedClient(response),
    )
    with pytest.raises(LLMProviderError, match="invalid JSON"):
        provider.respond(CognitiveRequest(messages=()))

def test_tool_call_response_does_not_trigger_quality_retry():
    """An action candidate must never be sent through text-only repair."""
    class CapturingClient:
        calls = 0

        def chat(self, **kwargs):
            self.calls += 1
            return SimpleNamespace(message=SimpleNamespace(
                content="",
                tool_calls=(SimpleNamespace(function=SimpleNamespace(
                    name="example", arguments={"ok": True}), id="call-1"),),
            ))

    client = CapturingClient()
    provider = OllamaProvider(create_default_configuration().provider, client=client)
    result = provider.respond(CognitiveRequest(messages=()))
    assert client.calls == 1
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "example"

def test_disallowed_tools_are_not_sent_to_ollama():
    from sofia.cognition.model import CognitiveToolDefinition

    class CapturingClient:
        kwargs = None

        def chat(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                message=SimpleNamespace(content="Allowed text.", tool_calls=()),
            )

    client = CapturingClient()
    provider = OllamaProvider(create_default_configuration().provider, client=client)
    request = CognitiveRequest(
        messages=(),
        tools=(CognitiveToolDefinition(
            name="dangerous_action",
            description="A tool that must not be exposed to this request.",
            parameters={"type": "object"},
        ),),
        allow_tools=False,
    )
    result = provider.respond(request)
    assert result.content == "Allowed text."
    assert "tools" not in client.kwargs
