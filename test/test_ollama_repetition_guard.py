"""In-memory Ollama text-repeat tests; no live model, tools, or SQLite."""
from types import SimpleNamespace

from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
    CognitiveToolCall, CognitiveToolDefinition,
)
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.cognition.repetition_guard import (
    build_rephrase_request, is_near_duplicate_reply,
)
from sofia.config.model import ProviderConfiguration

_OLD = (
    '*ears twitch, tail swishes* I appreciate the gesture, but this is '
    'unexpected. I could be flattered, flustered, or confused. '
    'There is a certain boldness to it, and I like that. What was that about?'
)
_COPY = (
    '*ears twitch, tail swishes* I appreciate the gesture but this is... '
    'unexpected. I could be flattered, flustered, or confused! '
    'There is a certain boldness to it, and I like that. What was that about?'
)
_NEW = 'I would rather not narrate that gesture. Can we talk about the lab instead?'


def _message(role, content, **kwargs):
    return CognitiveMessage(role=role, content=content, **kwargs)


def _request(user='A distinct gesture.', *, tools=()):
    return CognitiveRequest(messages=(
        _message(CognitiveRole.SYSTEM, 'Canonical boundaries remain in force.'),
        _message(CognitiveRole.USER, 'An earlier gesture.'),
        _message(CognitiveRole.ASSISTANT, _OLD),
        _message(CognitiveRole.USER, user),
    ), tools=tools)


class _Client:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        next_response = self.outputs.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return SimpleNamespace(message=SimpleNamespace(content=next_response, tool_calls=()))


def _provider(client):
    return OllamaProvider(
        configuration=ProviderConfiguration(provider='ollama', model='test-model'),
        client=client,
    )


def test_near_verbatim_long_reply_is_detected_without_modifying_request():
    request = _request()
    original = request.messages
    assert is_near_duplicate_reply(request, CognitiveResponse(content=_COPY))
    retry = build_rephrase_request(request)
    assert retry.messages[-1] is request.messages[-1]
    assert retry.messages[:-2] == request.messages[:-1]
    assert retry.messages[-2].role is CognitiveRole.SYSTEM
    assert retry.tools == request.tools
    assert request.messages == original


def test_rephrased_response_is_returned_after_exactly_one_retry():
    client = _Client(_COPY, _NEW)
    response = _provider(client).respond(_request())
    assert response.content == _NEW
    assert len(client.calls) == 2
    assert client.calls[0]['messages'][-1]['content'] == 'A distinct gesture.'
    assert client.calls[1]['messages'][-1]['content'] == 'A distinct gesture.'
    assert client.calls[1]['messages'][-2]['role'] == 'system'
    assert len(client.calls[1]['messages']) == len(client.calls[0]['messages']) + 1


def test_no_retry_for_novel_or_short_reply():
    for output in (_NEW, 'Yes.'):
        client = _Client(output)
        assert _provider(client).respond(_request()).content == output
        assert len(client.calls) == 1


def test_explicit_repeat_request_does_not_retry():
    client = _Client(_COPY)
    assert _provider(client).respond(_request('Please repeat that exactly.')).content == _COPY
    assert len(client.calls) == 1


def test_tool_bearing_request_does_not_retry_or_reexecute_tools():
    tool = CognitiveToolDefinition(name='inspect', description='Read-only inspection.',
                                   parameters={'type': 'object'})
    client = _Client(_COPY)
    request = _request(tools=(tool,))
    assert _provider(client).respond(request).content == _COPY
    assert len(client.calls) == 1
    assert client.calls[0]['tools'][0]['function']['name'] == 'inspect'


def test_tool_history_and_tool_call_response_do_not_trigger_retry():
    tool_call = CognitiveToolCall(name='inspect', arguments={})
    history = CognitiveRequest(messages=(
        _message(CognitiveRole.ASSISTANT, _OLD, tool_calls=(tool_call,)),
        _message(CognitiveRole.USER, 'Inspect something.'),
    ))
    assert not is_near_duplicate_reply(history, CognitiveResponse(content=_COPY))
    assert not is_near_duplicate_reply(_request(), CognitiveResponse(
        content=_COPY, tool_calls=(tool_call,)))


def test_failed_or_still_duplicate_retry_falls_back_without_loop():
    for second in (RuntimeError('Ollama unavailable'), _COPY, '  '):
        client = _Client(_COPY, second)
        assert _provider(client).respond(_request()).content == _COPY
        assert len(client.calls) == 2


def test_provider_does_not_retry_empty_history_or_quoted_short_text():
    request = CognitiveRequest(messages=(_message(CognitiveRole.USER, 'Hello'),))
    assert not is_near_duplicate_reply(request, CognitiveResponse(content=_COPY))
    assert not is_near_duplicate_reply(_request(), CognitiveResponse(content='Sure.'))
