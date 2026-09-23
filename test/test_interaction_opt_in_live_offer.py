"""Opt-in service integration: stub cognitive engine and disposable SQLite ONLY."""
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from types import SimpleNamespace
import json
import sqlite3

import pytest

from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.cognition.provider import LLMProvider
from sofia.conversation.store import ConversationStore
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.decision_expression import from_reviewed_action
from sofia.interaction.expanded_service import ExpandedConversationService
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.opt_in_service import OptInInteractionConversationService
from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.reviewed_hug_question import CLARIFICATION
from sofia.interaction.source_link import VerifiedInteractionState

NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)


class StubLLM(LLMProvider):
    def __init__(self, callback=None):
        self.calls = []
        self.callback = callback

    def respond(self, request):
        self.calls.append(request)
        if self.callback:
            self.callback(len(self.calls))
        if len(self.calls) == 1:
            return CognitiveResponse(content=json.dumps({
                'choice': 'clarify', 'reason': 'Diagnostic explanation NOT evidence.',
            }))
        return CognitiveResponse(content='Would you like a hug in our avatar scene?')


class StubAssembler:
    def assemble(self, context, tools=()):
        assert tools == ()
        return CognitiveRequest(messages=(
            CognitiveMessage(role=CognitiveRole.SYSTEM,
                             content='AUTHORITATIVE SELF-STATE PROJECTION\nTest canonical context.'),
            *context.request.messages,
        ), tools=())


@pytest.fixture
def live_candidate(tmp_path):
    path = tmp_path / 'disposable.db'
    store = ConversationStore(path)
    session = store.create_session()
    ledger = InteractionLedger(path)
    adapter = VerifiedInteractionState(path, InteractionCatalog(('head', 'left-hand')))
    provider = StubLLM()
    engine = LLMCognitiveEngine(configuration=SimpleNamespace(), provider=provider)
    runtime = SimpleNamespace(
        configuration=SimpleNamespace(
            provider=SimpleNamespace(provider='ollama', model='qwen3:14b'),
            state_path=path,
        ),
        cognitive_system=SimpleNamespace(engine=engine, context_assembler=StubAssembler()),
        memory_system=SimpleNamespace(recall_relevant=lambda _text: ()),
        identity=None, personality=None, constitution=None, embodiment=None,
        core_state=None, operational_state=None, runtime_continuity=None,
        workspace_changes=None, operational_self_model=None,
    )
    service = object.__new__(OptInInteractionConversationService)
    service._runtime = runtime
    service._conversation_store = store
    service._session = session
    service._model_lock = RLock()
    service._active_user_requests = 0
    service._last_user_activity = monotonic()

    def build_request():
        turns = store.list_messages(session.id)
        user = turns[-1]
        intent = parse_user_action(user.content, message_id=user.id)
        frame = from_reviewed_action(user_text=user.content, intent=intent)
        return CognitiveRequest(messages=(
            frame.reviewed,
            *tuple(CognitiveMessage(role=(CognitiveRole.USER if m.role.value == 'user'
                                          else CognitiveRole.ASSISTANT), content=m.content)
                   for m in turns),
        ), tools=())

    service._build_request = build_request
    return service, path, adapter, provider, ledger


def _turns(path):
    with sqlite3.connect(path) as db:
        return db.execute('SELECT role, content FROM conversation_messages '
                          'ORDER BY created_at, id').fetchall()


def _record_boundary(service, adapter):
    path = service._runtime.configuration.state_path
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                   ('source-b1', service._session.id, 'assistant',
                    'I do not want hugs in this avatar scene.',
                    '2026-09-21T00:00:00+00:00'))
    adapter.record_boundary(
        revision_id='b1', subject='sofia', semantic_id='hug', region_id='*',
        active=True, source_id='source-b1', session_id=service._session.id,
        exact_content='I do not want hugs in this avatar scene.',
        reviewer_id='test-reviewer', prior_id=None, at=NOW,
    )


def test_default_off_uses_unchanged_parent_route(monkeypatch, live_candidate):
    service, path, _, provider, _ = live_candidate
    monkeypatch.delenv('SOFIA_INTERACT_STAGED_OFFERS', raising=False)
    monkeypatch.setattr(ExpandedConversationService, 'respond',
                        lambda self, content: 'existing:' + content)
    assert service.respond(OFFER) == 'existing:' + OFFER
    assert service.respond('Could I hug you?') == 'existing:Could I hug you?'
    assert not _turns(path) and provider.calls == []


def test_invalid_optin_setting_rejects_without_persistence(monkeypatch, live_candidate):
    service, path, _, provider, _ = live_candidate
    monkeypatch.setenv('SOFIA_INTERACT_STAGED_OFFERS', 'surprise')
    with pytest.raises(ValueError, match='must be 1 or 0'):
        service.respond(OFFER)
    assert not _turns(path) and provider.calls == []


def test_exact_opted_offer_saves_one_user_one_assistant(monkeypatch, live_candidate):
    service, path, _, provider, _ = live_candidate
    monkeypatch.setenv('SOFIA_INTERACT_STAGED_OFFERS', '1')
    result = service.respond(OFFER)
    assert result.content == 'Would you like a hug in our avatar scene?'
    assert _turns(path) == [
        ('user', OFFER), ('assistant', result.content),
    ]
    assert len(provider.calls) == 2
    assert all(request.tools == () for request in provider.calls)
    assert 'Diagnostic explanation NOT evidence.' not in ' '.join(
        m.content for m in provider.calls[1].messages)
    assert service._active_user_requests == 0
    assert service._session.id is not None


