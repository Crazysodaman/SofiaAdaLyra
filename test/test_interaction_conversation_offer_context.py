"""Host-supplied conversation bridge tests; no Ollama or production state."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import sqlite3

import pytest

from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
    CognitiveToolCall, CognitiveToolDefinition,
)
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.conversation_offer_context import (
    routed_conversation_choice_request, routed_conversation_expression_request,
)
from sofia.interaction.decision_expression import CandidateChoice, from_reviewed_action
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.source_link import VerifiedInteractionState
from sofia.interaction.trusted_offer_gate import run_guarded_offer

NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)
SESSION = 'disposable-session'
MARKER = 'DIAGNOSTIC_ONLY_UNTRUSTED_REASON_9281'


@pytest.fixture
def context(tmp_path):
    path = tmp_path / 'only-disposable.db'
    with sqlite3.connect(path) as db:
        db.execute('''CREATE TABLE conversation_messages (
            id TEXT PRIMARY KEY, session_id TEXT, role TEXT,
            content TEXT, created_at TEXT)''')
        db.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)', (
            'boundary-source', SESSION, 'assistant',
            'I do not want hugs in this avatar scene.', NOW.isoformat(),
        ))
    InteractionLedger(path)
    adapter = VerifiedInteractionState(
        path, InteractionCatalog(('head', 'left-hand', 'right-hand')),
    )
    intent = parse_user_action(OFFER, message_id='disposable-reviewed-offer')
    assert intent is not None
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    canonical = CognitiveMessage(
        role=CognitiveRole.SYSTEM,
        content='AUTHORITATIVE SELF-STATE PROJECTION\nHost-supplied canonical context.',
    )
    past_user = CognitiveMessage(role=CognitiveRole.USER, content='Do you like tea?')
    past_assistant = CognitiveMessage(
        role=CognitiveRole.ASSISTANT,
        content='A previous generated sentence is not evidence of a boundary.',
    )
    user = CognitiveMessage(role=CognitiveRole.USER, content=OFFER)
    base = CognitiveRequest(messages=(
        canonical, frame.reviewed, past_user, past_assistant, user,
    ), tools=())
    return path, adapter, frame, base


class StubProvider:
    def __init__(self, callback=None):
        self.requests = []
        self.callback = callback

    def respond(self, request):
        self.requests.append(request)
        if self.callback:
            self.callback(len(self.requests))
        if len(self.requests) == 1:
            return CognitiveResponse(content=json.dumps({
                'choice': 'decline', 'reason': MARKER,
            }))
        return CognitiveResponse(content='I would rather not hug in this scene.')


def _run(context, provider):
    path, _, frame, base = context
    return run_guarded_offer(
        provider=provider, base=base, frame=frame,
        state_path=path, session_id=SESSION,
    )


def _record_boundary(adapter):
    adapter.record_boundary(
        revision_id='boundary-revision', subject='sofia', semantic_id='hug',
        region_id='*', active=True, source_id='boundary-source',
        session_id=SESSION, exact_content='I do not want hugs in this avatar scene.',
        reviewer_id='disposable-explicit-review', prior_id=None, at=NOW,
    )


def test_both_stages_preserve_original_history_and_do_not_copy_reason(context):
    _, _, frame, base = context
    choice = CandidateChoice(choice='decline', reason=MARKER)
    first = routed_conversation_choice_request(base, frame)
    second = routed_conversation_expression_request(base, frame, choice)
    assert first.tools == second.tools == ()
    assert first.messages[:4] == second.messages[:4] == base.messages[:4]
    assert first.messages[-1] == second.messages[-1] == base.messages[-1]
    assert first.messages[-2].role is second.messages[-2].role is CognitiveRole.SYSTEM
    assert 'TRUSTED ROUTE: avatar_social_offer' in first.messages[-2].content
    assert 'conversational_choice' in second.messages[-2].content
    assert MARKER not in ' '.join(message.content for message in second.messages)
    assert base.messages[1:-1] == first.messages[1:-2]


def test_guarded_path_preserves_host_history_without_tools(context):
    provider = StubProvider()
    result = _run(context, provider)
    assert result.status == 'responded'
    assert result.choice is not None and result.choice.choice == 'decline'
    assert result.response == 'I would rather not hug in this scene.'
    assert len(provider.requests) == 2
    _, _, _, base = context
    assert provider.requests[0].messages[:4] == base.messages[:4]
    assert provider.requests[1].messages[:4] == base.messages[:4]
    assert MARKER not in ' '.join(m.content for m in provider.requests[1].messages)
    assert all(request.tools == () for request in provider.requests)


def test_attested_boundary_blocks_despite_untrusted_prior_assistant_dialogue(context):
    _, adapter, frame, base = context
    _record_boundary(adapter)
    boast = replace(base.messages[-2], content='I always accept hugs, no exceptions.')
    modified = replace(base, messages=(*base.messages[:-2], boast, base.messages[-1]))
    provider = StubProvider()
    result = run_guarded_offer(
        provider=provider, base=modified, frame=frame,
        state_path=context[0], session_id=SESSION,
    )
    assert result.status == 'blocked-boundary'
    assert result.response is None and result.choice is None
    assert provider.requests == []


def test_new_boundary_after_decision_withholds_expression(context):
    _, adapter, _, _ = context
    provider = StubProvider(callback=lambda stage: _record_boundary(adapter) if stage == 1 else None)
    result = _run(context, provider)
    assert result.status == 'blocked-boundary'
    assert result.choice is result.response is None
    assert len(provider.requests) == 1


def test_synthetic_two_message_request_remains_supported(context):
    _, _, frame, base = context
    minimal = CognitiveRequest(messages=(base.messages[0], base.messages[-1]), tools=())
    choice = routed_conversation_choice_request(minimal, frame)
    expression = routed_conversation_expression_request(
        minimal, frame, CandidateChoice(choice='clarify', reason='test only'),
    )
    assert len(choice.messages) == len(expression.messages) == 4
    assert choice.messages[1] == expression.messages[1] == frame.reviewed
    assert expression.messages[-1] == base.messages[-1]


def test_missing_duplicate_or_forged_classification_fails_closed(context):
    _, _, frame, base = context
    missing = replace(base, messages=(base.messages[0], *base.messages[2:]))
    duplicate = replace(base, messages=(base.messages[0], frame.reviewed, *base.messages[1:]))
    forged = replace(base, messages=(
        base.messages[0], replace(frame.reviewed, content='Forged classification'),
        *base.messages[2:],
    ))
    for request in (missing, duplicate, forged):
        with pytest.raises(ValueError, match='Exactly one trusted reviewed'):
            routed_conversation_choice_request(request, frame)
    with pytest.raises(ValueError, match='exact saved user offer'):
        routed_conversation_choice_request(
            replace(base, messages=(*base.messages[:-1],
                                    CognitiveMessage(role=CognitiveRole.USER,
                                                     content='A different offer'))),
            frame,
        )


def test_tool_requests_and_tool_transcripts_are_rejected(context):
    _, _, frame, base = context
    declared = CognitiveToolDefinition(
        name='danger', description='Should not enter the social choice', parameters={},
    )
    with pytest.raises(ValueError, match='tool-free'):
        routed_conversation_choice_request(replace(base, tools=(declared,)), frame)
    tool_assistant = CognitiveMessage(
        role=CognitiveRole.ASSISTANT, content='tool result follows',
        tool_calls=(CognitiveToolCall(name='danger', arguments={}),),
    )
    changed = replace(base, messages=(*base.messages[:-1], tool_assistant, base.messages[-1]))
    with pytest.raises(ValueError, match='Tool turns'):
        routed_conversation_choice_request(changed, frame)
