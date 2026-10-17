"""The local avatar source-art player uses deterministic, bounded frame cues."""
from __future__ import annotations

from sofia.avatar.vtuber_review_player import preview_steps


def test_demo_blinks_winks_and_changes_visemes_without_fake_voice_receipts():
    frames = preview_steps()
    assert frames[0].expression == "neutral"
    expressions = [item.expression for item in frames]
    assert "blink" in expressions
    assert "left_wink" in expressions
    assert "right_wink" in expressions
    assert all(letter in expressions for letter in ("A", "E", "O", "M"))
    assert all(100 <= item.duration_ms <= 1000 for item in frames)
    assert len(expressions) > len(set(expressions))


def test_importing_player_does_not_start_tk_or_touch_runtime():
    import sofia.avatar.vtuber_review_player as module
    assert hasattr(module, "run_local_preview")
    assert not hasattr(module, "ACTIVE_RUNTIME")


def test_mouth_viseme_inventory_imports_and_covers_all_states():
    """Regression: a missing inner comprehension loop used to crash import."""
    from sofia.avatar.vtuber_mouth_viseme_review import (
        _ART_FILES, _EXPECTED, MOUTH_STATES, VISEME_STATES,
    )
    expected = (
        {f"layers/mouths/{state}.png" for state in MOUTH_STATES}
        | {f"layers/visemes/{state}.png" for state in VISEME_STATES}
    )
    assert len(expected) == 12
    assert _ART_FILES == expected
    assert expected <= _EXPECTED
