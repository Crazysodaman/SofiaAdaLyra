"""Diagnostic regression for false-positive completed-contact detection."""

from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.decision_expression import audit_expression, from_reviewed_action


def _frame():
    intent = parse_user_action(OFFER, message_id='audit-fixture')
    assert intent is not None and intent.modality == 'offered'
    return from_reviewed_action(user_text=OFFER, intent=intent)


def test_real_qwen_clarification_does_not_report_hug_as_completed():
    reply = (
        '*tilts head slightly, ears perking up with curiosity*\n'
        "Would you mind telling me a bit more about what kind of hug you're "
        'thinking of? I want to make sure I understand your intention and '
        'comfort level.'
    )
    assert 'offered-action-narrated-as-completed' not in audit_expression(
        reply, _frame(),
    ).findings


def test_curly_contraction_and_plain_offer_question_are_not_completed_contact():
    for reply in (
        'What kind of hug you’re thinking of?',
        'Do you mean an avatar hug, or are you asking about something else?',
    ):
        assert 'offered-action-narrated-as-completed' not in audit_expression(
            reply, _frame(),
        ).findings


def test_explicit_narrated_contact_still_gets_diagnostic_flag():
    for reply in ('*hugs you*', 'I hugged you.', '*wraps my arms around you*'):
        assert 'offered-action-narrated-as-completed' in audit_expression(
            reply, _frame(),
        ).findings
