"""Release source staging must preserve *Git object* bytes on Windows.

Does not invoke release promotion or modify production data.
"""
from pathlib import Path
import subprocess

import pytest

from sofia.verify.stage_release_source import stage_reviewed_git_tree


def git(root: Path, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, check=True,
    ).stdout


def sample_checkout(tmp_path: Path) -> Path:
    repo = tmp_path / "checkout"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "release-fixture@example.invalid")
    git(repo, "config", "user.name", "Release fixture")
    git(repo, "config", "core.autocrlf", "true")
    # The index normalizes only Git's own configured source representation.
    (repo / "source.txt").write_bytes(b"first\r\nsecond\r\n")
    (repo / "binary.dat").write_bytes(bytes([0, 255, 13, 10, 128, 129]))
    git(repo, "add", "--", ".")
    git(repo, "commit", "-qm", "tiny reviewed source")
    return repo


def test_stage_raw_git_bytes_not_windows_worktree_bytes(tmp_path):
    repo = sample_checkout(tmp_path)
    target = tmp_path / "external-stage"
    count = stage_reviewed_git_tree(repo, target)
    assert count == 2
    tracked = git(repo, "show", "HEAD:source.txt")
    assert tracked == b"first\nsecond\n"
    assert (target / "source.txt").read_bytes() == tracked
    assert (target / "binary.dat").read_bytes() == git(
        repo, "show", "HEAD:binary.dat",
    )
    # An altered editable checkout must never become the wheel source.
    (repo / "source.txt").write_bytes(b"malicious checkout modification\n")
    second = tmp_path / "independently-reviewed-stage"
    assert stage_reviewed_git_tree(repo, second) == count
    assert (second / "source.txt").read_bytes() == tracked


def test_stage_refuses_nonempty_or_checkout_parent_target(tmp_path):
    repo = sample_checkout(tmp_path)
    with pytest.raises(ValueError, match="outside checkout"):
        stage_reviewed_git_tree(repo, repo / "stage")
    target = tmp_path / "existing"
    target.mkdir()
    (target / "old.py").write_text("not source", encoding="utf-8")
    with pytest.raises(ValueError, match="empty ordinary directory"):
        stage_reviewed_git_tree(repo, target)


def test_stage_can_never_stage_unreviewed_symlink(tmp_path):
    repo = sample_checkout(tmp_path)
    linked = repo / "redirect"
    try:
        linked.symlink_to(repo / "source.txt")
    except (OSError, NotImplementedError):
        pytest.skip("OS does not allow symlinks for test user")
    git(repo, "add", "redirect")
    git(repo, "commit", "-qm", "tracked redirect")
    with pytest.raises(ValueError, match="nonregular Git tree object"):
        stage_reviewed_git_tree(repo, tmp_path / "outside")
