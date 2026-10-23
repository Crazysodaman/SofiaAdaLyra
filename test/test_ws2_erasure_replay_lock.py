"""Deferred erasure replay is serialized with signed journal append owner.

Synthetic canonical SQLite and separately held test journal only. No tests
were run and no live memory was deleted.
"""
from contextlib import contextmanager

import pytest

from sofia.core.memory.deletion_ledger import MemoryErasureError
from test.test_memory_deletion_restore import (
    _erase, _prepare, _assert_no_deleted_candidate,
)


def test_replay_holds_existing_external_append_lock_through_sqlite_commit(
    tmp_path, monkeypatch,
):
    state, ledger, _engine = _prepare(tmp_path)
    _erase(ledger)
    real_lock = ledger._exclusive
    real_apply = ledger._apply_to_sqlite_under_lock
    held = []
    observed = []

    @contextmanager
    def observed_lock():
        with real_lock():
            held.append(True)
            try:
                yield
            finally:
                held.pop()

    def observed_replay(path):
        observed.append(bool(held))
        return real_apply(path)

    monkeypatch.setattr(ledger, "_exclusive", observed_lock)
    monkeypatch.setattr(
        ledger, "_apply_to_sqlite_under_lock", observed_replay,
    )

    assert ledger.apply_to_sqlite(state) == 1
    assert observed == [True]
    assert held == []
    _assert_no_deleted_candidate(state)
    assert ledger.verify_applied(state)["verified_absent"] == 1


def test_lost_external_journal_lock_denies_sqlite_erase_before_mutation(
    tmp_path, monkeypatch,
):
    state, ledger, _engine = _prepare(tmp_path)
    _erase(ledger)

    @contextmanager
    def denied_lock():
        raise MemoryErasureError("independent journal append lock is unavailable")
        yield

    monkeypatch.setattr(ledger, "_exclusive", denied_lock)
    with pytest.raises(MemoryErasureError, match="append lock"):
        ledger.apply_to_sqlite(state)

    from sqlite3 import connect
    with connect(state) as db:
        assert db.execute(
            "SELECT content FROM memory_candidate"
        ).fetchone()[0] == "PRIVATE-REMOVED-SUMMARY"
