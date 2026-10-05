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


@pytest.mark.parametrize('sentence,action,modality', [
    ('I strike a sensual pose for you', 'sensual-pose', 'described'),
    ('I flash my chest at you', 'flash-chest', 'described'),
    ('I press my breasts together for you', 'breast-press-pose', 'described'),
    ('I have sex with you', 'sexual-intercourse', 'described'),
    ('I ask to have sex with you', 'sexual-intercourse', 'offered'),
    ('I perform oral sex on you', 'oral-sex', 'described'),
    ('I ask to perform oral sex on you', 'oral-sex', 'offered'),
    ('I give you a blowjob', 'fellatio', 'described'),
    ('I perform cunnilingus on you', 'cunnilingus', 'described'),
    ('I perform analingus on you', 'analingus', 'described'),
    ('I have anal sex with you', 'anal-sex', 'described'),
    ('I have vaginal sex with you', 'vaginal-sex', 'described'),
    (
        'I manually stimulate your genitals',
        'manual-genital-stimulation',
        'described',
    ),
    (
        'I ask to manually stimulate your genitals',
        'manual-genital-stimulation',
        'offered',
    ),
    ('I mutually masturbate with you', 'mutual-masturbation', 'described'),
    ('I rub my genitals against yours', 'genital-rubbing', 'described'),
])
def test_exact_private_actions_use_the_same_bounded_action_path(
    sentence,
    action,
    modality,
):
    intent = parse_user_action(sentence, message_id='saved-private-action')
    assert intent is not None
    assert (intent.actor, intent.target, intent.action_id, intent.modality) == (
        'user', 'sofia', action, modality,
    )


@pytest.mark.parametrize('sentence', [
    'Could we have sex?',
    'I would have sex with you',
    'I pretend to perform oral sex on you',
    'I have sex with you and kiss you',
    '"I have sex with you"',
])
def test_private_questions_hypotheticals_quotes_and_composites_abstain(sentence):
    assert parse_user_action(sentence, message_id='saved-private-action') is None
