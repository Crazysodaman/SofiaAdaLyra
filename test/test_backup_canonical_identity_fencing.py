"""Canonical-state backup source fencing, authored for deferred verification.

No tests or CI are executed in the V18 production-coding workstream.
"""
from contextlib import closing
import os
import sqlite3

import pytest

from sofia.ops.backup import BackupCipher, BackupEngine
from sofia.state.canonical_sqlite import CanonicalStateUnavailable


@pytest.fixture
def engine():
    return BackupEngine(BackupCipher(b"k" * 32))


def _state(path):
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE durable_event (id INTEGER PRIMARY KEY)")
        db.execute("INSERT INTO durable_event VALUES (1)")
        db.commit()


@pytest.mark.parametrize("failure", ("replaced", "unavailable"))
def test_backup_does_not_adopt_new_or_missing_writer_during_snapshot(
    tmp_path, monkeypatch, engine, failure,
):
    state = tmp_path / "sofia.db"
    _state(state)
    replacement = tmp_path / "replacement.db"
    _state(replacement)
    original_snapshot = BackupEngine._sqlite_snapshot

    def lose_source(source, target, *, guard=None):
        assert guard is not None  # pinned before staging/backup work
        if failure == "replaced":
            os.replace(replacement, source)
        else:
            source.unlink()
        return original_snapshot(source, target, guard=guard)

    monkeypatch.setattr(BackupEngine, "_sqlite_snapshot", staticmethod(lose_source))
    backup_root = tmp_path / "backups"
    with pytest.raises(CanonicalStateUnavailable):
        engine.create(
            state_path=state,
            destination_root=backup_root,
            source_host_id="canonical-host-unspecified",
            failure_domain="fixture-only",
        )
    assert backup_root.is_dir()
    assert not list(backup_root.iterdir())


def test_snapshot_refuses_missing_source_without_creating_new_sqlite(tmp_path):
    missing = tmp_path / "sofia.db"
    target = tmp_path / "snapshot.db"
    with pytest.raises(CanonicalStateUnavailable):
        BackupEngine._sqlite_snapshot(missing, target)
    assert not missing.exists()
    assert not target.exists()
