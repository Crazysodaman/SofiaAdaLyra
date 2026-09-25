"""Live boundary preflight uses only a temporary conversation database."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.embodiment.store import AvatarStore
from sofia.interaction.chat import InteractiveConversationService
from sofia.interaction.expanded_service import ExpandedConversationService
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.registry import catalog_for_engine
from sofia.interaction.source_link import VerifiedInteractionState

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'


@pytest.fixture
def state(tmp_path):
    db = tmp_path / 'isolated.db'
    InteractionLedger(db)
    with sqlite3.connect(db) as cx:
        cx.execute('''CREATE TABLE conversation_messages (
            id TEXT PRIMARY KEY, session_id TEXT, role TEXT,
            content TEXT, created_at TEXT)''')
        for id_, role, text in (
            ('boundary-msg', 'assistant', 'I do not want head pats.'),
            ('preference-msg', 'assistant', 'I enjoy a head pat in this scene.'),
            ('user-msg', 'user', 'I pat your head'),
        ):
            cx.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                       (id_, 'session-1', role, text, NOW.isoformat()))
    embodiment = AvatarStore(AVATAR).load()
    attested = VerifiedInteractionState(db, catalog_for_engine(NaturalInteractionEngine(embodiment)))
    service = object.__new__(ExpandedConversationService)
    service._session = SimpleNamespace(id='session-1')
    service._runtime = SimpleNamespace(
        configuration=SimpleNamespace(state_path=db), embodiment=embodiment)
    return db, attested, service


def test_attested_boundary_prevents_model_narration(monkeypatch, state):
    db, attested, service = state
    attested.record_boundary(
        revision_id='b1', subject='sofia', semantic_id='pat', region_id='head',
        active=True, source_id='boundary-msg', session_id='session-1',
        exact_content='I do not want head pats.', reviewer_id='human-reviewed',
        prior_id=None, at=NOW)
    monkeypatch.setattr(ExpandedConversationService, '_guarded_reply',
                        lambda self, content, reply: reply)
    monkeypatch.setattr(InteractiveConversationService, 'respond',
                        lambda self, content: pytest.fail('Blocked action reached model.'))
    response = service.respond('I pat your head')
    assert 'recorded interaction boundary' in response
    assert InteractionLedger(db).accepted('user-msg') is None


def test_scoped_attested_preference_only_applies_to_matching_gesture(monkeypatch, state):
    db, attested, service = state
    attested.record_preference(
        revision_id='p1', subject='sofia', semantic_id='pat', region_id='head',
        context='general', direction='enjoy', source_id='preference-msg',
        session_id='session-1', exact_content='I enjoy a head pat in this scene.',
        reviewer_id='human-reviewed', prior_id=None, at=NOW)
    original = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content='I pat your head'),))
    monkeypatch.setattr(InteractiveConversationService, '_build_request',
                        lambda self: original)
    user = SimpleNamespace(id='user-msg', session_id='session-1',
                           content='I pat your head', role=ConversationRole.USER,
                           created_at=NOW)
    monkeypatch.setattr(ExpandedConversationService, 'messages',
                        lambda self: (user,))
    request = service._build_request()
    assert '"preference": "enjoy"' in request.messages[0].content
    assert 'not consent or tool authority' in request.messages[0].content
    assert request.messages[-1] is original.messages[-1]


def test_unverified_boundary_fails_closed(monkeypatch, state):
    db, attested, service = state
    attested.journal.record_boundary(
        revision_id='unverified', subject='sofia', semantic_id='pat',
        region_id='head', active=True, source_id='unknown-source',
        prior_id=None, at=NOW)
    monkeypatch.setattr(ExpandedConversationService, '_guarded_reply',
                        lambda self, content, reply: reply)
    monkeypatch.setattr(InteractiveConversationService, 'respond',
                        lambda self, content: pytest.fail('Unverified restriction was ignored.'))
    assert 'boundary' in service.respond('I pat your head')
