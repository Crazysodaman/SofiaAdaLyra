from pathlib import Path

from conftest import _package_markers


def test_every_test_file_has_package_ownership() -> None:
    root = Path(__file__).parent
    files = tuple(sorted(root.glob("test_*.py")))
    assert files
    missing = [
        path.name
        for path in files
        if not _package_markers(path)
    ]
    assert missing == []


def test_representative_cross_package_ownership() -> None:
    root = Path(__file__).parent
    assert {
        "pkg_ops",
        "pkg_integrate",
        "pkg_safe",
    }.issubset(
        _package_markers(
            root / "test_dev_know_integrate_ops_cross_package.py"
        )
    )
    assert {
        "pkg_ui",
        "pkg_social",
        "pkg_net",
    }.issubset(
        _package_markers(root / "test_discord_bridge.py")
    )
    assert "pkg_habit" in _package_markers(
        root / "test_habit_package_grouping_fixture.py"
    )
