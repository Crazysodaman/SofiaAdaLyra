"""Deferred Phase 03 foreign-key recovery gate using isolated SQLite fixtures.

No tests were executed when this regression source was authored.
"""
import sqlite3

import pytest

from sofia.ops.backup import BackupCipher, BackupEngine, BackupError
from test.test_ops_backup_restore import make_state, make_erasure_journal


def test_authenticated_backup_with_orphaned_foreign_key_cannot_be_published(
    tmp_path, monkeypatch,
):
    original = make_state(tmp_path)
    with sqlite3.connect(original) as db:
        db.executescript(
            """
            CREATE TABLE original_owner (id INTEGER PRIMARY KEY);
            CREATE TABLE original_event (
                id INTEGER PRIMARY KEY,
                owner_id INTEGER NOT NULL REFERENCES original_owner(id)
            );
            INSERT INTO original_event (id, owner_id) VALUES (1, 999);
            """
        )
        # SQLite file integrity is valid although this foreign key is broken.
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.execute("PRAGMA foreign_key_check").fetchone() is not None

    engine = BackupEngine(BackupCipher(b"k" * 32))
    backup, _evidence = engine.create(
        state_path=original,
        destination_root=tmp_path / "encrypted",
        source_host_id="venus",
        failure_domain="separate-fixture",
    )
    monkeypatch.setattr(
        "sofia.ops.backup.verify_production_component_schemas",
        lambda _path: None,
    )
    destination = tmp_path / "restored" / "sofia.db"
    with pytest.raises(BackupError, match="foreign_key_check"):
        engine.restore(
            backup_dir=backup,
            target_state_path=destination,
            verifier="offline-fixture-only",
            erasure_journal=make_erasure_journal(tmp_path),
        )
    assert not destination.exists()
    assert not (destination.parent / "protected" / "identity.json").exists()
    assert engine.verify(backup).source_host_id == "venus"
