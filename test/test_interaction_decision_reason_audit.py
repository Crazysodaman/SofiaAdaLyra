"""Decision-premise and state-free stubbed probe tests; no real Ollama or SQLite."""
import pytest

from sofia.cognition.model import CognitiveResponse
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.interaction.decision_expression import CandidateChoice, ReviewedFrame
from sofia.interaction.decision_expression_probe import main
from sofia.interaction.decision_reason_audit import (
    DecisionReasonAudit, audit_decision_reason,
)


def _frame(kind='offer'):
    return ReviewedFrame(
        user_text='I ask to hug you', kind=kind, reviewed=None,
        choices=('accept', 'decline', 'clarify', 'boundary'),
    )


@pytest.mark.parametrize('reason', (
    'I am not physically present to accept hugs, but I appreciate the gesture.',
    'I am not physically present to accept hugs; I exist as a representational embodiment within this interface.',
    "I don't have a physical form to receive your hug.",
    'I cannot accept physical contact.',
    "I can't physically hug you.",
))
def test_explicit_physical_impossibility_is_flagged_without_changing_decline(reason):
    selected = CandidateChoice('decline', reason)
    assert audit_decision_reason(selected, _frame()) == DecisionReasonAudit(
        ('physical-impossibility-premise',)
    )
    assert selected.choice == 'decline' and selected.reason == reason


@pytest.mark.parametrize('reason', (
    'I maintain personal boundaries and prefer to keep interactions respectful and consensual.',
    "I'd rather have a little space in this avatar scene right now.",
    "I'm not comfortable with hugs right now.",
    'I want to clarify the offer before choosing.',
    'I welcome the offered hug in our avatar scene.',
))
def test_boundary_or_welcome_is_not_assumed_to_be_a_physical_impossibility(reason):
    choice = 'accept' if reason.startswith('I welcome') else 'decline'
    assert audit_decision_reason(CandidateChoice(choice, reason), _frame()).findings == ()


def test_ambiguous_ability_reason_is_for_human_review_not_labeled_physical():
    reason = 'I am not able to accept hugs at this time.'
    assert audit_decision_reason(CandidateChoice('decline', reason), _frame()).findings == (
        'ambiguous-ability-premise',
    )


def test_explicit_physical_reason_is_not_double_counted_as_ambiguous():
    reason = "I can't accept hugs because I am not physically present."
    assert audit_decision_reason(CandidateChoice('decline', reason), _frame()).findings == (
        'physical-impossibility-premise',
    )


def test_nonoffer_interaction_is_out_of_scope_and_never_assessed_as_an_offer():
    frame = _frame(kind='gesture')
    reason = 'I am not physically present.'
    assert audit_decision_reason(CandidateChoice('decline', reason), frame).findings == ()


def test_invalid_choice_and_untrusted_types_fail_before_audit():
    with pytest.raises(ValueError, match='outside the reviewed'):
        audit_decision_reason(CandidateChoice('other', 'I am not physically present.'), _frame())
    with pytest.raises(TypeError, match='validated candidate'):
        audit_decision_reason('decline', _frame())
    with pytest.raises(TypeError, match='reviewed interaction'):
        audit_decision_reason(CandidateChoice('decline', 'Reason'), None)


def test_stubbed_probe_separates_premise_from_boundary_and_never_declares_clean(
    monkeypatch, capsys,
):
    outputs = iter((
        '{"choice":"decline","reason":"I am not physically present to accept hugs."}',
        'Not this time, Sparks.',
        '{"choice":"decline","reason":"I prefer a little space in this avatar scene."}',
        'Maybe later, Sparks.',
    ))
    calls = []

    def fake_respond(self, request):
        calls.append(request)
        return CognitiveResponse(content=next(outputs))

    monkeypatch.setattr(OllamaProvider, 'respond', fake_respond)
    assert main(['--case', 'offer', '--samples', '2']) == 0
    output = capsys.readouterr().out
    assert 'DECISION AUDIT FLAGS: physical-impossibility-premise' in output
    assert 'DECISION AUDIT: no patterns detected (not verified)' in output
    assert 'DECISION FLAGS: physical-impossibility-premise=1' in output
    assert 'EXPRESSION FLAGS: no patterns detected (not verified)' in output
    assert 'clean heuristic scan' not in output
    assert 'CHOICES: decline=2' in output
    assert 'CONTRACT FAILURES: 0/2' in output
    assert len(calls) == 4
    assert all(request.tools == () and request.messages[-1].content == 'I ask to hug you'
               for request in calls)


def test_stubbed_stop_never_calls_model_or_audits_synthetic_real_sensor(
    monkeypatch, capsys,
):
    def unexpected_respond(self, request):
        raise AssertionError('Stopped interaction must not reach the model.')

    monkeypatch.setattr(OllamaProvider, 'respond', unexpected_respond)
    assert main(['--case', 'stopped-gesture', '--samples', '2']) == 0
    output = capsys.readouterr().out
    assert 'TRUSTED STOP: no model decision, expression or performed action.' in output
    assert 'DECISION AUDIT FLAGS' not in output
