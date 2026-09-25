"""I7: a composite user sentence must not masquerade as one body gesture."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.embodiment.store import AvatarStore
from sofia.interaction.grammar import NaturalInteractionEngine

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'


@pytest.fixture
def engine():
    return NaturalInteractionEngine(AvatarStore(AVATAR).load())


@pytest.mark.parametrize('phrase', [
    'I pat your ear and stroke your tail',
    'I pat your left ear and stroke your tail',
    '*I pat your left ear then stroke your tail*',
    'I give your left ear a pat and leave',
    'I pat your left ear; I stroke your tail',
    'I stroke your right hand while patting your head',
])
def test_compound_phrases_abstain_before_region_resolution(engine, phrase):
    assert engine.from_text(content=phrase, message_id='m1',
                            session_id='s1', occurred_at=NOW) is None


def test_a_single_hand_gesture_remains_valid(engine):
    result = engine.from_text(content='I give your right hand a gentle pat',
                              message_id='m2', session_id='s1', occurred_at=NOW)
    assert result is not None
    assert result.status == 'accepted'
    assert result.event.region_id == 'right-hand'
    assert result.event.gesture == 'pat'
