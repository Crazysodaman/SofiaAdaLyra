"""Anatomical cue IDs must not match arbitrary substrings."""
from datetime import datetime, timezone
from pathlib import Path

from sofia.embodiment.store import AvatarStore
from sofia.interaction.core import InteractionEngine

AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'
NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)


def test_forearm_never_receives_fox_ear_stage_directions():
    engine = InteractionEngine(AvatarStore(AVATAR).load())
    for region in ('left-forearm', 'right-forearm'):
        result = engine.from_lab_pointer(fixture_id='fixture', session_id='session',
                                         region_id=region, gesture='touch', occurred_at=NOW)
        assert result.status == 'accepted'
        assert not any('ear' in cue for cue in result.text_cues)
    ear = engine.from_lab_pointer(fixture_id='fixture-ear', session_id='session',
                                  region_id='left-ear', gesture='touch', occurred_at=NOW)
    assert ear.status == 'accepted'
    assert '*one ear flicks*' in ear.text_cues
