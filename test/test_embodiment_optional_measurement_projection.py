from pathlib import Path

from sofia.cognition.self_state import AuthoritativeSelfState
from sofia.embodiment.store import EmbodimentStore


SEED = Path(__file__).resolve().parents[1] / "src/sofia/embodiment/avatar.json"


def test_unknown_dimensions_are_truthful_and_private_anatomy_is_excluded():
    embodiment = EmbodimentStore(SEED).load()
    projection = AuthoritativeSelfState(
        core_state=None, embodiment=embodiment, operational_state=None,
    ).serialize()
    assert "- height: 67 in" in projection
    assert "- neck_circumference: UNKNOWN (not measured)" in projection
    assert "- fox_tail_length: UNKNOWN (not measured)" in projection
    assert "- neck_circumference: None" not in projection
    assert "nipple_color" not in projection
    assert "vulva_color" not in projection
    assert "anus_color" not in projection
