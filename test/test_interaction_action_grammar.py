"""Whole-body action language is classified but never executed by this parser."""
import pytest

from sofia.interaction.action_grammar import parse_user_action


@pytest.mark.parametrize('sentence,action,modality', [
    ('I hug you', 'hug', 'described'),
    ('Sofía, I embrace you', 'hug', 'described'),
    ('I ask to hug you', 'hug', 'offered'),
    ('I offer you my hand', 'offer-hand', 'offered'),
    ('I help you in the lab', 'help-in-lab', 'offered'),
    ('I sit in your lap', 'sit-in-lap', 'described'),
    ('*I move away*', 'move-away', 'described'),
])
def test_exact_single_actions(sentence, action, modality):
    intent = parse_user_action(sentence, message_id='saved-1')
    assert (intent.actor, intent.target, intent.action_id, intent.modality) == (
        'user', 'sofia', action, modality)


@pytest.mark.parametrize('sentence', [
    'Sofía hugs me', 'I hug you and kiss your cheek',
    'I ask to hug you then I do it', 'Would I hug you?',
    'I do not hug you', '"I hug you"', 'I hug your right hand',
    'I touch your cheek', 'I install a package on your server',
])
def test_discussion_unknown_actors_and_composites_abstain(sentence):
    assert parse_user_action(sentence, message_id='saved-1') is None
