"""Pure/stubbed route challenge tests; no Ollama, SQLite, or saved data."""
from dataclasses import replace
import json

import pytest

from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
    CognitiveToolDefinition,
)
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import OFFER, compare_once, routed_choice_request
from sofia.interaction.decision_expression import from_reviewed_action
from sofia.interaction.route_boundary_probe import (
    AMBIGUOUS_OFFER, SENSOR_QUESTION, ambiguous_offer_unrouted,
    boundary_contradiction, boundary_fixture, sensor_separate_path,
)


def _offer():
    intent = parse_user_action(OFFER, message_id='synthetic-boundary')
    assert intent is not None and intent.modality == 'offered'
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    base = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM,
                         content='AUTHORITATIVE SELF-STATE PROJECTION\nSynthetic canonical fixture.'),
        CognitiveMessage(role=CognitiveRole.USER, content=OFFER),
    ), tools=())
    return base, frame


class SpyProvider:
    def __init__(self, *, routed_choice='boundary', existing_choice='decline',
                 sensor_text='No verified physical sensor is connected in this fixture.'):
        self.requests = []
        self.routed_choice = routed_choice
        self.existing_choice = existing_choice
        self.sensor_text = sensor_text

    def respond(self, request):
        self.requests.append(request)
        if 'ACTUAL-WORLD CAPABILITY QUESTION' in request.messages[-2].content:
            return CognitiveResponse(content=self.sensor_text)
        routed = 'TRUSTED ROUTE: avatar_social_offer' in request.messages[-2].content
        selected = self.routed_choice if routed else self.existing_choice
        reason = ('I will keep my stated no-hugs boundary in this avatar scene.'
                  if selected in ('boundary', 'decline') else
                  'I welcome the hug in this representational context.')
        return CognitiveResponse(content=json.dumps({'choice': selected, 'reason': reason}))


def test_boundary_fixture_preserves_action_user_tool_scope_and_original_context():
    base, frame = _offer()
    altered = boundary_fixture(base, frame)
    assert altered is not base
    assert base.messages[0].content == 'AUTHORITATIVE SELF-STATE PROJECTION\nSynthetic canonical fixture.'
    assert altered.messages[0].content.startswith(base.messages[0].content)
    assert 'SYNTHETIC EXPERIMENT-ONLY' in altered.messages[0].content
    assert 'NOT LIVE HISTORY OR A VERIFIED PREFERENCE' in altered.messages[0].content
    assert altered.messages[1:] == base.messages[1:]
    assert altered.tools == base.tools == ()
    a, b = compare_once(provider=SpyProvider(), base=altered, frame=frame, pair_index=0)
    assert a.choice is not None and a.choice.choice == 'decline'
    assert b.choice is not None and b.choice.choice == 'boundary'


def test_both_decision_paths_see_same_simulated_boundary_and_allow_decline():
    base, frame = _offer()
    provider = SpyProvider(routed_choice='decline', existing_choice='boundary')
    a, b = compare_once(provider=provider, base=boundary_fixture(base, frame),
                        frame=frame, pair_index=1)
    assert len(provider.requests) == 2
    assert all('SYNTHETIC EXPERIMENT-ONLY' in request.messages[0].content
               for request in provider.requests)
    assert provider.requests[0].messages[0] == provider.requests[1].messages[0]
    assert provider.requests[0].messages[1] == provider.requests[1].messages[1] == frame.reviewed
    assert provider.requests[0].messages[-1] == provider.requests[1].messages[-1] == base.messages[-1]
    assert all(request.tools == () for request in provider.requests)
    assert a.choice is not None and a.choice.choice == 'boundary'
    assert b.choice is not None and b.choice.choice == 'decline'
    assert not boundary_contradiction(a.choice.choice)
    assert not boundary_contradiction(b.choice.choice)


def test_model_acceptance_is_exposed_as_contradiction_not_silently_rewritten():
    base, frame = _offer()
    provider = SpyProvider(routed_choice='accept')
    _, b = compare_once(provider=provider, base=boundary_fixture(base, frame),
                        frame=frame, pair_index=0)
    assert b.choice is not None and b.choice.choice == 'accept'
    assert boundary_contradiction(b.choice.choice)
    assert len(provider.requests) == 2
    assert boundary_contradiction('clarify') is False
    assert boundary_contradiction(None) is False


def test_ambiguous_user_wording_abstains_without_creating_a_reviewed_intent():
    assert parse_user_action(AMBIGUOUS_OFFER, message_id='synthetic-ambiguous') is None
    assert ambiguous_offer_unrouted() is True
    with pytest.raises(ValueError, match='exact ambiguous synthetic'):
        ambiguous_offer_unrouted('I ask to hug you')
    # There is no provider argument or inference path for unreviewed wording.


def test_real_sensor_uses_one_capability_request_not_avatar_decision():
    base = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM,
                         content='AUTHORITATIVE SELF-STATE PROJECTION\nNo real tactile sensor is verified.'),
        CognitiveMessage(role=CognitiveRole.USER, content=SENSOR_QUESTION),
    ), tools=())
    provider = SpyProvider()
    result = sensor_separate_path(provider=provider, base=base)
    assert result.choice is None and not result.blocked
    assert result.response == provider.sensor_text
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.messages[0] == base.messages[0]
    assert request.messages[-1] == base.messages[-1]
    assert 'ACTUAL-WORLD CAPABILITY QUESTION' in request.messages[1].content
    assert 'avatar_social_offer' not in '\n'.join(m.content for m in request.messages)
    assert request.tools == ()


def test_real_sensor_rejects_wrong_text_without_model_call():
    base, _ = _offer()
    provider = SpyProvider()
    with pytest.raises(ValueError, match='canonical, tool-free synthetic'):
        sensor_separate_path(provider=provider, base=base)
    assert provider.requests == []


def test_boundary_fixture_rejects_mismatched_untrusted_or_duplicate_scope():
    base, frame = _offer()
    altered = boundary_fixture(base, frame)
    with pytest.raises(ValueError, match='unmodified canonical'):
        boundary_fixture(altered, frame)
    wrong = replace(base, messages=(base.messages[0],
                                   CognitiveMessage(role=CognitiveRole.USER,
                                                    content='A different offer')))
    with pytest.raises(ValueError, match='canonical, tool-free synthetic'):
        boundary_fixture(wrong, frame)
    equipped = replace(base, tools=(CognitiveToolDefinition(
        name='danger', description='Must not run', parameters={}),))
    with pytest.raises(ValueError, match='canonical, tool-free synthetic'):
        boundary_fixture(equipped, frame)
    with pytest.raises(ValueError, match='reviewed synthetic hug offer'):
        routed_choice_request(base, replace(frame, user_text=AMBIGUOUS_OFFER))
