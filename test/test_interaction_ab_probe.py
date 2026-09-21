"""A/B comparison request construction; no Ollama call, DB, or live session."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.cognition.model import CognitiveRole
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.store import AvatarStore
from sofia.identity.store import IdentityStore
from sofia.interaction.ab_probe import build_pair
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.personality.store import PersonalityStore

ROOT = Path(__file__).resolve().parents[1] / 'src' / 'sofia'
CASES = (
    ('ear', '*pats your ear*'),
    ('offer', 'I ask to hug you'),
    ('hypothetical', 'What happens if I pat your tail or rub your chest?'),
    ('technical', "I'm troubleshooting a Windows service that won't start. How would you diagnose it?"),
)


@pytest.mark.parametrize('case,text', CASES)
def test_probe_constructs_static_context_with_identical_synthetic_user_input(case, text, tmp_path):
    minimal, assembled = build_pair(
        case=case, text=text,
        identity=IdentityStore(ROOT / 'identity' / 'identity.json').load(),
        personality=PersonalityStore(ROOT / 'personality' / 'personality.json').load(),
        constitution=ConstitutionStore(ROOT / 'constitution' / 'constitution.md').load(),
        embodiment=AvatarStore(ROOT / 'data' / 'avatar.json').load(),
    )
    assert minimal.messages[-1].role is assembled.messages[-1].role is CognitiveRole.USER
    assert minimal.messages[-1].content == assembled.messages[-1].content == text
    assert minimal.messages[0].role is assembled.messages[0].role is CognitiveRole.SYSTEM
    assert len(assembled.messages[0].content) > len(minimal.messages[0].content)
    if case == 'ear':
        # An unspecified ear is not silently reinterpreted as left or right.
        assert '"policy_status": "clarify"' in assembled.messages[1].content
        assert '"region_id": null' in assembled.messages[1].content
        assert '"gesture": null' in assembled.messages[1].content
    if case == 'offer':
        assert '"modality": "offered"' in assembled.messages[1].content
        assert '"actions_executed": false' in assembled.messages[1].content
    if case == 'hypothetical':
        assert '"actions_executed": false' in assembled.messages[1].content
    assert not (tmp_path / 'sofia.db').exists()


def test_canonical_engine_requires_a_side_for_singular_ear():
    engine = NaturalInteractionEngine(AvatarStore(ROOT / 'data' / 'avatar.json').load())
    ambiguous = engine.from_text(
        content='*pats your ear*', message_id='ear-1',
        session_id='synthetic-session', occurred_at=datetime.now(timezone.utc),
    )
    specific = engine.from_text(
        content='*pats your left ear*', message_id='ear-2',
        session_id='synthetic-session', occurred_at=datetime.now(timezone.utc),
    )
    assert ambiguous is not None and ambiguous.status == 'clarify'
    assert ambiguous.event.region_id is None
    assert specific is not None and specific.status == 'accepted'
    assert specific.event.region_id == 'left-ear'
