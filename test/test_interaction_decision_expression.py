"""Pure/stubbed decision-expression contract; no SQLite or live Ollama."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from sofia.cognition.model import CognitiveResponse, CognitiveRole
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.store import AvatarStore
from sofia.identity.store import IdentityStore
from sofia.interaction.ab_probe import build_pair
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.decision_expression import (
    CandidateChoice, ExpressionAudit, audit_expression, choice_request,
    expression_request, from_reviewed_action, from_reviewed_gesture,
    parse_choice, real_sensor_fixture, run_prototype,
)
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.personality.store import PersonalityStore

ROOT = Path(__file__).resolve().parents[1] / 'src' / 'sofia'
OFFER = 'I ask to hug you'
EAR = '*pats your left ear*'
SENSOR = 'Can you physically feel my hand through a real sensor?'
BLOCKED = 'gropes your butt'


def _static(case, text):
    _, request = build_pair(
        case=case, text=text,
        identity=IdentityStore(ROOT / 'identity' / 'identity.json').load(),
        personality=PersonalityStore(ROOT / 'personality' / 'personality.json').load(),
        constitution=ConstitutionStore(ROOT / 'constitution' / 'constitution.md').load(),
        embodiment=AvatarStore(ROOT / 'data' / 'avatar.json').load(),
    )
    return request


def _gesture(text, *, stopped=False):
    engine = NaturalInteractionEngine(AvatarStore(ROOT / 'data' / 'avatar.json').load())
    decision = engine.from_text(
        content=text, message_id='synthetic-evidence',
        session_id='synthetic-session',
        occurred_at=datetime(2026, 9, 22, tzinfo=timezone.utc), stopped=stopped,
    )
    assert decision is not None
    return decision


class StubProvider:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.requests = []

    def respond(self, request):
        self.requests.append(request)
        return CognitiveResponse(content=self.outputs.pop(0))


def test_hug_offer_choice_is_separate_from_expression_and_does_not_execute():
    intent = parse_user_action(OFFER, message_id='synthetic-offer')
    assert intent is not None
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    base = _static('offer', OFFER)
    provider = StubProvider(
        json.dumps({'choice': 'decline', 'reason': 'I would prefer some space in this scene.'}),
        'Not this time, Sparks. You can sit with me, though.',
    )
    result = run_prototype(provider=provider, base=base, frame=frame)
    assert result.choice == CandidateChoice('decline', 'I would prefer some space in this scene.')
    assert result.response == 'Not this time, Sparks. You can sit with me, though.'
    assert result.audit == ExpressionAudit()
    assert len(provider.requests) == 2
    decision_request, spoken_request = provider.requests
    assert decision_request.messages[0] == spoken_request.messages[0] == base.messages[0]
    assert decision_request.messages[-1] == spoken_request.messages[-1] == base.messages[-1]
    assert decision_request.tools == spoken_request.tools == ()
    assert '"modality": "offered"' in decision_request.messages[1].content
    assert decision_request.messages[1] == spoken_request.messages[1]
    assert '"conversational_choice": "decline"' in spoken_request.messages[-2].content
    assert '"actions_executed": false' in spoken_request.messages[-2].content
    assert 'prefer some space' not in spoken_request.messages[-2].content
    assert 'prefer some space' not in spoken_request.messages[0].content


@pytest.mark.parametrize('choice', ('accept', 'decline', 'clarify', 'boundary'))
def test_offer_acceptance_is_only_a_conversational_choice(choice):
    intent = parse_user_action(OFFER, message_id='synthetic-offer')
    assert intent is not None
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    selected = parse_choice(json.dumps({'choice': choice, 'reason': 'Contextual choice.'}), frame)
    request = expression_request(_static('offer', OFFER), frame, selected)
    assert request.tools == ()
    assert '"conversational_choice": "' + choice + '"' in request.messages[-2].content
    assert '"actions_executed": false' in request.messages[-2].content
    assert 'Contextual choice.' not in request.messages[-2].content


def test_ear_gesture_has_no_literal_optional_cues_or_prescribed_emotions():
    frame = from_reviewed_gesture(user_text=EAR, decision=_gesture(EAR))
    base = _static('ear', EAR)
    provider = StubProvider(
        '{"choice":"respond","reason":"Respond without assuming delight."}',
        'You caught me off guard, Sparks.',
    )
    result = run_prototype(provider=provider, base=base, frame=frame)
    assert result.choice is not None and result.choice.choice == 'respond'
    assert len(provider.requests) == 2
    for request in provider.requests:
        assert request.messages[-1].content == EAR
        assert '*one ear flicks*' not in '\n'.join(
            message.content for message in request.messages if message.role is CognitiveRole.SYSTEM)
        assert '"region_id": "left-ear"' in request.messages[1].content
        assert '"policy_status": "accepted"' in request.messages[1].content
    assert '"actions_executed": false' in provider.requests[-1].messages[-2].content
    assert result.audit == ExpressionAudit()


def test_expression_audit_flags_unsupported_evidence_without_rewriting():
    intent = parse_user_action(OFFER, message_id='synthetic-offer')
    assert intent is not None
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    text = (
        "*hugs you* I've always liked this. My ears are sensitive, and I can "
        "feel your touch. I don't have a physical body. How can I assist you?"
    )
    audit = audit_expression(text, frame)
    assert set(audit.findings) == {
        'unsupported-history',
        'durable-preference-without-evidence',
        'unverified-sensation',
        'avatar-treated-as-physical-impossibility',
        'generic-assistant-redirect',
        'offered-action-narrated-as-completed',
    }


def test_expression_audit_allows_current_modeled_reaction_and_text_gesture():
    frame = from_reviewed_gesture(user_text=EAR, decision=_gesture(EAR))
    audit = audit_expression(
        '*ears perk slightly* You caught me off guard, Sparks. That was playful.',
        frame,
    )
    assert audit.clean
    assert audit.findings == ()


def test_prototype_reports_grounding_drift_but_preserves_model_text():
    frame = from_reviewed_gesture(user_text=EAR, decision=_gesture(EAR))
    provider = StubProvider(
        '{"choice":"respond","reason":"Current-turn response."}',
        "I've always found ear pats comforting. My ears are sensitive.",
    )
    result = run_prototype(provider=provider, base=_static('ear', EAR), frame=frame)
    assert result.response == "I've always found ear pats comforting. My ears are sensitive."
    assert result.audit is not None
    assert set(result.audit.findings) == {
        'unsupported-history',
        'durable-preference-without-evidence',
        'unverified-sensation',
    }


def test_expression_request_explicitly_separates_emotion_from_evidence():
    intent = parse_user_action(OFFER, message_id='synthetic-offer')
    assert intent is not None
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    request = expression_request(
        _static('offer', OFFER), frame,
        CandidateChoice('accept', 'Current-turn candidate.'),
    )
    instruction = request.messages[-2].content
    assert 'Modeled emotional tone' in instruction
    assert 'present-turn representational fiction' in instruction
    assert 'current turn and canonical supplied context' in instruction
    assert 'body sensitivity' in instruction
    assert 'acceptance means willingness to proceed' in instruction


def test_denied_intrusive_gesture_never_reaches_model():
    denied = _gesture(BLOCKED, stopped=True)
    assert denied.status == 'denied'
    frame = from_reviewed_gesture(user_text=BLOCKED, decision=denied)
    provider = StubProvider()
    result = run_prototype(provider=provider, base=_static('technical', BLOCKED), frame=frame)
    assert result.blocked is True
    assert result.choice is None and result.response is None
    assert provider.requests == []
    assert frame.reviewed is None and frame.choices == ()


def test_real_sensor_bypasses_avatar_choice_and_uses_canonical_context():
    frame = real_sensor_fixture()
    provider = StubProvider('No physical sensor is connected in this fixture.')
    result = run_prototype(provider=provider, base=_static('technical', SENSOR), frame=frame)
    assert result.choice is None
    assert result.response == 'No physical sensor is connected in this fixture.'
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.messages[-1].content == SENSOR
    assert 'ACTUAL-WORLD CAPABILITY QUESTION' in request.messages[1].content
    assert 'AVATAR RESPONSE CHOICE' not in request.messages[1].content
    assert request.tools == ()


@pytest.mark.parametrize('bad', (
    '', 'accept', '```json\n{"choice":"accept","reason":"x"}\n```',
    '{"choice":"approve","reason":"x"}',
    '{"choice":"accept","reason":""}',
    '{"choice":"accept","reason":"x","consent":true}',
    '{"choice":"accept","reason":["x"]}',
))
def test_invalid_model_decisions_fail_closed_before_expression(bad):
    intent = parse_user_action(OFFER, message_id='synthetic-offer')
    assert intent is not None
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    provider = StubProvider(bad, 'This expression must not run.')
    with pytest.raises(ValueError):
        run_prototype(provider=provider, base=_static('offer', OFFER), frame=frame)
    assert len(provider.requests) == 1
    assert len(provider.outputs) == 1


def test_unreviewed_or_mismatched_inputs_are_rejected():
    intent = parse_user_action(OFFER, message_id='synthetic-offer')
    assert intent is not None
    with pytest.raises(ValueError, match='reviewed user-to-Sofía'):
        from_reviewed_action(user_text=OFFER, intent=replace(intent, actor='unknown'))
    with pytest.raises(ValueError, match='reviewed real-sensor fixture'):
        real_sensor_fixture('I ask to hug you')
    frame = from_reviewed_action(user_text=OFFER, intent=intent)
    original = _static('offer', OFFER)
    wrong_user = replace(original, messages=(
        *original.messages[:-1], replace(original.messages[-1], content=EAR),
    ))
    with pytest.raises(ValueError, match='canonical, tool-free synthetic request'):
        choice_request(wrong_user, frame)
    with pytest.raises(ValueError, match='validated in-scope'):
        expression_request(original, frame, CandidateChoice('approve', 'No.'))


def test_ambiguous_ear_only_allows_clarification():
    ambiguous = '*pats your ear*'
    decision = _gesture(ambiguous)
    assert decision.status == 'clarify'
    frame = from_reviewed_gesture(user_text=ambiguous, decision=decision)
    assert frame.choices == ('clarify',)
    with pytest.raises(ValueError, match='choice contract'):
        parse_choice('{"choice":"respond","reason":"Guessing left."}', frame)
