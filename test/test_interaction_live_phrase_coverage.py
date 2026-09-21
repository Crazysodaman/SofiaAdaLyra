"""Live-transcript phrase coverage: in-memory parsing, no DB or model calls."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.embodiment.store import AvatarStore
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.chat import interaction_prompt
from sofia.interaction.grammar import NaturalInteractionEngine

AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'
NOW = datetime(2026, 9, 21, 22, tzinfo=timezone.utc)


def _interpret(content, *, stopped=False):
    return NaturalInteractionEngine(AvatarStore(AVATAR).load()).from_text(
        content=content, message_id='saved-live-1', session_id='test-session',
        occurred_at=NOW, stopped=stopped,
    )


@pytest.mark.parametrize('text,gesture', (
    ('Good girl, gently touches your butt', 'touch'),
    ('gropes your butt', 'intimate-touch'),
    ('*gropes your butt*', 'intimate-touch'),
    ('I grope your butt', 'intimate-touch'),
))
def test_live_phrases_are_classified_as_described_virtual_gestures(text, gesture):
    decision = _interpret(text)
    assert decision is not None
    assert decision.status == 'accepted'  # recognized, NOT consent or real contact
    assert decision.event.region_id == 'buttocks'
    assert decision.event.gesture == gesture
    assert decision.event.source == 'user_text'
    assert decision.event.evidence_ref == 'saved-live-1'
    prompt = interaction_prompt(decision)
    assert '"region_id": "buttocks"' in prompt
    assert '"policy_status": "accepted"' in prompt
    assert 'NOT sensed' in prompt
    assert 'does NOT mean Sofía consented' in prompt


@pytest.mark.parametrize('text', (
    'Good girl, gently touches your butt',
    'gropes your butt',
))
def test_stop_still_denies_newly_recognized_phrases(text):
    decision = _interpret(text, stopped=True)
    assert decision is not None and decision.status == 'denied'
    assert '"region_id": null' in interaction_prompt(decision)


@pytest.mark.parametrize('text', (
    'What if I grope your butt?',
    'I grope your butt and pat your ear',
    'Good girl, gently touches your butt and rubs your tail',
    '"gropes your butt"',
    'I do not grope your butt',
    'grope your butt; then move away',
))
def test_discussion_quotes_negation_and_composites_still_abstain(text):
    assert _interpret(text) is None


def test_ear_ambiguity_and_hug_offer_are_not_silently_converted():
    ear = _interpret('*pats your ear*')
    assert ear is not None and ear.status == 'clarify'
    assert ear.event.region_id is None
    assert _interpret('I ask to hug you') is None
    offer = parse_user_action('I ask to hug you', message_id='saved-offer-1')
    assert offer is not None and offer.modality == 'offered'
