"""Deferred regression: restored bytes never follow a predictable temp alias.

No host state, real backup pruning, pairing or live filesystem touched.
"""
import sys

import pytest

import sofia.platform.ops.backup as backup_module
from sofia.platform.ops.backup import BackupCipher, BackupEngine
from test.test_ops_backup_restore import make_state, make_erasure_journal


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="fixture symlink creation")
def test_restore_does_not_follow_preexisting_predictable_temp_symlink(
    tmp_path, monkeypatch,
):
    state = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    archive, _ = engine.create(
        state_path=state,
        destination_root=tmp_path / "encrypted",
        source_host_id="venus",
        failure_domain="offline-fixture",
    )
    deletion_journal = make_erasure_journal(tmp_path)
    monkeypatch.setattr(
        backup_module, "verify_production_component_schemas",
        lambda _path: None,
    )

    root = tmp_path / "recovered"
    root.mkdir()
    original_external = tmp_path / "outside-not-approved"
    original_external.write_bytes(b"do-not-overwrite-this-host-file")
    predictable = root / ".sofia.db.restore"
    predictable.symlink_to(original_external)

    target = root / "sofia.db"
    verified = engine.restore(
        backup_dir=archive,
        target_state_path=target,
        verifier="offline-fixture-review",
        erasure_journal=deletion_journal,
    )

    assert verified.succeeded is True
    assert target.is_file()
    assert target.read_bytes().startswith(b"SQLite format 3")
    assert predictable.is_symlink()
    assert original_external.read_bytes() == b"do-not-overwrite-this-host-file"
