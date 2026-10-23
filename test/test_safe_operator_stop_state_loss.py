"""Phase 02/03 canonical operator-stop failure semantics, unexecuted tests."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import sqlite3

import pytest

from test.owner_auth_fixture import resume_with_signed_owner_proof

from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


def _canonical_db(tmp_path):
    return bootstrap_canonical_sqlite(tmp_path / "sofia.db")


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
        store.set(active=True, updated_by="Sparks", reason="no ghost canonical state")
    with pytest.raises(FileNotFoundError, match="canonical SQLite state is unavailable"):
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


def test_stop_resume_writes_tamper_evident_audit_in_same_transaction(tmp_path):
    from sofia.platform.safe.audit import AuditChain

    path = _canonical_db(tmp_path)
    stop = OperatorStopStore(path)
    timestamp = datetime(2026, 10, 11, tzinfo=timezone.utc)
    stop.set(
        active=True, updated_by="Sparks",
        reason="owner stop", at=timestamp,
    )
    resume_with_signed_owner_proof(stop, reason="owner resume", now=timestamp)
    with closing(sqlite3.connect(path)) as db:
        events = db.execute(
            "SELECT event_type, payload_json FROM safe_audit_event "
            "WHERE event_type LIKE 'operator.stop.%' ORDER BY sequence"
        ).fetchall()
    assert [event[0] for event in events] == [
        "operator.stop.activated", "operator.stop.cleared",
    ]
    assert '"previously_active":false' in events[0][1]
    assert '"previously_active":true' in events[1][1]
    assert AuditChain(path).verify() == (True, None)


def test_failure_to_audit_operator_transition_rolls_back_stop_mutation(
    tmp_path, monkeypatch,
):
    path = _canonical_db(tmp_path)
    stop = OperatorStopStore(path)
    assert stop.current().active is False

    def reject_audit(*args, **kwargs):
        raise RuntimeError("canonical audit append unavailable")

    monkeypatch.setattr(stop.audit, "append_in_transaction", reject_audit)
    with pytest.raises(RuntimeError, match="audit append unavailable"):
        stop.set(
            active=True, updated_by="Sparks",
            reason="must not claim a recorded stop",
        )
    assert stop.current().active is False
    with closing(sqlite3.connect(path)) as db:
        assert db.execute(
            "SELECT count(*) FROM safe_audit_event "
            "WHERE event_type LIKE 'operator.stop.%'"
        ).fetchone()[0] == 0


def test_reopening_after_deleted_operator_stop_row_does_not_reset_pause(tmp_path):
    """A reboot cannot silently turn corrupt STOP state into 'inactive'."""
    state = _canonical_db(tmp_path)
    stop = OperatorStopStore(state)
    stop.set(active=True, updated_by="Sparks", reason="emergency halt")
    with closing(sqlite3.connect(state)) as db, db:
        db.execute("DELETE FROM safe_operator_stop")

    with pytest.raises(RuntimeError, match="missing after initialization"):
        OperatorStopStore(state)
    with closing(sqlite3.connect(state)) as db:
        assert db.execute(
            "SELECT count(*) FROM safe_operator_stop"
        ).fetchone()[0] == 0


def test_dropped_operator_stop_table_with_audit_history_cannot_reset_pause(tmp_path):
    """Prior STOP audit evidence fences destructive table-loss recovery."""
    state = _canonical_db(tmp_path)
    store = OperatorStopStore(state)
    store.set(active=True, updated_by="Sparks", reason="owner halt")
    with closing(sqlite3.connect(state)) as db, db:
        db.execute("DROP TABLE safe_operator_stop")

    with pytest.raises(RuntimeError, match="canonical recovery"):
        OperatorStopStore(state)
    # The failed reopen must roll back CREATE TABLE in the same transaction.
    with closing(sqlite3.connect(state)) as db:
        assert db.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='safe_operator_stop'"
        ).fetchone() is None


def test_fresh_canonical_state_bootstraps_stop_only_once(tmp_path):
    state = _canonical_db(tmp_path)
    first = OperatorStopStore(state)
    assert not first.current().active
    again = OperatorStopStore(state)
    assert again.current() == first.current()
