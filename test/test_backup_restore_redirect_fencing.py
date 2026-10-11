"""Deferred signed backup restore destination symlink safety contracts."""
import pytest

from sofia.ops.backup import BackupCipher, BackupEngine, BackupError
from test.test_ops_backup_restore import NOW, make_state, make_erasure_journal


def _fixture_archive(tmp_path):
    state = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    archive, _ = engine.create(
        state_path=state, destination_root=tmp_path / "backups",
        source_host_id="isolated-fixture", failure_domain="separate-test-disk",
        now=NOW,
    )
    return engine, archive


def _link_or_skip(link, destination, *, directory=False):
    try:
        link.symlink_to(destination, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("OS denies symlink creation")


def test_restore_refuses_protected_redirect_before_any_writes(tmp_path):
    engine, archive = _fixture_archive(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    restore = tmp_path / "restored"
    restore.mkdir()
    _link_or_skip(restore / "protected", outside, directory=True)
    with pytest.raises(BackupError, match="symbolic link or junction"):
        engine.restore(
            backup_dir=archive, target_state_path=restore / "sofia.db",
            verifier="fixture", erasure_journal=make_erasure_journal(tmp_path),
        )
    assert not (restore / "sofia.db").exists()
    assert not any(outside.iterdir())


def test_restore_refuses_redirected_canonical_file_even_with_replace(tmp_path):
    engine, archive = _fixture_archive(tmp_path)
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"preserve-this-file")
    restore = tmp_path / "restored"
    restore.mkdir()
    _link_or_skip(restore / "sofia.db", outside)
    with pytest.raises(BackupError, match="symbolic link or junction"):
        engine.restore(
            backup_dir=archive, target_state_path=restore / "sofia.db",
            verifier="fixture", erasure_journal=make_erasure_journal(tmp_path), replace_existing=True,
        )
    assert outside.read_bytes() == b"preserve-this-file"


def test_restore_refuses_redirected_parent_directory(tmp_path):
    engine, archive = _fixture_archive(tmp_path)
    outside = tmp_path / "outside-home"
    outside.mkdir()
    redirected = tmp_path / "redirected-home"
    _link_or_skip(redirected, outside, directory=True)
    with pytest.raises(BackupError, match="symbolic link or junction"):
        engine.restore(
            backup_dir=archive, target_state_path=redirected / "sofia.db",
            verifier="fixture", erasure_journal=make_erasure_journal(tmp_path),
        )
    assert not any(outside.iterdir())
