"""Deferred backup retention safety for redirected roots and archive children.

All directories are synthetic. No production archive is deleted, and the
coding workstream does not execute this test file.
"""
from pathlib import Path
import pytest

from sofia.ops.backup import BackupError, rotate_backups


def _backup(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(parents=True)
    (path / "manifest.json").write_text("{}", encoding="utf-8")
    return path


def _link_or_skip(link, dest, *, directory=False):
    try:
        link.symlink_to(dest, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("OS does not permit symbolic links")


def test_retention_denies_symlinked_root_and_preserves_external_archives(tmp_path):
    external = tmp_path / "external-archive-root"
    external.mkdir()
    protected = _backup(external, "20260101-old")
    _backup(external, "20260103-new")
    redirected = tmp_path / "retention-redirect"
    _link_or_skip(redirected, external, directory=True)

    with pytest.raises(BackupError, match="symbolic link or junction"):
        rotate_backups(redirected, keep=1)
    assert protected.is_dir()
    assert (external / "20260103-new").is_dir()


def test_retention_denies_redirected_child_even_if_marked_as_archive(tmp_path):
    root = tmp_path / "backup-root"
    root.mkdir()
    external = tmp_path / "unrelated-owner-data"
    external.mkdir()
    (external / "manifest.json").write_text("{}", encoding="utf-8")
    (external / "irrecoverable-identity").write_bytes(b"preserve")
    _backup(root, "20260104-new")
    _link_or_skip(root / "20260101-old", external, directory=True)

    with pytest.raises(BackupError, match="symbolic link or junction"):
        rotate_backups(root, keep=1)
    assert (external / "irrecoverable-identity").read_bytes() == b"preserve"
    assert (root / "20260104-new").exists()


def test_retention_preflights_entire_expired_generation_before_deleting_any(tmp_path):
    root = tmp_path / "backup-root"
    root.mkdir()
    oldest = _backup(root, "20260101-oldest")
    next_oldest = _backup(root, "20260102-older")
    current = _backup(root, "20260103-current")
    unrelated = tmp_path / "outside-payload"
    unrelated.write_bytes(b"do-not-touch")
    _link_or_skip(next_oldest / "payload-link", unrelated)

    with pytest.raises(BackupError, match="symbolic link or junction"):
        rotate_backups(root, keep=1)
    assert oldest.exists()
    assert next_oldest.exists()
    assert current.exists()
    assert unrelated.read_bytes() == b"do-not-touch"


def test_safe_directories_still_rotate_by_name_without_following_links(tmp_path):
    root = tmp_path / "backup-root"
    root.mkdir()
    oldest = _backup(root, "20260101-oldest")
    newer = _backup(root, "20260102-older")
    current = _backup(root, "20260103-current")
    removed = rotate_backups(root, keep=1)
    assert removed == (newer, oldest)
    assert current.exists()
    assert not oldest.exists()
    assert not newer.exists()