def test_active_attested_boundary_blocks_before_model(monkeypatch, live_candidate):
    service, path, adapter, provider, _ = live_candidate
    _record_boundary(service, adapter)
    monkeypatch.setenv('SOFIA_INTERACT_STAGED_OFFERS', '1')
    service._build_request = lambda: (_ for _ in ()).throw(
        AssertionError('Blocked offer entered ordinary context assembly.'))
    result = service.respond(OFFER)
    assert 'recorded interaction boundary' in result.content
    assert provider.calls == []
    assert ('user', OFFER) in _turns(path)
    assert ('assistant', result.content) in _turns(path)


def test_boundary_activated_during_expression_is_enforced_at_commit(monkeypatch, live_candidate):
    service, path, adapter, provider, _ = live_candidate
    provider.callback = lambda step: _record_boundary(service, adapter) if step == 2 else None
    monkeypatch.setenv('SOFIA_INTERACT_STAGED_OFFERS', '1')
    result = service.respond(OFFER)
    assert len(provider.calls) == 2
    assert 'recorded interaction boundary' in result.content
    assert 'Would you like a hug' not in str(_turns(path))


def test_stopped_session_blocks_even_with_optin(monkeypatch, live_candidate):
    service, path, _, provider, ledger = live_candidate
    ledger.control(session_id=service._session.id, message_id='stop1',
                   content='Sofía, stop interactions', occurred_at=NOW)
    monkeypatch.setenv('SOFIA_INTERACT_STAGED_OFFERS', '1')
    result = service.respond(OFFER)
    assert 'paused' in result.content and provider.calls == []
    assert ('assistant', result.content) in _turns(path)


def test_unreviewed_phrase_uses_parent_not_staged_route(monkeypatch, live_candidate):
    service, path, _, provider, _ = live_candidate
    monkeypatch.setenv('SOFIA_INTERACT_STAGED_OFFERS', '1')
    monkeypatch.setattr(ExpandedConversationService, 'respond',
                        lambda self, content: 'existing:' + content)
    for text in (
        'Could I hug you and check your sensors?',
        'Could I physically hug you?',
        'If I could hug you, what would happen?',
        'Can you physically feel my hand through a real sensor?',
    ):
        assert service.respond(text) == 'existing:' + text
    assert provider.calls == [] and not _turns(path)


@pytest.mark.parametrize('question', (
    'Could I hug you?', 'Can I hug you?', 'May I give you a hug?',
))
def test_reviewed_question_only_clarifies_and_saves_both_turns(
    monkeypatch, live_candidate, question,
):
    service, path, _, provider, _ = live_candidate
    monkeypatch.setenv('SOFIA_INTERACT_STAGED_OFFERS', '1')
    service._build_request = lambda: (_ for _ in ()).throw(
        AssertionError('Ambiguous question reached ordinary model assembly.'))
    result = service.respond(question)
    assert result.content == CLARIFICATION
    assert _turns(path) == [('user', question), ('assistant', CLARIFICATION)]
    assert provider.calls == [] and service._active_user_requests == 0
    assert service._session.id is not None


def test_attested_boundary_blocks_reviewed_question_without_model(
    monkeypatch, live_candidate,
):
    service, path, adapter, provider, _ = live_candidate
    _record_boundary(service, adapter)
    monkeypatch.setenv('SOFIA_INTERACT_STAGED_OFFERS', '1')
    result = service.respond('Could I hug you?')
    assert 'recorded interaction boundary' in result.content
    assert CLARIFICATION not in str(_turns(path))
    assert ('user', 'Could I hug you?') in _turns(path)
    assert provider.calls == []


def test_stop_blocks_reviewed_question_without_model(monkeypatch, live_candidate):
    service, path, _, provider, ledger = live_candidate
    ledger.control(session_id=service._session.id, message_id='stop1',
                   content='Sofía, stop interactions', occurred_at=NOW)
    monkeypatch.setenv('SOFIA_INTERACT_STAGED_OFFERS', '1')
    result = service.respond('Can I hug you?')
    assert 'paused' in result.content and provider.calls == []
    assert ('assistant', result.content) in _turns(path)


def test_real_sample_accept_then_refuse_is_not_saved(monkeypatch, live_candidate):
    service, path, _, provider, _ = live_candidate
    monkeypatch.setenv('SOFIA_INTERACT_STAGED_OFFERS', '1')

    def contradictory_respond(request):
        provider.calls.append(request)
        if len(provider.calls) == 1:
            return CognitiveResponse(content=json.dumps({
                'choice': 'accept', 'reason': 'I appreciate your offer.',
            }))
        return CognitiveResponse(content=(
            'I appreciate the gesture, but I’m not sure I’m ready for that right now. '
            'Let’s keep things light and friendly for now.'
        ))

    monkeypatch.setattr(provider, 'respond', contradictory_respond)
    with pytest.raises(ValueError, match='Expression contradicts'):
        service.respond(OFFER)
    assert len(provider.calls) == 2
    assert _turns(path) == [('user', OFFER)]
    assert service._active_user_requests == 0
