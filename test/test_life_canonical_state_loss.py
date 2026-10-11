"""Fail-closed canonical SQLite state ownership for LIFE/Main/GOALS.

Regressions are intentionally authored but not executed in the current
source-coding campaign. They must run in the final exact-revision CI gate.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import pytest

from sofia.conversation.lifelong import LifelongThreadStore
from sofia.goals.evidence import GoalEvidenceIndex, GoalEvidenceLedger
from sofia.life.store import LifeStore
from sofia.social.model import AudienceKind, PrincipalContext


OWNERS = (LifeStore, LifelongThreadStore, GoalEvidenceLedger, GoalEvidenceIndex)


def _owner():
    return PrincipalContext(
        principal_id="owner:verified",
        audience_id="local:text",
        audience_kind=AudienceKind.PRIVATE,
        display_name="Owner",
    )


def _read(store):
    if isinstance(store, LifeStore):
        return store.active_interests(audience_id="local:text")
    if isinstance(store, LifelongThreadStore):
        return store.list_threads(owner=_owner())
    if isinstance(store, GoalEvidenceIndex):
        return store.lookup("missing-test-ref")
    return store.record(
        kind="reviewed_evidence",
        observed_at=datetime.now(timezone.utc),
        source="local:test",
        assertion="A local test fact",
    )


@pytest.mark.parametrize("store_class", OWNERS)
def test_missing_state_is_not_created_during_store_start(tmp_path, store_class):
    path = tmp_path / "not-installed" / "sofia.db"
    with pytest.raises(FileNotFoundError):
        store_class(path)
    assert not path.exists()
    assert not path.parent.exists()


@pytest.mark.parametrize("store_class", OWNERS)
def test_lost_canonical_state_cannot_be_resurrected_after_start(tmp_path, store_class):
    path = tmp_path / "sofia.db"
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA user_version")
    owner = store_class(path)
    path.unlink()  # No store retains a live connection here.
    with pytest.raises((FileNotFoundError, sqlite3.OperationalError)):
        _read(owner)
    assert not path.exists(), "a disconnected writer may not create a new sofia.db"


@pytest.mark.parametrize("store_class", OWNERS)
def test_redirected_canonical_path_rejected_at_initialization(tmp_path, store_class):
    actual = tmp_path / "copy.db"
    with closing(sqlite3.connect(actual)) as db:
        db.execute("PRAGMA user_version")
    path = tmp_path / "sofia.db"
    try:
        path.symlink_to(actual)
    except (OSError, NotImplementedError):
        pytest.skip("host denies unprivileged symlinks")
    with pytest.raises(FileNotFoundError):
        store_class(path)
    assert actual.exists()


@pytest.mark.parametrize("store_class", OWNERS)
def test_symlink_swap_cannot_redirect_subsequent_canonical_reads(
    tmp_path, store_class,
):
    path = tmp_path / "sofia.db"
    copied = tmp_path / "stale.db"
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA user_version")
    with closing(sqlite3.connect(copied)) as db:
        db.execute("PRAGMA user_version")
    owner = store_class(path)
    path.unlink()
    try:
        path.symlink_to(copied)
    except (OSError, NotImplementedError):
        pytest.skip("host denies unprivileged symlinks")
    with pytest.raises(FileNotFoundError):
        _read(owner)
    assert copied.exists()
