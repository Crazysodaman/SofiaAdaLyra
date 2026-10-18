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


def test_preview_player_help_does_not_need_tk_or_staged_art():
    """Smoke test the command startup without launching a desktop window."""
    import pytest
    from sofia.avatar.vtuber_review_player import main
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_review_player_identifies_specific_missing_batch_path(tmp_path):
    from sofia.avatar.vtuber_review_player import review_directory_status

    base = tmp_path / "Private-Source" / "Reviewed-Candidates"
    foundation = base / "Batch09-ModularFoundation-v3"
    features = base / "Batch10_11_IndependentEyesBrows-v1"
    mouths = base / "Batch12_13_MouthsVisemes-v1"
    foundation.mkdir(parents=True)
    features.mkdir(parents=True)
    (foundation / "manifest.json").write_text("{}")
    (features / "manifest.json").write_text("{}")

    rows = review_directory_status(
        foundation=foundation, features=features, mouths=mouths,
    )
    assert [item["status"] for item in rows] == [
        "ok", "ok", "directory does not exist (package not staged or wrong path)",
    ]
    assert "Batch 12/13" in rows[2]["batch"]
    assert rows[2]["path"] == str(mouths)


def test_preview_check_paths_only_diagnoses_without_starting_tk(tmp_path, capsys):
    from sofia.avatar.vtuber_review_player import main
    import json

    paths = [tmp_path / label for label in ("Batch09", "Batch1011", "Batch1213")]
    for path in paths:
        path.mkdir()
        (path / "manifest.json").write_text("{}")
    argv = [
        "--foundation-root", str(paths[0]),
        "--features-root", str(paths[1]),
        "--mouths-root", str(paths[2]), "--check-paths",
    ]
    assert main(argv) == 0
    assert [row["status"] for row in json.loads(capsys.readouterr().out)] == [
        "ok", "ok", "ok",
    ]
    (paths[2] / "manifest.json").unlink()
    assert main(argv) == 2
    assert json.loads(capsys.readouterr().out)[2]["status"].startswith("manifest.json missing")
