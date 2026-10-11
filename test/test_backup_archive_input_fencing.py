"""Deferred backup source/archive path identity safety regression contracts.

Runs only against isolated fixture files, never production state/backup
paths. Symlinks may require developer mode on Windows and are skipped there.
"""
from pathlib import Path

import pytest

from sofia.config.defaults import production_storage_layout
from sofia.ops.backup import BackupCipher, BackupEngine, BackupError
from test.test_ops_backup_restore import NOW, make_state


def _link_or_skip(link: Path, target: Path, *, directory: bool = False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("operating system does not permit symlink fixtures")


def _engine():
    return BackupEngine(BackupCipher(b"k" * 32))


def _archive(tmp_path):
    engine = _engine()
    state = make_state(tmp_path)
    archive, _ = engine.create(
        state_path=state, destination_root=tmp_path / "backups",
        source_host_id="synthetic-host",
        failure_domain="isolated-fixture-disk",
        now=NOW,
    )
    return engine, archive


def test_create_rejects_redirected_protected_root_before_backup_published(tmp_path):
    state = make_state(tmp_path)
    protected = production_storage_layout(state_path=state).protected_root
    outside = tmp_path / "outside"
    protected.rename(outside)
    _link_or_skip(protected, outside, directory=True)
    with pytest.raises(BackupError, match="symbolic link or junction"):
        _engine().create(
            state_path=state, destination_root=tmp_path / "backups",
            source_host_id="fixture",
            failure_domain="isolated-disk",
            now=NOW,
        )
    assert not any(
        p.is_dir() and (p / "manifest.json").exists()
        for p in (tmp_path / "backups").glob("*")
    )


def test_create_refuses_external_symlinked_personality_file(tmp_path):
    state = make_state(tmp_path)
    original = production_storage_layout(state_path=state).personality_path
    source = tmp_path / "unrelated-secret.txt"
    source.write_text("must stay outside archival scope", encoding="utf-8")
    original.unlink()
    _link_or_skip(original, source)
    with pytest.raises(BackupError, match="symbolic link or junction"):
        _engine().create(
            state_path=state, destination_root=tmp_path / "backups",
            source_host_id="fixture", failure_domain="isolated-disk", now=NOW,
        )


def test_verify_refuses_redirected_encrypted_payload_even_with_valid_cipher(tmp_path):
    engine, archive = _archive(tmp_path)
    payload = next((archive / "payload").glob("*.bin"))
    copy = tmp_path / "payload-copy"
    copy.write_bytes(payload.read_bytes())
    payload.unlink()
    _link_or_skip(payload, copy)
    with pytest.raises(BackupError, match="symbolic link or junction"):
        engine.verify(archive)


def test_verify_refuses_redirected_archive_root(tmp_path):
    engine, archive = _archive(tmp_path)
    redirected = tmp_path / "archive-link"
    _link_or_skip(redirected, archive, directory=True)
    with pytest.raises(BackupError, match="symbolic link or junction"):
        engine.verify(redirected)


def test_normal_isolated_signed_archive_still_verifies(tmp_path):
    engine, archive = _archive(tmp_path)
    manifest = engine.verify(archive)
    assert any(x.logical_path == "sofia.db" for x in manifest.entries)
