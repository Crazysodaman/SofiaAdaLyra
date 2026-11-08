"""CA-1207: malformed model responses must fail closed at the provider boundary."""
from types import SimpleNamespace

import pytest

from sofia.core.cognition.model import CognitiveRequest
from sofia.core.cognition.provider import LLMProviderError
from sofia.core.cognition.providers.ollama_provider import OllamaProvider
from sofia.platform.core_worker.ollama_transport import GenericOllamaProvider
from sofia.platform.config import create_default_configuration


class MalformedClient:
    def __init__(self, response):
        self.response = response

    def chat(self, **kwargs):
        return self.response


@pytest.mark.parametrize("payload", [
    None,
    SimpleNamespace(message=None),
    SimpleNamespace(message=SimpleNamespace()),
    SimpleNamespace(message=SimpleNamespace(content=123, tool_calls=())),
    SimpleNamespace(message=SimpleNamespace(content="", tool_calls=(None,))),
    SimpleNamespace(message=SimpleNamespace(content="", tool_calls="bad")),
    SimpleNamespace(message=SimpleNamespace(content="", tool_calls=123)),
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
    from sofia.core.cognition.model import CognitiveToolDefinition

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


def test_text_only_request_rejects_unexpected_model_tool_call():
    call = SimpleNamespace(
        function=SimpleNamespace(name="unexpected", arguments={}),
        id="call-2",
    )
    payload = SimpleNamespace(
        message=SimpleNamespace(content="", tool_calls=(call,)),
    )
    provider = OllamaProvider(
        create_default_configuration().provider,
        client=MalformedClient(payload),
    )
    with pytest.raises(LLMProviderError, match="text-only"):
        provider.respond(CognitiveRequest(messages=(), allow_tools=False))


@pytest.mark.parametrize("raw", [
    '{"path":"safe","path":"unsafe"}',
    '{"gain":NaN}',
    '{"gain":Infinity}',
    '{"gain":-Infinity}',
    '{"config":{"scope":"owner","scope":"other"}}',
])
def test_ambiguous_or_nonfinite_json_tool_arguments_are_rejected(raw):
    tool_call = SimpleNamespace(
        function=SimpleNamespace(name="inspect", arguments=raw),
        id="call-raw",
    )
    provider = OllamaProvider(
        create_default_configuration().provider,
        client=MalformedClient(SimpleNamespace(message=SimpleNamespace(
            content="", tool_calls=(tool_call,),
        ))),
    )
    with pytest.raises(LLMProviderError, match="invalid JSON"):
        provider.respond(CognitiveRequest(messages=()))


@pytest.mark.parametrize("arguments", [
    {"x": float("nan")},
    {"x": float("inf")},
    {1: "non-string key"},
    {"x": object()},
    {"x": {"y": tuple(range(2))}},
    {"x": "a" * 65537},
    {"x": [0] * 4097},
    {"x": "ok", "y": "\ud800"},
])
def test_native_tool_arguments_must_be_bounded_json(arguments):
    tool_call = SimpleNamespace(
        function=SimpleNamespace(name="inspect", arguments=arguments),
        id="call-native",
    )
    provider = OllamaProvider(
        create_default_configuration().provider,
        client=MalformedClient(SimpleNamespace(message=SimpleNamespace(
            content="", tool_calls=(tool_call,),
        ))),
    )
    with pytest.raises(LLMProviderError):
        provider.respond(CognitiveRequest(messages=()))


def test_tool_arguments_reject_cycle_and_excessive_nesting():
    circular = {}
    circular["self"] = circular
    deep = {}
    pointer = deep
    for _ in range(20):
        pointer["child"] = {}
        pointer = pointer["child"]
    for arguments in (circular, deep):
        tool = SimpleNamespace(
            function=SimpleNamespace(name="inspect", arguments=arguments),
        )
        provider = OllamaProvider(
            create_default_configuration().provider,
            client=MalformedClient(SimpleNamespace(message=SimpleNamespace(
                content="", tool_calls=(tool,),
            ))),
        )
        with pytest.raises(LLMProviderError, match="safety limits"):
            provider.respond(CognitiveRequest(messages=()))


def test_tool_call_fanout_is_capped_before_candidate_dispatch():
    calls = tuple(SimpleNamespace(
        function=SimpleNamespace(name="inspect", arguments={"ok": True}),
    ) for _ in range(17))
    provider = OllamaProvider(
        create_default_configuration().provider,
        client=MalformedClient(SimpleNamespace(message=SimpleNamespace(
            content="", tool_calls=calls,
        ))),
    )
    with pytest.raises(LLMProviderError, match="too many tool calls"):
        provider.respond(CognitiveRequest(messages=()))


def test_valid_bounded_nested_tool_arguments_keep_original_values():
    arguments = '{"nested":{"path":"café","flags":[true,null,3.5]}}'
    call = SimpleNamespace(
        function=SimpleNamespace(name="inspect", arguments=arguments),
        id="call-valid",
    )
    provider = OllamaProvider(
        create_default_configuration().provider,
        client=MalformedClient(SimpleNamespace(message=SimpleNamespace(
            content="", tool_calls=(call,),
        ))),
    )
    result = provider.respond(CognitiveRequest(messages=()))
    assert result.tool_calls[0].arguments == {
        "nested": {"path": "café", "flags": [True, None, 3.5]},
    }
    assert result.tool_calls[0].call_id == "call-valid"


def test_ollama_rejects_unpaired_surrogate_content_before_persistence():
    model = SimpleNamespace(message=SimpleNamespace(
        content="unpaired " + chr(0xD800), tool_calls=(),
    ))
    provider = OllamaProvider(
        create_default_configuration().provider,
        client=MalformedClient(model),
    )
    with pytest.raises(LLMProviderError, match="Unicode"):
        provider.respond(CognitiveRequest(messages=()))

@pytest.mark.parametrize("provider_class", [
    OllamaProvider,
    GenericOllamaProvider,
])
@pytest.mark.parametrize("content", ["", "   \n\t", None])
def test_empty_ollama_completion_fails_closed_instead_of_becoming_canned_chat(
    provider_class, content,
):
    """Thinking-only/blank model output is a failed inference, not a reply."""
    response = SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=()),
    )
    provider = provider_class(
        create_default_configuration().provider,
        client=MalformedClient(response),
    )
    with pytest.raises(LLMProviderError, match="empty cognitive response"):
        provider.respond(CognitiveRequest(messages=(), allow_tools=False))

