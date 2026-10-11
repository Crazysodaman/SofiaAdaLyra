"""Phase 02/03 canonical operator-stop failure semantics, unexecuted tests."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.safe.operator_stop import OperatorStopStore


def _canonical_db(tmp_path):
    path = tmp_path / "sofia.db"
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA user_version")
    return path


def test_missing_canonical_db_does_not_bootstrap_an_inactive_stop(tmp_path):
    path = tmp_path / "missing" / "sofia.db"
    with pytest.raises(FileNotFoundError):
        OperatorStopStore(path)
    assert not path.exists()
    assert not path.parent.exists()


def test_removed_state_fails_closed_on_stop_read_and_update(tmp_path):
    path = _canonical_db(tmp_path)
    store = OperatorStopStore(path)
    store.set(active=True, updated_by="Sparks", reason="operator intervention")
    path.unlink()
    with pytest.raises(FileNotFoundError):
        store.current()
    with pytest.raises(FileNotFoundError):
        store.set(active=False, updated_by="Sparks", reason="do not restore authority")
    assert not path.exists()


def test_missing_stop_row_cannot_report_success(tmp_path):
    path = _canonical_db(tmp_path)
    store = OperatorStopStore(path)
    with closing(sqlite3.connect(path)) as db:
        with db:
            db.execute("DELETE FROM safe_operator_stop")
    with pytest.raises(RuntimeError, match="missing"):
        store.set(
            active=True, updated_by="Sparks",
            reason="cannot invent durable receipt",
            at=datetime(2026, 10, 11, tzinfo=timezone.utc),
        )


def test_stop_state_persists_on_real_canonical_database(tmp_path):
    path = _canonical_db(tmp_path)
    store = OperatorStopStore(path)
    saved = store.set(
        active=True, updated_by="Sparks",
        reason="do not execute remote mutations",
    )
    assert saved.active
    assert OperatorStopStore(path).current() == saved
