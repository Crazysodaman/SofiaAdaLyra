"""Synthetic pointer semantics are not real avatar clicks or physical touch."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.embodiment.store import AvatarStore
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.registry import CATALOG_VERSION

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'


def test_text_and_synthetic_expanded_verbs_share_semantics():
    engine = NaturalInteractionEngine(AvatarStore(AVATAR).load())
    text = engine.from_text(content='I kiss your left cheek', message_id='m2',
                            session_id='s1', occurred_at=NOW)
    hit = engine.from_lab_pointer(fixture_id='synthetic', session_id='s1',
                                  region_id='left-cheek', gesture='kiss', occurred_at=NOW)
    assert text is not None and text.status == hit.status == 'accepted'
    assert text.event.semantics == hit.event.semantics
    assert hit.event.registry_version == CATALOG_VERSION


def test_unsupported_or_stopped_synthetic_hit_never_becomes_contact():
    engine = NaturalInteractionEngine(AvatarStore(AVATAR).load())
    with pytest.raises(ValueError):
        engine.from_lab_pointer(fixture_id='s', session_id='s1', region_id='nose',
                                gesture='unsupported-action', occurred_at=NOW)
    denied = engine.from_lab_pointer(fixture_id='s', session_id='s1', region_id='nose',
                                     gesture='kiss', occurred_at=NOW, stopped=True)
    assert denied.status == 'denied' and denied.emotion_options == ()
