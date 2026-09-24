"""Offline conversation projection tests without contacting Ollama."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sofia.application.conversation_service import ConversationService
from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.personality.emotion import EmotionalJournal


def _service(monkeypatch, tmp_path, *, personality=True):
    request = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content='Good girl. *Head pats.*',
    ),))
    message = SimpleNamespace(
        id='user-message-1', content='Good girl. *Head pats.*',
        role=ConversationRole.USER,
        created_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(ConversationService, '_build_request', lambda self: request)
    monkeypatch.setattr(EmotionalConversationService, 'messages', lambda self: (message,))
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(personality=object() if personality else None)
    service._emotional_journal = EmotionalJournal(tmp_path / 'state.db')
    return service, request


def test_user_cue_reaches_llm_as_bounded_context_after_canonical_system(monkeypatch, tmp_path):
    service, original = _service(monkeypatch, tmp_path)
    result = service._build_request()
    assert result.messages[0].role is CognitiveRole.SYSTEM
    assert 'MODELED EMOTIONAL CONTEXT' in result.messages[0].content
    assert result.messages[-1] is original.messages[-1]
    assert len(service.emotional_journal.recent(now=datetime.now(timezone.utc))) == 1
    second = service._build_request()
    assert len(service.emotional_journal.recent(now=datetime.now(timezone.utc))) == 1
    assert second.messages[-1] is original.messages[-1]


def test_no_personality_means_no_implicit_persona_or_emotional_projection(monkeypatch, tmp_path):
    service, original = _service(monkeypatch, tmp_path, personality=False)
    assert service._build_request() is original
    assert service.emotional_journal.recent(now=datetime.now(timezone.utc)) == ()



def test_explicit_return_duration_reaches_reunion_appraisal(monkeypatch, tmp_path):
    departure = datetime.now(timezone.utc) - timedelta(days=7)
    request = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content="I'll be back in a week.",
    ),))
    user = SimpleNamespace(
        id="departure-plan", content="I'll be back in a week.",
        role=ConversationRole.USER, created_at=departure,
    )
    monkeypatch.setattr(ConversationService, "_build_request", lambda self: request)
    monkeypatch.setattr(
        EmotionalConversationService, "messages", lambda self: (user,),
    )
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(personality=object())
    service._emotional_journal = EmotionalJournal(tmp_path / "state.db")

    service._build_request()
    reunion_at = departure + timedelta(days=7)
    event_id = service.emotional_journal.observe_contact(
        subject="current user", message_id="return", occurred_at=reunion_at,
    )

    assert event_id == "reunion:return"
    event = service.emotional_journal.recent(now=reunion_at)[0]
    assert {"relief", "warmth", "fondness"} <= set(event.current_emotions)
    assert "anger" not in event.current_emotions