@pytest.mark.parametrize("provider_class", [
    OllamaProvider,
    GenericOllamaProvider,
])
@pytest.mark.parametrize("cause", [
    TimeoutError("disposable Ollama read timeout"),
    ConnectionError("disposable Ollama offline"),
    RuntimeError("llama-server binary not found"),
])
def test_provider_outage_does_not_trigger_quality_repair_or_fake_chat(
    provider_class, cause,
):
    class FailingClient:
        calls = 0

        def chat(self, **kwargs):
            self.calls += 1
            raise cause

    client = FailingClient()
    provider = provider_class(
        create_default_configuration().provider,
        client=client,
    )
    with pytest.raises(LLMProviderError) as failed:
        provider.respond(CognitiveRequest(messages=(), allow_tools=False))
    assert failed.value.__cause__ is cause
    assert client.calls == 1
    assert "llama-server" not in str(failed.value)
    assert "disposable" not in str(failed.value)



def test_missing_model_error_then_recovery_without_canned_replies():
    """Simulated missing-model error and recovery; NOT a live-host test."""
    from ollama import ResponseError
    from sofia.platform.config.model import ProviderConfiguration

    class MissingThenAvailableClient:
        def __init__(self):
            self.calls = 0

        def chat(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise ResponseError("model not found in synthetic fixture", status_code=404)
            return SimpleNamespace(message=SimpleNamespace(
                content="A circuit breaker interrupts overloads to protect wiring.",
                tool_calls=(),
            ))

    request = CognitiveRequest(messages=(), allow_tools=False)
    for provider_class in (GenericOllamaProvider, OllamaProvider):
        client = MissingThenAvailableClient()
        provider = provider_class(
            ProviderConfiguration(provider="ollama", model="missing:disposable"),
            client=client,
        )
        with pytest.raises(LLMProviderError) as fail:
            provider.respond(request)
        assert isinstance(fail.value.__cause__, ResponseError)
        assert client.calls == 1, "The provider must not invent a model retry"
        success = provider.respond(request)
        assert success.content == "A circuit breaker interrupts overloads to protect wiring."
        assert client.calls == 2


def test_nonstreamed_connection_reset_is_not_assistant_text():
    """Current production chat is non-streaming; this is a transport reset."""

    class ResetClient:
        def chat(self, **kwargs):
            raise ConnectionResetError("synthetic mid-response connection loss")

    provider = GenericOllamaProvider(
        create_default_configuration().provider, client=ResetClient(),
    )
    with pytest.raises(LLMProviderError) as error:
        provider.respond(CognitiveRequest(messages=(), allow_tools=False))
    assert isinstance(error.value.__cause__, ConnectionResetError)
    assert "mid-response" not in str(error.value)
