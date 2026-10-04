import sqlite3

import pytest

import sofia.integrations.sqlite as adapter_module
from sofia.integrations.sqlite import SQLiteReadAdapter


@pytest.mark.parametrize("operation", ["tables", "query", "integrity_check", "wal_checkpoint"])
def test_short_lived_database_handles_close(tmp_path, monkeypatch, operation):
    path = tmp_path / "state.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE sample (value INTEGER)")
    db.execute("INSERT INTO sample VALUES (7)")
    db.commit()
    db.close()
    connections = []
    connect = sqlite3.connect

    def tracked_connect(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(adapter_module.sqlite3, "connect", tracked_connect)
    adapter = SQLiteReadAdapter(path)
    if operation == "query":
        assert adapter.query("SELECT value FROM sample") == ({"value": 7},)
    elif operation == "tables":
        assert adapter.tables() == ("sample",)
    elif operation == "integrity_check":
        assert adapter.integrity_check() == ("ok",)
    else:
        assert len(adapter.wal_checkpoint()) == 3
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")


def test_failed_query_also_closes_handle(tmp_path, monkeypatch):
    path = tmp_path / "state.db"
    db = sqlite3.connect(path)
    db.close()
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    adapter = SQLiteReadAdapter(path)
    monkeypatch.setattr(adapter, "_connect_ro", lambda: connection)
    with pytest.raises(sqlite3.OperationalError):
        adapter.query("SELECT * FROM missing")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
