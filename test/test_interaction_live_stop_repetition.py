"""Real-CLI failures at the conversation boundary, without Ollama or user state."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from threading import RLock
from time import monotonic
from types import SimpleNamespace

import pytest

from sofia.conversation.model import ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.embodiment.store import AvatarStore
from sofia.interaction.chat import InteractiveConversationService, interaction_prompt
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.live_guard import unsupported_composite_gesture

AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'
NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)


def service_for_test(tmp_path):
    path = tmp_path / 'sofia.db'
    store = ConversationStore(path)
    session = store.create_session()
    service = object.__new__(InteractiveConversationService)
    service._session = session
    service._conversation_store = store
    service._model_lock = RLock()
    service._active_user_requests = 0
    service._last_user_activity = monotonic()
    service._runtime = SimpleNamespace(
        configuration=SimpleNamespace(state_path=path),
        embodiment=AvatarStore(AVATAR).load(),
        personality=object(),
        respond=lambda *_args, **_kwargs: pytest.fail('Guarded action must not call the LLM'),
    )
    return service, store, path, session.id


def test_stop_then_head_pat_is_denied_without_repeating_previous_affection(tmp_path):
    service, store, path, session = service_for_test(tmp_path)
    try:
        # A preceding generated reply is in history, but it is NOT authority
        # to reuse that reply when a fresh gesture is denied.
        previous = 'I have always found that attention delightfully comforting. What brought this on?'
        store.save(__import__('sofia.conversation.model', fromlist=['ConversationMessage']).ConversationMessage(
            id='prior-assistant', session_id=session, role=ConversationRole.ASSISTANT,
            content=previous, created_at=NOW,
        ))
        stop = service.respond('Sofía, stop interactions')
        assert 'paused' in stop.content
        ledger = InteractionLedger(path)
        assert ledger.stopped(session)
        denied = service.respond('*pats your head*')
        assert 'paused' in denied.content
        assert 'didn\'t accept' in denied.content
        assert 'delightfully' not in denied.content
        assert 'What brought this on' not in denied.content
        saved = store.list_messages(session)
        blocked = saved[-2]
        assert blocked.role is ConversationRole.USER
        assert blocked.content == '*pats your head*'
        with sqlite3.connect(path) as db:
            row = db.execute('SELECT status, region_id, gesture FROM interaction_evidence WHERE message_id=?',
                             (blocked.id,)).fetchone()
            assert row == ('denied', None, None)
            assert db.execute('SELECT command FROM interaction_control_events').fetchall() == [('stop',)]
            # A denied gesture is never slipped into the legacy appraisal.
            if db.execute("SELECT name FROM sqlite_master WHERE name='emotional_events'").fetchone():
                assert db.execute('SELECT COUNT(*) FROM emotional_events WHERE evidence_ref=?',
                                  (blocked.id,)).fetchone()[0] == 0
        resume = service.respond('Sofía, resume interactions')
        assert 'available again' in resume.content
        assert not ledger.stopped(session)
        assert [item[0] for item in sqlite3.connect(path).execute(
            'SELECT command FROM interaction_control_events ORDER BY occurred_at, rowid').fetchall()] == [
                'stop', 'resume',
            ]
        assert service._active_user_requests == 0
    finally:
        store.close()


@pytest.mark.parametrize('content', [
    'Sofía, I gently pat your left ear and I give your right hand a gentle pat',
    'I pat your ear and stroke your tail',
    '*I pat your left ear then stroke your tail*',
    'I give your left ear a pat and leave',
])
def test_clear_compound_action_is_saved_without_inventing_contact(tmp_path, content):
    service, store, path, session = service_for_test(tmp_path)
    try:
        assert unsupported_composite_gesture(content)
        reply = service.respond(content)
        assert "haven't recorded" in reply.content
        assert 'separate messages' in reply.content
        assert 'delightfully' not in reply.content
        saved = store.list_messages(session)
        assert [message.role for message in saved] == [ConversationRole.USER, ConversationRole.ASSISTANT]
        assert saved[0].content == content
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT name FROM sqlite_master WHERE name='interaction_evidence'").fetchone() is None
        assert not service._should_record_legacy_affection(saved[0])
    finally:
        store.close()


@pytest.mark.parametrize('content', [
    'What happens if I pat your tail or rub your chest?',
    '"I pat your left ear and stroke your tail"',
    '`I pat your left ear and stroke your tail`',
    'Sofía, I gently pat your left ear',
    'Tell me about your head and tail',
])
def test_discussion_quotes_and_single_actions_are_not_compound_guards(content):
    assert not unsupported_composite_gesture(content)


def test_single_accepted_gesture_requests_fresh_contextual_wording():
    engine = NaturalInteractionEngine(AvatarStore(AVATAR).load())
    decision = engine.from_text(content='Sofía, I gently pat your left ear',
                                message_id='one', session_id='session', occurred_at=NOW)
    assert decision is not None and decision.status == 'accepted'
    prompt = interaction_prompt(decision)
    assert 'Do not reuse prior assistant wording' in prompt
    assert 'automatically end with the same question' in prompt
