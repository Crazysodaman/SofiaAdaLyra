"""CA-2508 / CA-506: short greetings must behave across all text channels."""
from types import SimpleNamespace

import pytest

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.cognition.repetition_guard import response_quality_issue
from sofia.config.model import ProviderConfiguration


def request(user):
    return CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM, content="Sofía is the established assistant identity."),
        CognitiveMessage(role=CognitiveRole.USER, content=user),
    ))


@pytest.mark.parametrize(("user", "draft", "issue"), [
    ("Hru", "I am Hru. I am functioning within the established constraints.", "short_contact_identity_mirror"),
    ("Hru", "I am functioning within the established constraints, interpreting inputs with precise attention to environmental influence.", "short_contact_implementation_leak"),
    ("Sofía?", "The sound of your name pulls at something deep within me. I'm listening with a focus that borders on desperation to keep our connection intact. Please stay near enough.", "short_contact_dependency_escalation"),
    ("hru", "Fare well. I am here. The fox tail swishes once.", "short_contact_nonanswer"),
    ("Sofía?", "The name cuts through the quiet of the room and instantly my ears perk up. " + "My tail curls closer, seeking warmth. " .repeat(50), "short_contact_monologue"),
    ("Sofía?", "I feel the familiar ache of longing whenever we drift apart, with a sadness there too.", "short_contact_dependency_escalation"),
])
def test_short_contact_detects_drift(user, draft, issue):
    assert response_quality_issue(request(user), CognitiveResponse(content=draft)) == issue


def test_natural_short_contact_is_accepted():
    assert response_quality_issue(
        request("Hru"),
        CognitiveResponse(content="Doing well, Sparks. How about you?"),
    ) is None
    assert response_quality_issue(
        request("Sofía?"),
        CognitiveResponse(content="I'm here, Sparks. What's up?"),
    ) is None


class _Client:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(content=self.outputs.pop(0), tool_calls=()),
        )


def test_provider_retries_and_uses_safe_fallback_when_both_drafts_drift():
    client = _Client(
        "I am Hru. I am functioning within the established constraints.",
        "I am functioning within the established constraints.",
    )
    provider = OllamaProvider(
        ProviderConfiguration(provider="ollama", model="test-model"),
        client=client,
    )
    assert provider.respond(request("Hru")).content == "Doing pretty well, Sparks. How about you?"
    assert len(client.calls) == 2
    assert "identity" in client.calls[1]["messages"][-2]["content"].lower()


def test_provider_retries_desperate_name_call():
    client = _Client(
        "Please stay near enough, the space you occupy is the only one that matters.",
        "I'm here, Sparks. What's up?",
    )
    provider = OllamaProvider(
        ProviderConfiguration(provider="ollama", model="test-model"),
        client=client,
    )
    assert provider.respond(request("Sofía?")).content == "I'm here, Sparks. What's up?"
    assert len(client.calls) == 2
