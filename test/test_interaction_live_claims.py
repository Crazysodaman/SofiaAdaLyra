"""Regression for the real CLI transcript; no LLM or local user state needed."""
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
from sofia.interaction.live_guard import mixed_interaction_control
from sofia.interaction.ledger import control_command
from datetime import datetime, timezone

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'


@pytest.mark.parametrize('content', [
    'So what changes happened? Sofía, I gently pat your left ear, I give your right hand a gentle pat, Sofía, stop interactions, *pats your head*, and Sofía, resume interactions',
    'Sofía, stop interactions; pat your head',
    'Could you explain this? Sofía, resume interactions',
    '"Sofía, stop interactions"',
])
def test_embedded_control_is_not_an_executed_command(content):
    assert mixed_interaction_control(content)
    assert control_command(content) is None


@pytest.mark.parametrize('content', [
    'Sofía, stop interactions', 'Sofía, resume interactions',
    'Tell me about your tail', 'I gently pat your left ear',
])
def test_exact_controls_and_ordinary_dialogue_keep_existing_route(content):
    assert not mixed_interaction_control(content)


def test_mixed_control_is_saved_but_neither_executed_nor_sent_to_model(tmp_path):
    path = tmp_path / 'sofia.db'
    store = ConversationStore(path)
    session = store.create_session()
    service = object.__new__(InteractiveConversationService)
    service._session = session
    service._conversation_store = store
    service._model_lock = RLock()
    service._active_user_requests = 0
    service._last_user_activity = monotonic()
    service._runtime = SimpleNamespace(respond=lambda *_args, **_kwargs: pytest.fail('LLM must not be called'))
    content = ('So what changes happened? Sofía, I gently pat your left ear, '
               'Sofía, stop interactions, *pats your head*, and Sofía, resume interactions')
    try:
        reply = service.respond(content)
        assert 'haven\'t executed' in reply.content
        assert 'Please send' in reply.content
        saved = store.list_messages(session.id)
        assert len(saved) == 2
        assert [item.role for item in saved] == [ConversationRole.USER, ConversationRole.ASSISTANT]
        assert saved[0].content == content
        assert saved[1].content == reply.content
        assert service._session is not None and service._active_user_requests == 0
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT name FROM sqlite_master WHERE name='interaction_evidence'").fetchone() is None
            assert db.execute("SELECT name FROM sqlite_master WHERE name='interaction_session_controls'").fetchone() is None
    finally:
        store.close()


def test_accepted_ear_gesture_preserves_representational_fox_anatomy():
    engine = NaturalInteractionEngine(AvatarStore(AVATAR).load())
    decision = engine.from_text(content='Sofía, I gently pat your left ear',
                                message_id='m1', session_id='s1', occurred_at=NOW)
    assert decision is not None and decision.status == 'accepted'
    prompt = interaction_prompt(decision)
    assert 'CANONICAL REPRESENTATIONAL fox-eared, fox-tailed body' in prompt
    assert 'Do not erase or deny that embodiment' in prompt
    assert 'Do not repeatedly lecture' in prompt
    assert '"region_id": "left-ear"' in prompt
    assert 'NOT sensed touch' in prompt
