"""Deferred real encrypted-archive restore durability barrier regressions.

All state, encrypted backups and deletion journals are tmp_path fixtures.
No test execution, production restore, rotation or host change.
"""
import os
import sys

import pytest

import sofia.ops.backup as backup_module
from sofia.ops.backup import (
    BackupCipher, BackupEngine, RestorePublicationUncertain,
)
from test.test_ops_backup_restore import make_state, make_erasure_journal


def _archive(tmp_path):
    engine = BackupEngine(BackupCipher(b"k" * 32))
    original = make_state(tmp_path)
    bundle, _evidence = engine.create(
        state_path=original,
        destination_root=tmp_path / "encrypted",
        source_host_id="venus", failure_domain="offline-fixture",
    )
    return engine, bundle, make_erasure_journal(tmp_path)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux directory fsync")
def test_restore_flushes_temp_bytes_before_rename_and_directory_afterwards(
    tmp_path, monkeypatch,
):
    engine, bundle, journal = _archive(tmp_path)
    monkeypatch.setattr(
        backup_module, "verify_production_component_schemas",
        lambda _path: None,
    )
    target = tmp_path / "restored" / "sofia.db"
    original_fsync = os.fsync
    original_replace = os.replace
    observed = []

    def track_fsync(descriptor):
        observed.append(("sync", os.readlink(f"/proc/self/fd/{descriptor}")))
        return original_fsync(descriptor)

    def track_replace(src, dst):
        observed.append(("rename", str(dst)))
        return original_replace(src, dst)

    monkeypatch.setattr(backup_module.os, "fsync", track_fsync)
    monkeypatch.setattr(backup_module.os, "replace", track_replace)

    result = engine.restore(
        backup_dir=bundle, target_state_path=target,
        verifier="offline-test", erasure_journal=journal,
    )
    assert result.succeeded
    renames = [(i, path) for i, (kind, path) in enumerate(observed)
               if kind == "rename" and str(target.parent) in path]
    assert renames
    for index, destination in renames:
        # The secure restore temp is an exclusively created random file,
        # never a predictable preexisting ".restore" symlink alias.
        from pathlib import Path
        prefix = str(Path(destination).with_name(
            "." + Path(destination).name + ".restore-"
        ))
        assert any(
            kind == "sync" and path.startswith(prefix) and path.endswith(".tmp")
            for kind, path in observed[:index]
        )
    last_rename = max(index for index, _ in renames)
    assert any(
        kind == "sync" and path == str(target.parent)
        for kind, path in observed[last_rename + 1:]
    )


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux directory fsync")
def test_restore_refuses_rename_before_durable_temporary_file(
    tmp_path, monkeypatch,
):
    engine, bundle, journal = _archive(tmp_path)
    monkeypatch.setattr(
        backup_module, "verify_production_component_schemas",
        lambda _path: None,
    )
    original_fsync = os.fsync
    original_replace = os.replace
    published = []

    def failed_temp_fsync(descriptor):
        original_path = os.readlink(f"/proc/self/fd/{descriptor}")
        if ".restore-" in original_path and original_path.endswith(".tmp"):
            raise OSError("simulated crash durability failure")
        return original_fsync(descriptor)

    def tracked_replace(src, dst):
        published.append(str(dst))
        return original_replace(src, dst)

    monkeypatch.setattr(backup_module.os, "fsync", failed_temp_fsync)
    monkeypatch.setattr(backup_module.os, "replace", tracked_replace)

    with pytest.raises(OSError, match="simulated crash durability"):
        engine.restore(
            backup_dir=bundle, target_state_path=tmp_path / "restore" / "sofia.db",
            verifier="offline-test", erasure_journal=journal,
        )
    assert not published


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux directory fsync")
def test_restore_directory_sync_failure_never_returns_verified_success(
    tmp_path, monkeypatch,
):
    engine, bundle, journal = _archive(tmp_path)
    monkeypatch.setattr(
        backup_module, "verify_production_component_schemas",
        lambda _path: None,
    )

    def failed_parent_durability(_directories):
        raise OSError("synthetic parent sync unavailable")

    monkeypatch.setattr(
        backup_module, "_fsync_restored_linux_directories",
        failed_parent_durability,
    )
    target = tmp_path / "restore" / "sofia.db"
    with pytest.raises(RestorePublicationUncertain, match="uncertain"):
        engine.restore(
            backup_dir=bundle, target_state_path=target,
            verifier="offline-test", erasure_journal=journal,
        )
    assert target.is_file()  # Published bytes need explicit offline inspection.
