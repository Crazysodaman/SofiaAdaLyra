"""V18 CA-6804 canonical SQLite regressions (authored, not run here)."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.application.background import BackgroundBudget
from sofia.conversation.store import ConversationStore
from sofia.run.work import DurableWorkStore
from sofia.safe.audit import AuditChain
from sofia.state.canonical_sqlite import (
    CanonicalSQLiteGuard,
    CanonicalStateUnavailable,
    bootstrap_canonical_sqlite,
)


def test_authorized_bootstrap_is_atomic_and_idempotent(tmp_path):
    path = tmp_path / "state" / "sofia.db"
    assert bootstrap_canonical_sqlite(path) == path.absolute()
    first = path.stat()
    assert bootstrap_canonical_sqlite(path) == path.absolute()
    second = path.stat()
    assert (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)
    with closing(sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True)) as db:
        assert db.execute("PRAGMA application_id").fetchone()[0] == 0x534F4649


@pytest.mark.parametrize(
    "owner",
    (AuditChain, DurableWorkStore, ConversationStore),
)
def test_ordinary_owner_never_bootstraps_missing_state(tmp_path, owner):
    path = tmp_path / "missing" / "sofia.db"
    with pytest.raises(CanonicalStateUnavailable):
        owner(path)
    assert not path.exists()
    assert not path.parent.exists()


def test_guard_rejects_regular_file_replacement_after_start(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    guard = CanonicalSQLiteGuard(path)
    path.unlink()
    replacement = tmp_path / "replacement.db"
    with closing(sqlite3.connect(replacement)) as db:
        db.execute("PRAGMA user_version=7")
    replacement.replace(path)
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        guard.connect()


def test_background_budget_fails_closed_after_state_loss(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    budget = BackgroundBudget(path)
    path.unlink()
    with pytest.raises(CanonicalStateUnavailable):
        budget.claim("life", now=datetime.now(timezone.utc))
    assert not path.exists()


def test_symlinked_parent_is_not_a_canonical_state_home(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    redirected = tmp_path / "redirected"
    try:
        redirected.symlink_to(actual, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("host denies unprivileged symlinks")
    with pytest.raises(CanonicalStateUnavailable, match="symbolic link"):
        bootstrap_canonical_sqlite(redirected / "sofia.db")
    assert not (actual / "sofia.db").exists()

def test_guard_refuses_replacement_during_sqlite_open_and_closes_new_handle(
    tmp_path, monkeypatch,
):
    """No swapped-in file may be adopted between stat and sqlite3.connect."""
    from sofia.state import canonical_sqlite

    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    guard = CanonicalSQLiteGuard(path)
    replacement = tmp_path / "replacement.db"
    with closing(sqlite3.connect(replacement)) as db:
        db.execute("PRAGMA user_version=17")
    original_connect = sqlite3.connect
    opened = []

    def swap_while_opening(*args, **kwargs):
        replacement.replace(path)
        db = original_connect(*args, **kwargs)
        opened.append(db)
        return db

    monkeypatch.setattr(canonical_sqlite.sqlite3, "connect", swap_while_opening)
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        guard.connect()
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("PRAGMA user_version")
