"""Deferred encrypted archive durability and absence-only publication.

All source files, keys, encrypted bundles, and target homes are synthetic
tmp_path fixtures. No CI, tests, live backup or host change is executed.
"""
import errno
import os
import sys

import pytest

import sofia.ops.backup as backup
from sofia.ops.backup import (
    BackupCipher, BackupEngine, BackupPublicationUncertain,
)
from test.test_ops_backup_restore import make_state


def _archive_setup(tmp_path):
    state = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    destination = tmp_path / "backups"
    return state, engine, destination


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux fsync")
def test_verified_archive_is_durable_before_absence_only_publication(
    tmp_path, monkeypatch,
):
    state, engine, destination = _archive_setup(tmp_path)
    original = backup._publish_backup_archive_without_replacing
    observed = []

    def check_before_rename(staging, final):
        assert (staging / "manifest.json").is_file()
        assert (staging / "manifest.hmac").is_file()
        assert (staging / "payload").is_dir()
        observed.append((staging, final))
        return original(staging, final)

    monkeypatch.setattr(
        backup, "_publish_backup_archive_without_replacing",
        check_before_rename,
    )
    bundle, receipt = engine.create(
        state_path=state, destination_root=destination,
        source_host_id="venus", failure_domain="separate-fixture",
    )
    assert observed and observed[0][1] == bundle
    assert bundle.is_dir() and not observed[0][0].exists()
    assert engine.verify(bundle).backup_id == receipt.backup_id


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux renameat2")
def test_atomic_publish_refuses_destination_created_after_preflight(
    tmp_path, monkeypatch,
):
    import ctypes

    staging = tmp_path / ".staging-fixture"
    staging.mkdir()
    (staging / "manifest.json").write_bytes(b"synthetic")
    final = tmp_path / "other-owner-backup"

    def fake_renameat2(_srcdir, _src, _dstdir, _dst, _flags):
        final.mkdir()
        (final / "operator-owned").write_bytes(b"must-survive")
        ctypes.set_errno(errno.EEXIST)
        return -1

    class FakeLibc:
        renameat2 = staticmethod(fake_renameat2)

    monkeypatch.setattr(ctypes, "CDLL", lambda *_a, **_kw: FakeLibc())
    with pytest.raises(FileExistsError, match="appeared during publish"):
        backup._publish_backup_archive_without_replacing(staging, final)

    assert (final / "operator-owned").read_bytes() == b"must-survive"
    assert (staging / "manifest.json").is_file()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux fsync")
def test_post_rename_archive_parent_fsync_is_explicitly_uncertain(
    tmp_path, monkeypatch,
):
    state, engine, destination = _archive_setup(tmp_path)
    actual = backup._fsync_restored_linux_directories
    published = []

    def fail_parent_barrier(directories):
        # Pre-rename preparation includes the internal staging payload
        # directory, but post-rename durability flushes only final.parent.
        if directories == {destination}:
            published.append(True)
            raise OSError("synthetic parent entry persistence failure")
        return actual(directories)

    monkeypatch.setattr(
        backup, "_fsync_restored_linux_directories", fail_parent_barrier,
    )
    with pytest.raises(BackupPublicationUncertain, match="uncertain"):
        engine.create(
            state_path=state, destination_root=destination,
            source_host_id="venus", failure_domain="separate-fixture",
        )
    assert published == [True]
    archives = [
        entry for entry in destination.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    ]
    assert len(archives) == 1
    assert engine.verify(archives[0]).entries


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux fsync")
def test_pre_rename_file_fsync_failure_never_publishes_backup(
    tmp_path, monkeypatch,
):
    state, engine, destination = _archive_setup(tmp_path)
    original_fsync = os.fsync

    def refuse_encrypted_payload(descriptor):
        current = os.readlink(f"/proc/self/fd/{descriptor}")
        if current.endswith(".bin") and "payload" in current:
            raise OSError("synthetic encrypted payload flush denied")
        return original_fsync(descriptor)

    monkeypatch.setattr(backup.os, "fsync", refuse_encrypted_payload)
    with pytest.raises(OSError, match="payload flush denied"):
        engine.create(
            state_path=state, destination_root=destination,
            source_host_id="venus", failure_domain="separate-fixture",
        )
    assert not [
        item for item in destination.iterdir()
        if item.is_dir() and not item.name.startswith(".")
    ]
