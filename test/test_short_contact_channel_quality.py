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
    ("Sofía?", " ".join(f"distinctword{n}" for n in range(80)), "short_contact_monologue"),
    ("Sofía?", "I feel the familiar ache of longing whenever we drift apart, with a sadness there too.", "short_contact_dependency_escalation"),
    ("Sofía?", 'A flash of a crooked grin meets the call. "Right here," comes the soft reply.', "short_contact_third_person_narration"),
    ("hru", "Just fine, thanks for asking. How about you? Anything interesting happening today?", "short_contact_question_stack"),
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


def test_short_contact_repair_avoids_interview_and_third_person_narration():
    client = _Client(
        "Just fine, thanks for asking. How about you? Anything interesting today?",
        "Doing well, Sparks. What about you?",
    )
    provider = _provider_for_short_contact(client)
    assert provider.respond(request("hru")).content == "Doing well, Sparks. What about you?"
    assert len(client.calls) == 2


def _provider_for_short_contact(client):
    return OllamaProvider(
        ProviderConfiguration(provider="ollama", model="test-model"),
        client=client,
    )


def test_short_contact_third_person_double_failure_falls_back_naturally():
    client = _Client(
        'A flash of a crooked grin meets the call. "Right here," comes the soft reply.',
        'A soft reply comes from across the room.',
    )
    assert _provider_for_short_contact(client).respond(request("Sofía?")).content == (
        "I'm here, Sparks. What's up?"
    )
    assert len(client.calls) == 2
