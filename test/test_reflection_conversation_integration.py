"""Verify reflection projection through the conversation boundary without an LLM."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sofia.application.conversation_service import ConversationService
from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.reflection import ReflectionJournal


def test_completed_reflection_reaches_conversation_once(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    request = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content='How did the testing go?',
    ),))
    user = SimpleNamespace(id='question-1', content='How did the testing go?',
                           role=ConversationRole.USER, created_at=now)
    monkeypatch.setattr(ConversationService, '_build_request', lambda self: request)
    monkeypatch.setattr(EmotionalConversationService, 'messages', lambda self: (user,))
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(personality=object())
    path = tmp_path / 'state.db'
    service._emotional_journal = EmotionalJournal(path)
    service._reflection_journal = ReflectionJournal(path)
    service.emotional_journal.record(
        event_id='verified-fix', source='observed', evidence_ref='pytest-result-1',
        description='The targeted tests passed.', emotions=('relief', 'joy'),
        occurred_at=now - timedelta(days=2),
    )
    result = service._build_request()
    assert result.messages[0].role is CognitiveRole.SYSTEM
    assert 'MODELED EMOTIONAL CONTEXT' in result.messages[0].content
    assert 'RECORDED REFLECTIONS' in result.messages[0].content
    assert 'verified-fix' in result.messages[0].content
    assert result.messages[-1] is request.messages[-1]
    count = len(service.reflection_journal.recent_thoughts())
    assert count >= 1
    service._build_request()
    assert len(ReflectionJournal(path).recent_thoughts()) == count


def test_reflections_do_not_create_a_persona_when_profile_absent(monkeypatch, tmp_path):
    request = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content='Hello',
    ),))
    monkeypatch.setattr(ConversationService, '_build_request', lambda self: request)
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(personality=None)
    service._emotional_journal = EmotionalJournal(tmp_path / 'state.db')
    service._reflection_journal = ReflectionJournal(tmp_path / 'state.db')
    assert service._build_request() is request
    assert service.reflection_journal.recent_thoughts() == ()
