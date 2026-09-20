"""Clarifications preserve the original event and require a real user turn."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from sofia.application.conversation_service import ConversationService
from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.personality.clarification import ClarificationJournal
from sofia.personality.emotion import EmotionalJournal

NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


def _stores(tmp_path):
    path = tmp_path / 'sofia.db'
    emotions = EmotionalJournal(path)
    emotions.record(
        event_id='test-run:one', source='observed', evidence_ref='pytest:one',
        description='A reported test result showed one failure.',
        emotions=('frustration', 'curiosity'), occurred_at=NOW,
    )
    return emotions, ClarificationJournal(path)


def test_user_clarification_is_durable_idempotent_and_not_a_rewrite(tmp_path):
    emotions, notes = _stores(tmp_path)
    args = dict(event_id='test-run:one', message_id='user:one',
                content='Actually, that failure was an expected test.',
                created_at=NOW + timedelta(minutes=2))
    notes.record(**args)
    notes.record(**args)
    original = EmotionalJournal(tmp_path / 'sofia.db').recent(now=NOW + timedelta(minutes=3))[0]
    assert original.original_emotions == ('frustration', 'curiosity')
    assert original.current_emotions == original.original_emotions
    assert original.revision_count == 0
    saved = ClarificationJournal(tmp_path / 'sofia.db').recent(now=NOW + timedelta(minutes=3))
    assert len(saved) == 1
    assert saved[0].message_id == 'user:one'
    assert saved[0].original_emotions == saved[0].current_emotions
    assert 'expected test' in saved[0].content
    assert 'not independently verified' in notes.prompt_context(now=NOW + timedelta(minutes=3))
    assert 'actually' in notes.prompt_context(now=NOW + timedelta(minutes=3)).lower()


def test_later_reappraisal_preserves_origin_and_shows_why(tmp_path):
    emotions, notes = _stores(tmp_path)
    notes.record(event_id='test-run:one', message_id='user:two',
                 content='The failure was intentional.', created_at=NOW)
    emotions.revise(event_id='test-run:one', emotions=('relief', 'curiosity'),
                    reason='User clarified: intentionally failing test.',
                    revised_at=NOW + timedelta(minutes=1))
    saved = ClarificationJournal(tmp_path / 'sofia.db').recent(now=NOW + timedelta(minutes=2))[0]
    assert saved.original_emotions == ('frustration', 'curiosity')
    assert saved.current_emotions == ('relief', 'curiosity')
    assert saved.latest_revision_reason == 'User clarified: intentionally failing test.'
    assert 'intentionally failing test' in notes.prompt_context(now=NOW + timedelta(minutes=2))


def test_clarification_rejects_missing_event_conflicts_and_bad_dates(tmp_path):
    _, notes = _stores(tmp_path)
    args = dict(event_id='test-run:one', message_id='user:one',
                content='A clarification.', created_at=NOW)
    with pytest.raises(KeyError):
        notes.record(**{**args, 'event_id': 'invented'})
    notes.record(**args)
    with pytest.raises(ValueError, match='different content'):
        notes.record(**{**args, 'content': 'Changed after recording.'})
    with pytest.raises(ValueError, match='timezone-aware'):
        notes.record(**{**args, 'message_id': 'new',
                        'created_at': NOW.replace(tzinfo=None)})
    with pytest.raises(ValueError, match='nonempty'):
        notes.record(**{**args, 'message_id': 'new', 'content': ''})


def test_conversation_requires_explicit_event_and_persisted_user_message(monkeypatch, tmp_path):
    emotions, notes = _stores(tmp_path)
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(personality=object())
    service._session = SimpleNamespace(id='session-1')
    service._emotional_journal = emotions
    service._clarification_journal = notes
    user = SimpleNamespace(id='user:one', role=ConversationRole.USER,
                           content='That test failure was expected.', created_at=NOW)
    assistant = SimpleNamespace(id='assistant:one', role=ConversationRole.ASSISTANT,
                                content='An assistant guess.', created_at=NOW)
    monkeypatch.setattr(EmotionalConversationService, 'messages',
                        lambda self: (user, assistant))
    service.clarify_event(event_id='test-run:one', message_id='user:one')
    service.clarify_event(event_id='test-run:one', message_id='user:one')
    with pytest.raises(ValueError, match='saved user message'):
        service.clarify_event(event_id='test-run:one', message_id='assistant:one')
    with pytest.raises(ValueError, match='saved user message'):
        service.clarify_event(event_id='test-run:one', message_id='other-session')
    with pytest.raises(KeyError):
        service.clarify_event(event_id='not-an-event', message_id='user:one')
    assert len(notes.recent(now=NOW)) == 1
    assert emotions.recent(now=NOW)[0].original_emotions == ('frustration', 'curiosity')


def test_clarification_is_projected_as_data_not_reclassified(monkeypatch, tmp_path):
    emotions, notes = _stores(tmp_path)
    notes.record(event_id='test-run:one', message_id='user:one',
                 content='It was intentional.', created_at=NOW)
    request = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.USER, content='What happened?'),
    ))
    monkeypatch.setattr(ConversationService, '_build_request', lambda self: request)
    monkeypatch.setattr(EmotionalConversationService, 'messages', lambda self: ())
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(personality=object())
    service._emotional_journal = emotions
    service._reflection_journal = None
    service._clarification_journal = notes
    # The stored note is in the past relative to the actual test execution date.
    result = service._build_request()
    assert 'USER CLARIFICATIONS OF RECORDED EVENTS' in result.messages[0].content
    assert 'It was intentional.' in result.messages[0].content
    assert 'original_emotions' in result.messages[0].content
    assert result.messages[-1] is request.messages[-1]
