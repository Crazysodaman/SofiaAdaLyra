from pathlib import Path

from conftest import _explicit_package_markers, _package_markers


def test_every_test_file_has_package_ownership() -> None:
    root = Path(__file__).parent
    files = tuple(sorted(root.glob("test_*.py")))
    assert files
    missing = [
        path.name
        for path in files
        if not _explicit_package_markers(path)
    ]
    assert missing == []


def test_representative_cross_package_ownership(tmp_path: Path) -> None:
    root = Path(__file__).parent
    assert {
        "pkg_ops",
        "pkg_integrate",
        "pkg_safe",
    }.issubset(
        _package_markers(
            root / "test_waves3_5_cross_package_acceptance.py"
        )
    )
    assert {
        "pkg_ui",
        "pkg_social",
        "pkg_net",
    }.issubset(
        _package_markers(root / "test_discord_bridge.py")
    )
    habit = tmp_path / "test_habit_package_grouping_fixture.py"
    habit.write_text(
        "from sofia.habits import HabitObservationStore\n",
        encoding="utf-8",
    )
    assert "pkg_habit" in _package_markers(habit)
    emotion = tmp_path / "test_affection_package_grouping_fixture.py"
    emotion.write_text(
        "from sofia.emotion.journal import EmotionalJournal\n",
        encoding="utf-8",
    )
    assert "pkg_core" in _explicit_package_markers(emotion)
