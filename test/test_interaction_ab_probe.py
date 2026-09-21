"""A/B comparison request construction; no Ollama call, DB, or live session."""
from pathlib import Path

import pytest

from sofia.cognition.model import CognitiveRole
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.store import AvatarStore
from sofia.identity.store import IdentityStore
from sofia.interaction.ab_probe import build_pair
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
    if case == 'offer':
        assert '"modality": "offered"' in assembled.messages[1].content
        assert '"actions_executed": false' in assembled.messages[1].content
    if case == 'hypothetical':
        assert '"actions_executed": false' in assembled.messages[1].content
    assert not (tmp_path / 'sofia.db').exists()
