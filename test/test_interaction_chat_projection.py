"""Headless chat integration tests; never call the model or the real desktop."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.embodiment.store import AvatarStore
from sofia.interaction.chat import InteractiveConversationService

AVATAR = Path(__file__).resolve().parents[1] / "src" / "sofia" / "data" / "avatar.json"


def _service(monkeypatch, content, *, personality=True, avatar=True):
    original_user = CognitiveMessage(role=CognitiveRole.USER, content=content)
    original = CognitiveRequest(messages=(original_user,))
    monkeypatch.setattr(EmotionalConversationService, "_build_request", lambda self: original)
    user = SimpleNamespace(id="message-1", session_id="session-1",
                           role=ConversationRole.USER, content=content,
                           created_at=datetime.now(timezone.utc))
    monkeypatch.setattr(InteractiveConversationService, "messages", lambda self: (user,))
    service = object.__new__(InteractiveConversationService)
    service._runtime = SimpleNamespace(
        personality=object() if personality else None,
        embodiment=AvatarStore(AVATAR).load() if avatar else None,
    )
    return service, original


def test_text_ear_interaction_projects_same_shared_policy_without_renderer(monkeypatch):
    service, original = _service(monkeypatch, "*taps your left ear*")
    result = service._build_request()
    assert result.messages[0].role is CognitiveRole.SYSTEM
    assert '"region_id": "left-ear"' in result.messages[0].content
    assert '"gesture": "tap"' in result.messages[0].content
    assert '"policy_status": "accepted"' in result.messages[0].content
    assert "*one ear flicks*" in result.messages[0].content
    assert "NOT sensed" in result.messages[0].content
    assert result.messages[-1] is original.messages[-1]
    assert original.messages[0].content == "*taps your left ear*"


def test_sensitive_region_is_recognized_without_mandatory_favorable_reaction(monkeypatch):
    service, _ = _service(monkeypatch, "*touches your groin*")
    result = service._build_request()
    prompt = result.messages[0].content
    assert '"policy_status": "accepted"' in prompt
    assert '"region_id": "groin"' in prompt
    assert '"gesture": "touch"' in prompt
    assert "does NOT mean" in prompt
    assert "negatively" in prompt
    assert '"optional_representational_text_cues": []' in prompt
    assert '"possible_modeled_emotions_not_actual_feelings": [' in prompt
    assert '"fondness"' in prompt and '"caution"' in prompt and '"frustration"' in prompt


@pytest.mark.parametrize("content", ["Tell me about your tail", "How do I pat your head?", "```pats your head```"])
def test_discussion_and_code_do_not_generate_an_interaction_projection(monkeypatch, content):
    service, original = _service(monkeypatch, content)
    assert service._build_request() is original


@pytest.mark.parametrize("personality,avatar", [(False, True), (True, False)])
def test_missing_personality_or_canonical_embodiment_does_not_invent_one(monkeypatch, personality, avatar):
    service, original = _service(monkeypatch, "*pats your head*",
                                 personality=personality, avatar=avatar)
    assert service._build_request() is original
