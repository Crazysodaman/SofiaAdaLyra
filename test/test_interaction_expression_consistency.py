"""Targeted regression for the real-model accept-then-refuse failure."""
from datetime import datetime, timezone
import json
import sqlite3

import pytest

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.atomic_offer_release import commit_guarded_offer_reply
from sofia.interaction.decision_expression import CandidateChoice, from_reviewed_action
from sofia.interaction.expression_consistency import validate_offer_expression
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.source_link import VerifiedInteractionState
from sofia.interaction.trusted_offer_gate import GuardedOfferResult, run_guarded_offer

CONTRADICTION = (
    '*ears twitch slightly, tail swishing in curiosity*\n'
    'I appreciate the gesture, but I’m not sure I’m ready for that right now. '
    'Let’s keep things light and friendly for now—maybe a pat on the head?'
)


@pytest.mark.parametrize('choice,reply', [
    ('accept', CONTRADICTION),
    ('accept', 'Thank you for asking. I am not comfortable with hugs right now.'),
    ('accept', 'I appreciate the gesture.'),  # appreciation is not acceptance
    ('decline', 'Yes, you can hug me.'),
    ('clarify', 'Go ahead and hug me.'),
    ('boundary', 'I accept your hug.'),
])
def test_explicit_choice_expression_conflict_is_rejected(choice, reply):
    with pytest.raises(ValueError, match='Expression contradicts'):
        validate_offer_expression(CandidateChoice(choice, 'diagnostic only'), reply)


@pytest.mark.parametrize('choice,reply', [
    ('accept', 'Yes, I would welcome a hug in our avatar scene.'),
    ('decline', 'No, I would rather keep some space.'),
    ('clarify', 'Are you offering a hug in our avatar scene?'),
    ('boundary', 'Please give me some space right now.'),
])
def test_in_scope_noncontradictory_examples_are_not_forced_to_accept(choice, reply):
    validate_offer_expression(CandidateChoice(choice, 'diagnostic only'), reply)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / 'only-disposable.db'
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE conversation_sessions (id TEXT PRIMARY KEY, '
                   'created_at TEXT NOT NULL, updated_at TEXT NOT NULL)')
        db.execute('CREATE TABLE conversation_messages (id TEXT PRIMARY KEY, '
                   'session_id TEXT NOT NULL, role TEXT NOT NULL, '
                   'content TEXT NOT NULL, created_at TEXT NOT NULL)')
        db.execute('INSERT INTO conversation_sessions VALUES (?,?,?)', ('session1', now, now))
        db.execute('INSERT INTO conversation_messages VALUES (?,?,?,?,?)',
                   ('offer1', 'session1', 'user', OFFER, now))
    InteractionLedger(path)
    VerifiedInteractionState(path, InteractionCatalog(('head', 'left-hand')))
    frame = from_reviewed_action(
        user_text=OFFER, intent=parse_user_action(OFFER, message_id='offer1'),
    )
    base = CognitiveRequest(messages=(
        CognitiveMessage(CognitiveRole.SYSTEM, 'AUTHORITATIVE SELF-STATE PROJECTION\nTest only.'),
        CognitiveMessage(CognitiveRole.USER, OFFER),
    ), tools=())
    return path, frame, base


class ContradictingProvider:
    def __init__(self):
        self.calls = 0

    def respond(self, request):
        self.calls += 1
        if self.calls == 1:
            return CognitiveResponse(content=json.dumps({
                'choice': 'accept', 'reason': 'I appreciate the offer.',
            }))
        return CognitiveResponse(content=CONTRADICTION)


def _assistant_replies(path):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT content FROM conversation_messages WHERE role='assistant'").fetchall()


def test_guarded_inference_vetoes_real_sample_before_reply_persistence(state):
    path, frame, base = state
    provider = ContradictingProvider()
    with pytest.raises(ValueError, match='Expression contradicts'):
        run_guarded_offer(provider=provider, base=base, frame=frame,
                          state_path=path, session_id='session1')
    assert provider.calls == 2
    assert _assistant_replies(path) == []


def test_atomic_commit_rejects_injected_contradictory_pair(state):
    path, _, _ = state
    with pytest.raises(ValueError, match='Expression contradicts'):
        commit_guarded_offer_reply(
            state_path=path, session_id='session1', user_message_id='offer1',
            user_content=OFFER,
            result=GuardedOfferResult(
                status='responded',
                choice=CandidateChoice('accept', 'diagnostic only'),
                response=CONTRADICTION,
            ),
        )
    assert _assistant_replies(path) == []
