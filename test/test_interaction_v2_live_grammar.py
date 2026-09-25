"""Integration regression for reviewed v2 names/verbs in the existing CLI engine."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.embodiment.store import AvatarStore
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.live_guard import unsupported_composite_gesture
from sofia.interaction.registry import CATALOG_VERSION

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'


@pytest.fixture
def engine():
    return NaturalInteractionEngine(AvatarStore(AVATAR).load())


@pytest.mark.parametrize('text,gesture,region', [
    ('I caress your left forearm', 'caress', 'left-forearm'),
    ('I kissed your right cheek', 'kiss', 'right-cheek'),
    ('I gently brush your tail tip', 'brush', 'tail-tip'),
    ('I boop your nose', 'boop', 'nose'),
    ('I massage your right shoulder', 'massage', 'right-shoulder'),
    ("I stroke Sofia's left ear tip", 'stroke', 'left-ear-tip'),
    ('I touch your tummy', 'touch', 'abdomen'),
])
def test_reviewed_verb_or_alias_in_live_engine(engine, text, gesture, region):
    result = engine.from_text(content=text, message_id='m1', session_id='s1', occurred_at=NOW)
    assert result is not None and result.status == 'accepted'
    assert (result.event.gesture, result.event.region_id) == (gesture, region)
    if gesture in ('kiss', 'caress', 'brush', 'boop', 'massage'):
        assert result.event.registry_version == CATALOG_VERSION


@pytest.mark.parametrize('text', [
    'I kiss your ear', 'I touch your hand', 'I caress your unknown organ',
    'I caress your left ear and kiss your right ear',
    'Would I kiss your cheek?', 'I do not kiss your cheek',
    '`I kiss your cheek`', '"I kiss your cheek"',
    'I caress your left ear then grab your tail',
])
def test_unknown_ambiguous_or_discussion_never_accepted(engine, text):
    outcome = engine.from_text(content=text, message_id='m1', session_id='s1', occurred_at=NOW)
    assert outcome is None or outcome.status != 'accepted'


@pytest.mark.parametrize('text', [
    'I kiss your cheek and pat your head',
    'I caress your forearm then tug your tail',
    'I massage your shoulder; I boop your nose',
])
def test_new_compounds_blocked_before_model(text):
    assert unsupported_composite_gesture(text)


@pytest.mark.parametrize('text', [
    'Would I kiss your cheek and pat your head?',
    '"I caress your tail and kiss your nose"',
    'I do not kiss your cheek and pat your head',
])
def test_discussion_does_not_trigger_guard(text):
    assert not unsupported_composite_gesture(text)


def test_new_verbs_obey_persisted_stop_and_replay(tmp_path, engine):
    ledger = InteractionLedger(tmp_path / 'isolated.db')
    ledger.control(session_id='s1', message_id='stop-1',
                   content='Sofía, stop interactions', occurred_at=NOW)
    blocked, fresh = ledger.process_text(
        engine=engine, content='I kiss your left cheek', message_id='blocked',
        session_id='s1', occurred_at=NOW)
    assert fresh and blocked is not None and blocked.status == 'denied'
    assert ledger.accepted('blocked') is None
    ledger.control(session_id='s1', message_id='resume-1',
                   content='Sofía, resume interactions', occurred_at=NOW)
    replay, fresh = ledger.process_text(
        engine=engine, content='I kiss your left cheek', message_id='blocked',
        session_id='s1', occurred_at=NOW)
    assert not fresh and replay is not None and replay.status == 'acknowledged'
    accepted, fresh = ledger.process_text(
        engine=engine, content='I kiss your left cheek', message_id='new',
        session_id='s1', occurred_at=NOW)
    assert fresh and accepted is not None and accepted.status == 'accepted'
    assert ledger.accepted('new') == ('s1', 'left-cheek', 'kiss')
