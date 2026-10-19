from pathlib import Path

from test.conftest import _explicit_package_markers, _package_markers


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
        "pkg_safe",
    } == _package_markers(
        root / "test_waves3_5_cross_package_acceptance.py"
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
    neuro = tmp_path / "test_neuro_package_grouping_fixture.py"
    neuro.write_text(
        "from sofia.neuro import NeuroRuntime\n",
        encoding="utf-8",
    )
    assert "pkg_core" in _explicit_package_markers(neuro)

def test_mentor_and_live2d_have_explicit_package_owners() -> None:
    root = Path(__file__).parent
    assert {"pkg_avatar", "pkg_dev", "pkg_integrate"}.issubset(
        _explicit_package_markers(root / "test_live2d_recovery.py")
    )
    mentor_tests = sorted(root.glob("test_mentor_*.py"))
    assert mentor_tests, "MENTOR package tests must stay discoverable"
    for path in mentor_tests:
        assert {"pkg_verify", "pkg_safe"}.issubset(
            _explicit_package_markers(path)
        ), path.name


def test_an_unmapped_test_does_not_gain_explicit_ownership(tmp_path: Path) -> None:
    probe = tmp_path / "test_unowned_feature.py"
    probe.write_text("def test_example(): pass\n", encoding="utf-8")
    assert _explicit_package_markers(probe) == frozenset()
    # The compatibility fallback must not masquerade as an explicit owner.
    assert _package_markers(probe) == frozenset({"pkg_core"})

