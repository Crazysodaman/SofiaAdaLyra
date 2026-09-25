"""All-region policy coverage: classification is not approval or a real touch."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.embodiment.store import AvatarStore
from sofia.interaction.chat import interaction_prompt
from sofia.interaction.core import InteractionEngine
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.ledger import InteractionLedger

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'


@pytest.fixture
def engine():
    return NaturalInteractionEngine(AvatarStore(AVATAR).load())


def test_every_canonical_region_has_same_recognition_not_blanket_denial(engine):
    for region in engine.regions:
        result = engine.from_lab_pointer(fixture_id='synthetic', session_id='s1',
                                         region_id=region, gesture='touch', occurred_at=NOW)
        assert result.status == 'accepted', region
        assert result.event.region_id == region
        assert 'not approval' in result.reason
        assert result.emotion_options, region
        assert engine.from_lab_pointer(fixture_id='synthetic-stopped', session_id='s1',
                                       region_id=region, gesture='touch', occurred_at=NOW,
                                       stopped=True).status == 'denied', region


@pytest.mark.parametrize('phrase,region', [
    ('I touch your forehead', 'forehead'),
    ('I touch your left hand', 'left-hand'),
    ('I touch your tail tip', 'tail-tip'),
    ('I touch your chest', 'chest'),
    ('I touch your left breast', 'left-breast'),
    ('I touch your right inner thigh', 'right-inner-thigh'),
    ('I touch your buttocks', 'buttocks'),
    ('I touch your groin', 'groin'),
    ('I touch your genitals', 'genitals'),
])
def test_text_and_synthetic_input_share_region_semantics(engine, phrase, region):
    written = engine.from_text(content=phrase, message_id='saved-message',
                               session_id='s1', occurred_at=NOW)
    synthetic = engine.from_lab_pointer(fixture_id='synthetic', session_id='s1',
                                        region_id=region, gesture='touch', occurred_at=NOW)
    assert written is not None and written.status == synthetic.status == 'accepted'
    assert written.event.semantics == synthetic.event.semantics
    assert written.emotion_options == synthetic.emotion_options


def test_representational_recognition_never_guarantees_favorable_reaction(engine):
    for phrase in ('I pat your head', 'I touch your tail', 'I touch your chest'):
        result = engine.from_text(content=phrase, message_id='m1', session_id='s1', occurred_at=NOW)
        assert result is not None and result.status == 'accepted'
        prompt = interaction_prompt(result)
        assert 'does NOT mean' in prompt
        assert 'positively' in prompt and 'negatively' in prompt
        assert 'boundary' in prompt and 'prior conversation' in prompt
        assert 'NOT sensed touch' in prompt
        assert 'played animation' in prompt


def test_stopped_session_denies_sensitive_and_ordinary_gestures_in_ledger(tmp_path, engine):
    ledger = InteractionLedger(tmp_path / 'sofia.db')
    ledger.control(session_id='s1', message_id='stop-1',
                   content='Sofía, stop interactions', occurred_at=NOW)
    for index, region in enumerate(('head', 'chest', 'genitals')):
        result, fresh = ledger.process_text(engine=engine, content=f'I touch your {region}',
                                            message_id=f'blocked-{index}', session_id='s1',
                                            occurred_at=NOW)
        assert fresh and result is not None and result.status == 'denied'
        assert result.emotion_options == ()
        assert ledger.accepted(f'blocked-{index}') is None
    ledger.control(session_id='s1', message_id='resume-1',
                   content='Sofía, resume interactions', occurred_at=NOW)
    result, fresh = ledger.process_text(engine=engine, content='I touch your chest',
                                        message_id='new-chest', session_id='s1', occurred_at=NOW)
    assert fresh and result is not None and result.status == 'accepted'
    assert ledger.accepted('new-chest') == ('s1', 'chest', 'touch')
