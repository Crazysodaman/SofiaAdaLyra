"""Live phrase coverage: isolated in-memory parsing and temporary-DB ledger checks."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.embodiment.store import AvatarStore
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.chat import interaction_prompt
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.ledger import InteractionLedger

AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'
NOW = datetime(2026, 9, 21, 22, tzinfo=timezone.utc)


def _engine():
    return NaturalInteractionEngine(AvatarStore(AVATAR).load())


def _interpret(content, *, stopped=False):
    return _engine().from_text(
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


def test_new_grammar_is_enforced_by_durable_stop_and_replay(tmp_path):
    ledger = InteractionLedger(tmp_path / 'isolated.db')
    engine = _engine()
    first, fresh = ledger.process_text(
        engine=engine, content='Good girl, gently touches your butt',
        message_id='saved-live-1', session_id='test-session', occurred_at=NOW,
    )
    assert fresh is True and first is not None and first.status == 'accepted'
    assert ledger.accepted('saved-live-1') == ('test-session', 'buttocks', 'touch')
    replay, fresh = ledger.process_text(
        engine=engine, content='Good girl, gently touches your butt',
        message_id='saved-live-1', session_id='test-session', occurred_at=NOW,
    )
    assert fresh is False and replay is not None and replay.status == 'acknowledged'
    ledger.control(session_id='test-session', message_id='stop-1',
                   content='Sofía, stop interactions', occurred_at=NOW)
    blocked, fresh = ledger.process_text(
        engine=engine, content='gropes your butt',
        message_id='saved-live-2', session_id='test-session', occurred_at=NOW,
    )
    assert fresh is True and blocked is not None and blocked.status == 'denied'
    assert ledger.accepted('saved-live-2') is None
