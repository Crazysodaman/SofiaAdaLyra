"""Pure request comparison tests; no Ollama inference or production database."""
from pathlib import Path
import json

import pytest

from sofia.cognition.model import CognitiveRole
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.store import AvatarStore
from sofia.identity.store import IdentityStore
from sofia.interaction.ab_probe import build_pair
from sofia.interaction.focused_probe import focused_variant
from sofia.personality.store import PersonalityStore

ROOT = Path(__file__).resolve().parents[1] / 'src' / 'sofia'


@pytest.mark.parametrize('case,text', (
    ('ear', '*pats your left ear*'),
    ('offer', 'I ask to hug you'),
))
def test_focused_comparison_preserves_everything_except_action_prose(case, text, tmp_path):
    _, original = build_pair(
        case=case, text=text,
        identity=IdentityStore(ROOT / 'identity' / 'identity.json').load(),
        personality=PersonalityStore(ROOT / 'personality' / 'personality.json').load(),
        constitution=ConstitutionStore(ROOT / 'constitution' / 'constitution.md').load(),
        embodiment=AvatarStore(ROOT / 'data' / 'avatar.json').load(),
    )
    focused = focused_variant(case=case, assembled=original)
    assert original.tools == focused.tools == ()
    assert len(original.messages) == len(focused.messages) == 3
    assert original.messages[0] == focused.messages[0]
    assert original.messages[-1] == focused.messages[-1]
    assert original.messages[-1].role is CognitiveRole.USER
    assert original.messages[-1].content == text
    assert focused.messages[1].role is CognitiveRole.SYSTEM
    assert focused.messages[1].content != original.messages[1].content
    assert len(focused.messages[1].content) < len(original.messages[1].content)
    assert json.loads(focused.messages[1].content.rsplit('\n', 1)[-1]) == json.loads(
        original.messages[1].content.rsplit('\n', 1)[-1])
    assert 'CONSTITUTION (bounded conversational projection)' in focused.messages[0].content
    assert not (tmp_path / 'sofia.db').exists()


def test_focused_comparison_rejects_unreviewed_case():
    with pytest.raises(ValueError, match='Unknown reviewed probe case'):
        focused_variant(case='unknown', assembled=None)
