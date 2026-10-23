"""Deferred encrypted-backup confinement of temporary plaintext SQLite copies.

Isolated test fixtures only. Production encrypted archive roots must never
receive a temporary plaintext source SQLite snapshot, including during
backup creation before final publication. No test execution occurs here.
"""
import pytest

from sofia.platform.ops.backup import BackupCipher, BackupEngine
from test.test_ops_backup_restore import make_state


def _fixture(tmp_path):
    source = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    archive_root = tmp_path / "external-encrypted-backup-root"
    return source, engine, archive_root


def test_online_sqlite_snapshot_is_local_to_protected_source_not_archive_root(
    tmp_path, monkeypatch,
):
    source, engine, backup_root = _fixture(tmp_path)
    actual = engine._sqlite_snapshot
    observed = []

    def inspect_snapshot(original, target, **kwargs):
        assert target.parent.parent == source.parent
        assert target.parent.name.startswith(".sofia-cleartext-snapshot-")
        assert not str(target).startswith(str(backup_root))
        observed.append(target)
        return actual(original, target, **kwargs)

    monkeypatch.setattr(engine, "_sqlite_snapshot", inspect_snapshot)
    archive, receipt = engine.create(
        state_path=source, destination_root=backup_root,
        source_host_id="synthetic-venus",
        failure_domain="separate-protected-fixture",
    )

    assert len(observed) == 1
    assert not observed[0].exists()
    assert not observed[0].parent.exists()
    assert not (archive / "sofia.db.snapshot").exists()
    assert sorted(file.name for file in archive.iterdir()) == [
        "manifest.hmac", "manifest.json", "payload",
    ]
    assert all(item.suffix == ".bin" for item in (archive / "payload").iterdir())
    assert engine.verify(archive).backup_id == receipt.backup_id


def test_failed_encryption_cleans_source_local_cleartext_snapshot(
    tmp_path, monkeypatch,
):
    source, engine, backup_root = _fixture(tmp_path)

    def synthetic_encryption_failure(_plaintext, *, aad):
        raise RuntimeError("synthetic encryption failure")

    monkeypatch.setattr(engine.cipher, "encrypt", synthetic_encryption_failure)
    with pytest.raises(RuntimeError, match="synthetic encryption failure"):
        engine.create(
            state_path=source, destination_root=backup_root,
            source_host_id="synthetic-venus", failure_domain="offline",
        )

    assert not list(source.parent.glob(".sofia-cleartext-snapshot-*"))
    assert not list(backup_root.glob("*.snapshot"))
    assert not [
        folder for folder in backup_root.iterdir()
        if folder.is_dir() and not folder.name.startswith(".")
    ]


@pytest.mark.parametrize("surprise", ("raw-sqlite", "extra-directory", "stray-file"))
def test_verified_encrypted_archive_rejects_unlisted_content(
    tmp_path, surprise,
):
    from sofia.platform.ops.backup import BackupError

    source, engine, backup_root = _fixture(tmp_path)
    archive, _ = engine.create(
        state_path=source, destination_root=backup_root,
        source_host_id="synthetic-venus",
        failure_domain="independent-offline-fixture",
    )
    if surprise == "raw-sqlite":
        (archive / "sofia.db.snapshot").write_bytes(
            b"SQLite format 3\\x00synthetic-private-backup-bytes"
        )
    elif surprise == "extra-directory":
        other = archive / "hidden-plaintext"
        other.mkdir()
        (other / "candidate.txt").write_text("synthetic private original")
    else:
        (archive / "unexpected.log").write_text("synthetic recovery secret")

    with pytest.raises(BackupError, match="unlisted"):
        engine.verify(archive)
