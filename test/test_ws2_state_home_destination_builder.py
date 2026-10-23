"""Deferred Settings > Storage destination construction contracts.

This is a read-only helper: no directories are created, no migrations
run and no tests/CI are invoked during source authoring.
"""
import pytest

from sofia.platform.ops.state_mobility import (
    inspect_state_relocation, proposed_state_home_from_parent,
)


def test_valid_absent_child_is_not_created_by_settings_preview(tmp_path):
    child = proposed_state_home_from_parent(tmp_path, "Sofia")
    assert child == tmp_path / "Sofia"
    assert not child.exists()


@pytest.mark.parametrize("name", (
    "", ".", "..", "../escape", "nested/path", r"nested\path",
    "CON", "con.json", "nul", "COM1", "LPT9.txt",
    ".hidden", "trailing.", "trailing ", "name\0bad", "💾",
    "a" * 65,
))
def test_invalid_folder_names_never_escape_parent(tmp_path, name):
    with pytest.raises(ValueError):
        proposed_state_home_from_parent(tmp_path, name)


def test_existing_empty_directory_is_not_silently_reused(tmp_path):
    home = tmp_path / "Sofia"
    home.mkdir()
    with pytest.raises(FileExistsError, match="must not already exist"):
        proposed_state_home_from_parent(tmp_path, "Sofia")
    assert home.is_dir()


def test_redirected_parent_cannot_approve_a_new_home(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    redirected = tmp_path / "redirect"
    try:
        redirected.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic link privilege unavailable on this host")
    with pytest.raises(PermissionError, match="unredirected"):
        proposed_state_home_from_parent(redirected, "Sofia")
    assert not (real / "Sofia").exists()


def test_unreadable_canonical_source_produces_a_blocker_not_a_crash(
    tmp_path, monkeypatch,
):
    """Read-only relocation inspection cannot bootstrap a missing/wrong DB."""
    from pathlib import Path
    from sofia.platform.ops import state_mobility

    original = tmp_path / "original" / "sofia.db"
    original.parent.mkdir()
    original.write_bytes(b"synthetic-only")
    destination = tmp_path / "new-absent-home"
    original_stat = Path.stat

    def unreadable_source(self, *args, **kwargs):
        if self == original:
            raise PermissionError("synthetic host lock")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", unreadable_source)
    monkeypatch.setattr(
        state_mobility, "_filesystem_kind", lambda _path: "local",
    )
    inspected = inspect_state_relocation(original, destination)
    assert inspected.source_database_exists is False
    assert inspected.source_bytes == 0
    assert "canonical_state_database_missing" in inspected.blockers
    assert inspected.ready_for_automatic_cutover is False
    assert not destination.exists()
