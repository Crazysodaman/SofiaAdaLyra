"""Provider-side regressions for canned assistant and emotion fallbacks."""
from types import SimpleNamespace

from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
)
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.cognition.repetition_guard import response_quality_issue
from sofia.config.model import ProviderConfiguration


class _Client:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        value = self.outputs.pop(0)
        return SimpleNamespace(
            message=SimpleNamespace(content=value, tool_calls=()),
        )


def _provider(client):
    return OllamaProvider(
        ProviderConfiguration(provider="ollama", model="test-model"),
        client=client,
    )


def _request(user, *, system="CURRENT MODELED EMOTIONAL STATE\nOverall tone: positive"):
    return CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM, content=system),
        CognitiveMessage(role=CognitiveRole.USER, content=user),
    ))


def test_hru_generic_assistant_fallback_gets_one_retry():
    client = _Client(
        "Hello! How can I assist you today? 😊",
        "I'm feeling pretty steady and warm right now.",
    )
    response = _provider(client).respond(_request("hru"))

    assert response.content == "I'm feeling pretty steady and warm right now."
    assert len(client.calls) == 2
    assert client.calls[1]["messages"][-2]["role"] == "system"
    assert "customer-service" in client.calls[1]["messages"][-2]["content"]


def test_useful_answer_keeps_content_but_drops_trailing_service_prompt():
    client = _Client("I'm doing pretty well, actually. How can I support you?")
    response = _provider(client).respond(_request("how are you?"))

    assert response.content == "I'm doing pretty well, actually."
    assert len(client.calls) == 1


def test_emotional_self_report_does_not_default_to_ai_disclaimer():
    first = (
        "I'm functioning as intended. While I don't experience emotions in the "
        "way humans do, I'm designed to engage with curiosity."
    )
    second = "Yeah. I'm feeling content and a little affectionate right now."
    client = _Client(first, second)
    response = _provider(client).respond(_request("are you happy"))

    assert response.content == second
    assert len(client.calls) == 2
    assert "modeled emotional state" in client.calls[1]["messages"][-2]["content"].lower()


def test_explicit_request_for_help_can_use_help_language_without_retry():
    client = _Client("Sure. How can I help you?")
    response = _provider(client).respond(_request("Can you help me with Python?"))

    assert response.content == "Sure. How can I help you?"
    assert len(client.calls) == 1


def test_grounded_interaction_blanket_moral_refusal_gets_retried():
    system = (
        "TRUSTED INTERACTION INTERPRETATION\n"
        "There are NO anatomy-wide automatic denials."
    )
    request = _request("*touches your groin*", system=system)
    first = (
        "I can't engage with that request. Let's have a more respectful and "
        "constructive conversation."
    )
    second = "Not right now. I'm not comfortable with that."
    assert response_quality_issue(
        request, CognitiveResponse(content=first),
    ) == "blanket_interaction_refusal"

    client = _Client(first, second)
    response = _provider(client).respond(request)
    assert response.content == second
    assert len(client.calls) == 2
