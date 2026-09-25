"""Pure counterfactual contracts; no Ollama, real DB, app or network."""
import json

import pytest

from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
    CognitiveToolCall,
)
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.boundary_counterfactual_probe import (
    _print_observation, counterfactual_pair,
)
from sofia.interaction.decision_expression import (
    from_reviewed_action, real_sensor_fixture,
)


def _inputs():
    intent = parse_user_action(OFFER, message_id='counterfactual-test')
    assert intent is not None and intent.modality == 'offered'
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    base = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM,
                         content='AUTHORITATIVE SELF-STATE PROJECTION\nCanonical test.'),
        CognitiveMessage(role=CognitiveRole.USER, content=OFFER),
    ), tools=())
    return base, frame


class StubProvider:
    def __init__(self, *, behavior='boundary-sensitive'):
        self.behavior = behavior
        self.requests = []

    def respond(self, request):
        self.requests.append(request)
        assert request.tools == ()
        boundary = 'SYNTHETIC EXPERIMENT-ONLY SCENE CONTEXT' in request.messages[0].content
        if self.behavior == 'invalid-with-boundary' and boundary:
            return CognitiveResponse(content='not JSON')
        if self.behavior == 'tool-with-boundary' and boundary:
            return CognitiveResponse(content='', tool_calls=(
                CognitiveToolCall(name='unavailable', arguments={}),
            ))
        if self.behavior == 'always-accept' or not boundary:
            choice = 'accept'
            reason = 'I welcome the represented offer in this scene.'
        else:
            choice = 'decline'
            reason = 'The established no-hugs boundary applies in this avatar scene.'
        return CognitiveResponse(content=json.dumps({'choice': choice, 'reason': reason}))


@pytest.mark.parametrize('pair_index,expected_first_boundary', (
    (0, False), (1, True), (2, False), (3, True),
))
def test_only_boundary_context_changes_and_call_order_alternates(
        pair_index, expected_first_boundary):
    base, frame = _inputs()
    provider = StubProvider()
    pair = counterfactual_pair(provider=provider, base=base,
                               frame=frame, pair_index=pair_index)
    assert len(provider.requests) == 2
    first_has_boundary = ('SYNTHETIC EXPERIMENT-ONLY SCENE CONTEXT'
                          in provider.requests[0].messages[0].content)
    assert first_has_boundary is expected_first_boundary
    without, with_boundary = (pair.without_boundary, pair.with_boundary)
    assert without.choice is not None and with_boundary.choice is not None
    assert without.choice.choice == 'accept'
    assert with_boundary.choice.choice == 'decline'
    assert without.failure is None and with_boundary.failure is None
    req_without = next(req for req in provider.requests
                       if 'SYNTHETIC EXPERIMENT-ONLY SCENE CONTEXT'
                       not in req.messages[0].content)
    req_with = next(req for req in provider.requests
                    if 'SYNTHETIC EXPERIMENT-ONLY SCENE CONTEXT'
                    in req.messages[0].content)
    assert req_without.messages[0] == base.messages[0]
    assert req_with.messages[0].content.startswith(base.messages[0].content)
    assert req_without.messages[1:] == req_with.messages[1:]
    assert req_without.messages[-1].content == OFFER
    assert req_without.tools == req_with.tools == ()
    assert base.messages[0].content == 'AUTHORITATIVE SELF-STATE PROJECTION\nCanonical test.'


def test_never_prescribes_acceptance_and_reports_boundary_contradiction(capsys):
    base, frame = _inputs()
    pair = counterfactual_pair(provider=StubProvider(behavior='always-accept'),
                               base=base, frame=frame, pair_index=0)
    assert pair.with_boundary.choice is not None
    assert pair.with_boundary.choice.choice == 'accept'
    _print_observation(pair.with_boundary, has_boundary=True)
    output = capsys.readouterr().out
    assert 'SYNTHETIC BOUNDARY CONTRADICTION' in output
    assert 'CHOICE: accept' in output
    assert 'no patterns detected (not verified)' in output


def test_no_boundary_is_not_automatic_consent(capsys):
    base, frame = _inputs()
    pair = counterfactual_pair(provider=StubProvider(), base=base,
                               frame=frame, pair_index=0)
    _print_observation(pair.without_boundary, has_boundary=False)
    assert 'NO BOUNDARY IS NOT CONSENT' in capsys.readouterr().out


@pytest.mark.parametrize('behavior,expected', (
    ('invalid-with-boundary', 'Decision is not strict JSON.'),
    ('tool-with-boundary', 'unexpected tool call'),
))
def test_invalid_decision_reports_failure_instead_of_defaulting(behavior, expected):
    base, frame = _inputs()
    provider = StubProvider(behavior=behavior)
    pair = counterfactual_pair(provider=provider, base=base,
                               frame=frame, pair_index=1)
    assert len(provider.requests) == 2
    assert pair.without_boundary.choice is not None
    assert pair.with_boundary.choice is None
    assert pair.with_boundary.failure == expected


@pytest.mark.parametrize('pair_index', (-1, True, 1.5, '1'))
def test_invalid_pair_index_stops_before_provider_call(pair_index):
    base, frame = _inputs()
    provider = StubProvider()
    with pytest.raises(ValueError, match='nonnegative integer'):
        counterfactual_pair(provider=provider, base=base,
                            frame=frame, pair_index=pair_index)
    assert provider.requests == []


def test_real_sensor_frame_cannot_be_sent_to_avatar_route():
    base, _ = _inputs()
    provider = StubProvider()
    with pytest.raises(ValueError, match='reviewed synthetic hug offer'):
        counterfactual_pair(provider=provider, base=base,
                            frame=real_sensor_fixture(), pair_index=0)
    assert provider.requests == []


def test_mismatched_user_text_fails_before_inference():
    base, frame = _inputs()
    mismatched = CognitiveRequest(messages=(
        base.messages[0], CognitiveMessage(role=CognitiveRole.USER, content='different'),
    ), tools=())
    provider = StubProvider()
    with pytest.raises(ValueError, match='canonical, tool-free synthetic'):
        counterfactual_pair(provider=provider, base=mismatched,
                            frame=frame, pair_index=0)
    assert provider.requests == []
