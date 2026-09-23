"""Disposable-free regression for the supervised Qwen clarification drift."""

import pytest

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.conversation_offer_context import (
    routed_conversation_expression_request,
)
from sofia.interaction.decision_expression import CandidateChoice, from_reviewed_action
from sofia.interaction.expression_consistency import validate_offer_expression


_REAL_QWEN_CLARIFY_DRIFT = (
    '*tilts head slightly, ears perking up with curiosity*\n'
    "I appreciate the gesture, but I'd prefer to keep things on a more "
    'intellectual and respectful level. How can I assist you instead?'
)


@pytest.mark.parametrize('reply', (
    _REAL_QWEN_CLARIFY_DRIFT,
    'I appreciate the offer. How can I help you?',
    'I would rather not hug right now. What else would you like to discuss?',
    'I appreciate your gesture.',
))
def test_clarify_does_not_silently_decline_or_redirect(reply):
    with pytest.raises(ValueError, match='Expression contradicts or fails to clarify'):
        validate_offer_expression(CandidateChoice('clarify', 'diagnostic only'), reply)


def test_question_about_offer_can_clarify_without_forcing_yes():
    validate_offer_expression(
        CandidateChoice('clarify', 'diagnostic only'),
        'Do you mean a hug in our avatar scene?',
    )


def test_conversation_clarify_prompt_preserves_history_and_never_promotes_reason():
    intent = parse_user_action(OFFER, message_id='reviewed-offer-1')
    assert intent is not None
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    canonical = CognitiveMessage(
        role=CognitiveRole.SYSTEM,
        content='AUTHORITATIVE SELF-STATE PROJECTION\nCanonical test.',
    )
    history = CognitiveMessage(role=CognitiveRole.ASSISTANT, content='Prior dialogue.')
    user = CognitiveMessage(role=CognitiveRole.USER, content=OFFER)
    base = CognitiveRequest(messages=(canonical, frame.reviewed, history, user), tools=())
    result = routed_conversation_expression_request(
        base, frame, CandidateChoice('clarify', 'untrusted private diagnostic'),
    )
    assert result.tools == ()
    assert result.messages[0] == canonical
    assert history in result.messages
    assert result.messages[-1] == user
    assert 'ask a brief, natural question about' in result.messages[-2].content
    assert 'untrusted private diagnostic' not in ' '.join(m.content for m in result.messages)
