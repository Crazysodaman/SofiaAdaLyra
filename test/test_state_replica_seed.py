"""Production State Plane replica publication and SQLite handle ownership."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

import pytest

from sofia.state.factory import _seed_sqlite
from sofia.state.sqlite_access import SQLiteAccess, _ObservedConnection


def _primary(path: Path) -> None:
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE evidence (value TEXT PRIMARY KEY)")
        db.execute("INSERT INTO evidence VALUES ('retained')")
        db.commit()


def test_replica_seed_publishes_verified_consistent_sqlite(tmp_path):
    primary = tmp_path / "primary.db"
    replica = tmp_path / "other" / "sofia.db"
    _primary(primary)
    _seed_sqlite(primary, replica)
    with closing(sqlite3.connect(f"{replica.as_uri()}?mode=ro", uri=True)) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT value FROM evidence").fetchall() == [("retained",)]
    assert not list(replica.parent.glob(".sofia-replica-seed-*"))


def test_existing_replica_is_never_overwritten(tmp_path):
    primary = tmp_path / "primary.db"
    replica = tmp_path / "replica.db"
    _primary(primary)
    replica.write_bytes(b"existing-data")
    _seed_sqlite(primary, replica)
    assert replica.read_bytes() == b"existing-data"


def test_invalid_source_does_not_publish_or_leave_staged_db(tmp_path):
    source = tmp_path / "not-a-database.db"
    source.write_bytes(b"invalid SQLite")
    replica = tmp_path / "replica.db"
    with pytest.raises(sqlite3.DatabaseError):
        _seed_sqlite(source, replica)
    assert not replica.exists()
    assert not list(tmp_path.glob(".sofia-replica-seed-*"))


def test_concurrent_publisher_is_not_replaced(tmp_path, monkeypatch):
    primary = tmp_path / "primary.db"
    replica = tmp_path / "replica.db"
    _primary(primary)

    def competing_publish(src, dst):
        assert Path(src).is_file()
        Path(dst).write_bytes(b"other-writer")
        raise FileExistsError("replica already published")

    monkeypatch.setattr("sofia.state.factory.os.link", competing_publish)
    with pytest.raises(FileExistsError):
        _seed_sqlite(primary, replica)
    assert replica.read_bytes() == b"other-writer"
    assert not list(tmp_path.glob(".sofia-replica-seed-*"))


def test_failed_sqlite_initialization_releases_reader_and_handle(
    tmp_path, monkeypatch,
):
    access = SQLiteAccess(tmp_path / "state.db", max_readers=1)
    original_execute = _ObservedConnection.execute

    class SetupFailure(Exception):
        pass

    def fail_pragma(self, sql, parameters=(), /):
        if "PRAGMA foreign_keys" in sql:
            raise SetupFailure("simulated setup failure")
        return original_execute(self, sql, parameters)

    monkeypatch.setattr(_ObservedConnection, "execute", fail_pragma)
    with pytest.raises(SetupFailure):
        access.connect()

    # The closed failed connection must not retain a reader slot or Windows
    # handle. The next connection can open without waiting for a leaked slot.
    monkeypatch.setattr(_ObservedConnection, "execute", original_execute)
    with closing(access.connect()) as db:
        assert db.execute("SELECT 1").fetchone() == (1,)
