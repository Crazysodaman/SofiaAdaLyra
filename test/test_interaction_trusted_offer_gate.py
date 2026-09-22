"""Disposable SQLite and stub-only tests for the opt-in guarded offer path."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import sqlite3

import pytest

from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole, CognitiveToolCall,
)
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.decision_expression import from_reviewed_action
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.source_link import VerifiedInteractionState
from sofia.interaction.trusted_offer_gate import run_guarded_offer

NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)
SESSION = 'session1'


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / 'disposable-state.db'
    with sqlite3.connect(path) as db:
        db.execute('''CREATE TABLE conversation_messages (
            id TEXT PRIMARY KEY, session_id TEXT, role TEXT,
            content TEXT, created_at TEXT)''')
        db.executemany('INSERT INTO conversation_messages VALUES (?,?,?,?,?)', (
            ('no-hugs', SESSION, 'assistant', 'I do not want hugs in this avatar scene.', NOW.isoformat()),
            ('revoked', SESSION, 'assistant', 'I am removing that no-hugs boundary.', NOW.isoformat()),
        ))
    InteractionLedger(path)  # Opt-in: stop schema only in disposable DB.
    adapter = VerifiedInteractionState(
        path, InteractionCatalog(('head', 'left-hand', 'right-hand')),
    )
    intent = parse_user_action(OFFER, message_id='test-reviewed-offer')
    assert intent is not None and intent.modality == 'offered'
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    base = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM,
                         content='AUTHORITATIVE SELF-STATE PROJECTION\nSynthetic only.'),
        CognitiveMessage(role=CognitiveRole.USER, content=OFFER),
    ), tools=())
    return path, adapter, base, frame


def _boundary(adapter, *, active=True, revision='b1', source='no-hugs', prior=None):
    adapter.record_boundary(
        revision_id=revision, subject='sofia', semantic_id='hug',
        region_id='*', active=active, source_id=source,
        session_id=SESSION,
        exact_content=('I do not want hugs in this avatar scene.' if active
                       else 'I am removing that no-hugs boundary.'),
        reviewer_id='test-only-reviewed-source', prior_id=prior, at=NOW,
    )


class StubProvider:
    def __init__(self, callback=None, *, decision='accept', invalid=False, tool=False):
        self.requests = []
        self.callback = callback
        self.decision = decision
        self.invalid = invalid
        self.tool = tool

    def respond(self, request):
        self.requests.append(request)
        step = len(self.requests)
        if self.callback is not None:
            self.callback(step)
        if self.tool:
            return CognitiveResponse(content='', tool_calls=(
                CognitiveToolCall(name='untrusted', arguments={}),
            ))
        if step == 1:
            if self.invalid:
                return CognitiveResponse(content='not strict JSON')
            return CognitiveResponse(content=json.dumps({
                'choice': self.decision,
                'reason': 'This is a present-turn conversational choice only.',
            }))
        return CognitiveResponse(content='I appreciate you asking. We can talk about that.')


def _run(setup, provider):
    path, _, base, frame = setup
    return run_guarded_offer(provider=provider, base=base, frame=frame,
                             state_path=path, session_id=SESSION)


def test_clear_attested_state_allows_routed_choice_and_expression_without_promoting_reason(setup):
    provider = StubProvider(decision='clarify')
    result = _run(setup, provider)
    assert result.status == 'responded' and result.choice.choice == 'clarify'
    assert len(provider.requests) == 2
    assert 'TRUSTED ROUTE: avatar_social_offer' in provider.requests[0].messages[-2].content
    assert 'This is a present-turn conversational choice only.' not in (
        ' '.join(message.content for message in provider.requests[1].messages))
    assert provider.requests[1].tools == provider.requests[0].tools == ()
    assert result.response == 'I appreciate you asking. We can talk about that.'


def test_source_attested_boundary_blocks_before_any_model_call(setup):
    _, adapter, _, _ = setup
    _boundary(adapter)
    provider = StubProvider()
    result = _run(setup, provider)
    assert result.status == 'blocked-boundary'
    assert result.choice is result.response is None
    assert provider.requests == []


def test_unattested_boundary_fails_closed_without_model_call(setup):
    _, adapter, _, _ = setup
    adapter.journal.record_boundary(
        revision_id='unverified', subject='sofia', semantic_id='*',
        region_id='*', active=True, source_id='absent', prior_id=None, at=NOW,
    )
    provider = StubProvider()
    result = _run(setup, provider)
    assert result.status == 'blocked-unverified-boundary'
    assert provider.requests == []


def test_attested_revocation_can_clear_scope_without_implying_consent(setup):
    _, adapter, _, _ = setup
    _boundary(adapter)
    _boundary(adapter, active=False, revision='b2', source='revoked', prior='b1')
    provider = StubProvider(decision='decline')
    result = _run(setup, provider)
    assert result.status == 'responded' and result.choice.choice == 'decline'
    assert len(provider.requests) == 2


def test_stopped_session_blocks_without_inference(setup):
    path, _, _, _ = setup
    InteractionLedger(path).control(
        session_id=SESSION, message_id='stopped-1',
        content='Sofía, stop interactions', occurred_at=NOW,
    )
    provider = StubProvider()
    result = _run(setup, provider)
    assert result.status == 'blocked-stop' and provider.requests == []


@pytest.mark.parametrize('stage,expected_count', ((1, 1), (2, 2)))
def test_inflight_new_boundary_withholds_candidate_reply(setup, stage, expected_count):
    _, adapter, _, _ = setup
    provider = StubProvider(callback=lambda step: _boundary(adapter) if step == stage else None)
    result = _run(setup, provider)
    assert result.status == 'blocked-boundary'
    assert result.choice is result.response is None
    assert len(provider.requests) == expected_count


def test_tampered_attested_source_raises_instead_of_bypassing(setup):
    path, adapter, _, _ = setup
    _boundary(adapter)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE conversation_messages SET content='changed' WHERE id='no-hugs'")
    provider = StubProvider()
    with pytest.raises(ValueError, match='modified'):
        _run(setup, provider)
    assert provider.requests == []


def test_missing_state_and_missing_policy_schema_fail_closed(setup, tmp_path):
    path, _, base, frame = setup
    provider = StubProvider()
    with pytest.raises(FileNotFoundError, match='Existing state database'):
        run_guarded_offer(provider=provider, base=base, frame=frame,
                          state_path=tmp_path / 'absent.db', session_id=SESSION)
    with sqlite3.connect(path) as db:
        db.execute('DROP TABLE interaction_session_controls')
    with pytest.raises(ValueError, match='policy schema missing'):
        _run(setup, provider)
    assert provider.requests == []


def test_invalid_decision_and_unexpected_tool_are_not_defaulted(setup):
    with pytest.raises(ValueError, match='strict JSON'):
        _run(setup, StubProvider(invalid=True))
    with pytest.raises(ValueError, match='unexpected tool call'):
        _run(setup, StubProvider(tool=True))


def test_unreviewed_or_changed_frame_and_session_are_rejected_before_model_call(setup):
    path, _, base, frame = setup
    provider = StubProvider()
    with pytest.raises(ValueError, match='canonical session ID'):
        run_guarded_offer(provider=provider, base=base, frame=frame,
                          state_path=path, session_id='bad session')
    with pytest.raises(ValueError, match='inconsistent with trusted grammar'):
        run_guarded_offer(provider=provider, base=base,
                          frame=replace(frame, kind='gesture'),
                          state_path=path, session_id=SESSION)
    assert provider.requests == []
