"""Deferred regression for imported ChatGPT source-evidence canonical fencing.

Source evidence remains in sofia.db, never an implicit replacement database.
"""
from contextlib import closing
import os
import sqlite3

import pytest

from sofia.memory.chatgpt_export_store import ChatGPTExportEvidenceStore
from sofia.state.canonical_sqlite import CanonicalStateUnavailable


def test_imported_evidence_owner_rejects_canonical_database_removal(tmp_path):
    path = tmp_path / "sofia.db"
    store = ChatGPTExportEvidenceStore(path)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE name='chatgpt_export_batch'"
        ).fetchone() is not None

    path.unlink()
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        store.counts("source-digest")
    assert not path.exists()


def test_imported_evidence_owner_rejects_canonical_database_replacement(tmp_path):
    path = tmp_path / "sofia.db"
    store = ChatGPTExportEvidenceStore(path)
    alternate = tmp_path / "other.db"
    with closing(sqlite3.connect(alternate)) as db:
        db.execute("CREATE TABLE other (id INTEGER PRIMARY KEY)")
        db.commit()

    os.replace(alternate, path)
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        store.search_relevant("source history", principal_id="person:sparks")
    with closing(sqlite3.connect(path)) as db:
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE name='chatgpt_export_batch'"
        ).fetchone() is None
