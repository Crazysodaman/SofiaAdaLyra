"""Deferred Settings > Storage destination construction contracts.

This is a read-only helper: no directories are created, no migrations
run and no tests/CI are invoked during source authoring.
"""
import pytest

from sofia.ops.state_mobility import (
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
