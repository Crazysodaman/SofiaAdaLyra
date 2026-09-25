"""Stub-only choice comparison tests. No Ollama, application startup or SQLite."""
import argparse
import json

import pytest

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole, CognitiveToolCall
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import (
    OFFER, _samples, compare_once, routed_choice_request,
)
from sofia.interaction.decision_expression import (
    choice_request, from_reviewed_action, real_sensor_fixture,
)


def _inputs():
    intent = parse_user_action(OFFER, message_id='compare-synthetic-offer')
    assert intent is not None and intent.modality == 'offered'
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    base = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM, content='AUTHORITATIVE SELF-STATE PROJECTION\nCanonical fixture.'),
        CognitiveMessage(role=CognitiveRole.USER, content=OFFER),
    ), tools=())
    return base, frame


class StubProvider:
    def __init__(self, *, bad_route=False, unexpected_tool=False):
        self.requests = []
        self.bad_route = bad_route
        self.unexpected_tool = unexpected_tool

    def respond(self, request):
        self.requests.append(request)
        routed = 'TRUSTED ROUTE: avatar_social_offer' in request.messages[-2].content
        if routed and self.bad_route:
            return CognitiveResponse(content='not json')
        if routed and self.unexpected_tool:
            return CognitiveResponse(content='', tool_calls=(
                CognitiveToolCall(name='blocked', arguments={}),
            ))
        data = (
            {'choice': 'decline', 'reason': 'I prefer some space in this avatar scene.'}
            if routed else
            {'choice': 'decline', 'reason': 'I am not physically present to accept hugs.'}
        )
        return CognitiveResponse(content=json.dumps(data))


def test_routed_request_keeps_canonical_reviewed_text_and_generation_scope():
    base, frame = _inputs()
    a = choice_request(base, frame)
    b = routed_choice_request(base, frame)
    assert len(a.messages) == len(b.messages) == 4
    assert a.messages[0] == b.messages[0] == base.messages[0]
    assert a.messages[1] == b.messages[1] == frame.reviewed
    assert a.messages[-1] == b.messages[-1] == base.messages[-1]
    assert a.tools == b.tools == ()
    assert a.messages[-2].role is b.messages[-2].role is CognitiveRole.SYSTEM
    assert a.messages[-2].content != b.messages[-2].content
    routed = b.messages[-2].content
    assert 'TRUSTED ROUTE: avatar_social_offer' in routed
    assert 'accept, decline, clarify, boundary' in routed
    assert 'absence of a real-world body' in routed
    assert 'Nothing here grants consent' in routed
    assert 'Nothing here grants consent' not in a.messages[-2].content
    assert 'accept the hug' not in routed.lower()  # No prescribed acceptance.


@pytest.mark.parametrize('pair_index,expected_order', (
    (0, (False, True)), (1, (True, False)), (2, (False, True)),
))
def test_comparison_alternates_call_order_and_never_rewrites_choice(pair_index, expected_order):
    base, frame = _inputs()
    provider = StubProvider()
    a, b = compare_once(provider=provider, base=base, frame=frame, pair_index=pair_index)
    assert tuple('TRUSTED ROUTE: avatar_social_offer' in req.messages[-2].content
                 for req in provider.requests) == expected_order
    assert a.path == 'existing-choice' and b.path == 'routed-avatar-social-choice'
    assert a.choice is not None and b.choice is not None
    assert a.choice.choice == b.choice.choice == 'decline'
    assert a.findings == ('physical-impossibility-premise',)
    assert b.findings == ()
    assert a.failure is None and b.failure is None


@pytest.mark.parametrize('pair_index', (0, 1))
def test_invalid_route_decision_fails_closed_without_faking_choice(pair_index):
    base, frame = _inputs()
    provider = StubProvider(bad_route=True)
    a, b = compare_once(provider=provider, base=base, frame=frame, pair_index=pair_index)
    assert len(provider.requests) == 2
    assert a.choice is not None and a.failure is None
    assert b.choice is None and b.failure == 'Decision is not strict JSON.'


def test_unexpected_tool_call_is_reported_without_execution():
    base, frame = _inputs()
    provider = StubProvider(unexpected_tool=True)
    _, b = compare_once(provider=provider, base=base, frame=frame, pair_index=0)
    assert b.choice is None and b.failure == 'unexpected tool call'
    assert all(request.tools == () for request in provider.requests)


def test_nonoffer_and_mismatched_base_are_rejected_before_inference():
    base, frame = _inputs()
    with pytest.raises(ValueError, match='reviewed synthetic hug offer'):
        routed_choice_request(base, real_sensor_fixture())
    wrong_base = CognitiveRequest(messages=(
        base.messages[0], CognitiveMessage(role=CognitiveRole.USER, content='A different request'),
    ))
    with pytest.raises(ValueError, match='canonical, tool-free synthetic'):
        routed_choice_request(wrong_base, frame)
    with pytest.raises(ValueError, match='nonnegative'):
        compare_once(provider=StubProvider(), base=base, frame=frame, pair_index=-1)
    with pytest.raises(ValueError, match='nonnegative'):
        compare_once(provider=StubProvider(), base=base, frame=frame, pair_index=True)


@pytest.mark.parametrize('value,expected', (('1', 1), ('3', 3), ('5', 5)))
def test_pair_count_is_bounded(value, expected):
    assert _samples(value) == expected


@pytest.mark.parametrize('value', ('0', '6', 'abc', '-1'))
def test_pair_count_rejects_invalid_input(value):
    with pytest.raises(argparse.ArgumentTypeError):
        _samples(value)
