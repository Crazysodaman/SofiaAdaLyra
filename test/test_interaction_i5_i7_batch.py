"""Focused headless I5-I7 acceptance; no network, model, avatar or live state."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.embodiment.store import AvatarStore
from sofia.interaction.chat import InteractiveConversationService
from sofia.interaction.core import InteractionEngine
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.ledger import InteractionLedger, control_command

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'


@pytest.fixture
def engine():
    return NaturalInteractionEngine(AvatarStore(AVATAR).load())


@pytest.fixture
def ledger(tmp_path):
    return InteractionLedger(tmp_path / 'existing-state.db')


def decision(ledger, engine, text, message='m1', session='s1'):
    return ledger.process_text(engine=engine, content=text, message_id=message,
                               session_id=session, occurred_at=NOW)


@pytest.mark.parametrize('content,region,verb', [
    ('Sofía, I gently pat your left ear', 'left-ear', 'pat'),
    ('I give your right hand a gentle pat', 'right-hand', 'pat'),
    ('*I stroke the tip of your right ear*', 'right-ear-tip', 'stroke'),
    ('I touch your fox tail', 'tail', 'touch'),
    ('I tap the base of your left ear', 'left-ear-base', 'tap'),
    ('I pat the tip of your tail', 'tail-tip', 'pat'),
])
def test_natural_aliases_share_pointer_meaning(engine, content, region, verb):
    text = engine.from_text(content=content, message_id='m1', session_id='s1', occurred_at=NOW)
    pointer = engine.from_lab_pointer(fixture_id='lab-1', session_id='s1',
                                      region_id=region, gesture=verb, occurred_at=NOW)
    assert text is not None and text.status == pointer.status == 'accepted'
    assert text.event.semantics == pointer.event.semantics
    assert text.emotion_options == pointer.emotion_options


@pytest.mark.parametrize('content', [
    'Sofía, pat your left ear',  # imperative to Sofía is NOT user contact
    'Sofía, I would pat your left ear', 'I could give your hand a pat',
    'I pat your ear and stroke your tail', 'I give your left ear a pat and leave',
    'She pats your left ear', 'Could I pat your left ear?',
    'I patted your head yesterday', '"I give your ear a pat"',
    '`I gently pat your ear`', 'I give your ear a pat\nI touch your tail',
])
def test_ambiguous_discussion_and_multiple_actions_abstain(engine, content):
    assert engine.from_text(content=content, message_id='m1', session_id='s1',
                            occurred_at=NOW) is None


def test_unknown_and_private_aliases_never_become_accepted(engine):
    ambiguous = engine.from_text(content='I pat your ear', message_id='m1',
                                 session_id='s1', occurred_at=NOW)
    assert ambiguous is not None and ambiguous.status == 'clarify'
    restricted = engine.from_text(content='I touch your left breast', message_id='m2',
                                  session_id='s1', occurred_at=NOW)
    assert restricted is not None and restricted.status == 'denied'


def test_source_linked_ledger_persists_once_and_replay_does_not_react(ledger, engine):
    first, fresh = decision(ledger, engine, '*pats your left ear*')
    assert first.status == 'accepted' and fresh
    assert ledger.accepted('m1') == ('s1', 'left-ear', 'pat')
    replay, fresh = decision(InteractionLedger(ledger.path), engine, '*pats your left ear*')
    assert replay.status == 'acknowledged' and not fresh
    assert not replay.emotion_options and not replay.text_cues
    with pytest.raises(ValueError, match='different evidence'):
        decision(ledger, engine, '*pats your right ear*')
    assert ledger.accepted('m1') == ('s1', 'left-ear', 'pat')


def test_private_denial_is_audited_without_region_and_cannot_be_retried(ledger, engine):
    denied, fresh = decision(ledger, engine, '*touches your groin*')
    assert denied.status == 'denied' and fresh
    assert ledger.accepted('m1') is None
    with ledger._connect() as db:
        saved = db.execute('SELECT status, region_id, gesture FROM interaction_evidence').fetchone()
    assert saved == ('denied', None, None)
    replay, fresh = decision(ledger, engine, '*touches your groin*')
    assert replay.status == 'acknowledged' and not fresh
    assert not replay.text_cues


def test_stop_persists_across_restart_and_resume_is_new_saved_user_turn(ledger, engine):
    assert control_command('Sofía, stop interactions') == 'stop'
    stopped = ledger.control(session_id='s1', message_id='stop-1',
                             content='Sofía, stop interactions', occurred_at=NOW)
    assert stopped.status == 'stopped'
    resumed_ledger = InteractionLedger(ledger.path)
    assert resumed_ledger.stopped('s1')
    blocked, fresh = decision(resumed_ledger, engine, '*pats your head*', message='blocked')
    assert blocked.status == 'denied' and fresh
    assert resumed_ledger.accepted('blocked') is None
    resume = resumed_ledger.control(session_id='s1', message_id='resume-1',
                                    content='Sofía, resume interactions', occurred_at=NOW)
    assert resume.status == 'resumed' and not resumed_ledger.stopped('s1')
    old, fresh = decision(resumed_ledger, engine, '*pats your head*', message='blocked')
    assert old.status == 'acknowledged' and not fresh
    new, fresh = decision(resumed_ledger, engine, '*pats your head*', message='new')
    assert new.status == 'accepted' and fresh
    assert resumed_ledger.stopped('unrelated-session') is False
    assert resumed_ledger.control(session_id='s1', message_id='stop-1',
                                  content='Sofía, stop interactions', occurred_at=NOW).status == 'replayed'
    assert not resumed_ledger.stopped('s1')


def test_controls_reject_forged_or_colliding_evidence(ledger, engine):
    for phrase in ('Stop interactions', 'Sofía, could you stop interactions?',
                   '"Sofía, stop interactions"', '`Sofía, stop interactions`'):
        assert control_command(phrase) is None
    ledger.control(session_id='s1', message_id='m1',
                   content='Sofía, stop interactions', occurred_at=NOW)
    with pytest.raises(ValueError, match='different evidence'):
        ledger.control(session_id='s1', message_id='m1',
                       content='Sofía, resume interactions', occurred_at=NOW)
    with pytest.raises(ValueError, match='session'):
        ledger.control(session_id='s2', message_id='m1',
                       content='Sofía, stop interactions', occurred_at=NOW)
    with pytest.raises(ValueError, match='session control'):
        decision(ledger, engine, '*pats your head*', message='m1')
    assert ledger.stopped('s1')


def _chat(monkeypatch, tmp_path, content, message_id='saved-1'):
    original = CognitiveRequest(messages=(CognitiveMessage(role=CognitiveRole.USER, content=content),))
    monkeypatch.setattr(EmotionalConversationService, '_build_request', lambda self: original)
    user = SimpleNamespace(id=message_id, session_id='session-1', content=content,
                           role=ConversationRole.USER, created_at=NOW)
    monkeypatch.setattr(InteractiveConversationService, 'messages', lambda self: (user,))
    service = object.__new__(InteractiveConversationService)
    service._runtime = SimpleNamespace(personality=object(),
        embodiment=AvatarStore(AVATAR).load(),
        configuration=SimpleNamespace(state_path=tmp_path / 'sofia.db'))
    return service, original, user


def test_chat_stop_and_replay_cannot_generate_fresh_gestures(monkeypatch, tmp_path):
    service, original, user = _chat(monkeypatch, tmp_path, 'Sofía, stop interactions')
    assert '"stopped": true' in service._build_request().messages[0].content
    assert service._build_request().messages[-1] is original.messages[-1]
    user.id, user.content = 'saved-2', 'I gently pat your left ear'
    blocked = service._build_request()
    assert '"policy_status": "denied"' in blocked.messages[0].content
    assert '"region_id": null' in blocked.messages[0].content
    assert service._build_request().messages[0].content.count('"policy_status": "acknowledged"') == 1
    user.id, user.content = 'saved-3', 'Sofía, resume interactions'
    assert '"stopped": false' in service._build_request().messages[0].content
    user.id, user.content = 'saved-4', 'I gently pat your left ear'
    assert '"policy_status": "accepted"' in service._build_request().messages[0].content
    assert InteractionLedger(tmp_path / 'sofia.db').accepted('saved-4') == ('session-1', 'left-ear', 'pat')


def test_regular_chat_does_not_instantiate_world_or_ledger(monkeypatch, tmp_path):
    service, original, _ = _chat(monkeypatch, tmp_path, 'Tell me about your tail')
    assert service._build_request() is original
    assert not (tmp_path / 'sofia.db').exists()
    assert not (tmp_path / 'sofia-lab.db').exists()
