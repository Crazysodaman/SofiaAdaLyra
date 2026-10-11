"""Deferred import and reviewed-promotion fencing regressions.

No tests executed in the concurrent V18 workstream.
"""
from datetime import datetime, timezone
import os
import sqlite3

import pytest

from sofia.memory.chatgpt_import_store import ChatGPTMemoryImportStore
from sofia.state.canonical_sqlite import CanonicalStateUnavailable
from test.test_chatgpt_memory_import import _import


@pytest.mark.skipif(os.name == "nt", reason="Windows retains open SQLite file locks")
def test_import_originals_do_not_read_orphaned_database_after_os_replacement(tmp_path):
    state = tmp_path / "sofia.db"
    store = ChatGPTMemoryImportStore(state)
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT name FROM sqlite_master WHERE name='chatgpt_memory_import_batch'"
        ).fetchone() is not None

    alternate = tmp_path / "replacement.db"
    with sqlite3.connect(alternate) as db:
        db.execute("CREATE TABLE other (id INTEGER PRIMARY KEY)")
    try:
        os.replace(alternate, state)
        with pytest.raises(CanonicalStateUnavailable, match="replaced"):
            store.list_imports()
        with pytest.raises(CanonicalStateUnavailable, match="replaced"):
            store.original_payload("source-digest")
    finally:
        store.close()


def test_reviewed_promotion_mapping_cannot_use_replaced_state(tmp_path):
    state = tmp_path / "sofia.db"
    _, imports, migration, candidate_ids = _import(state)
    try:
        # Existing import handles may hold the database open on Windows;
        # close first to prove the short-lived promotion mapping is pinned.
        migration.close()
        imports.close()
        alternate = tmp_path / "replacement.db"
        with sqlite3.connect(alternate) as db:
            db.execute("CREATE TABLE other (id INTEGER PRIMARY KEY)")
        os.replace(alternate, state)
        with pytest.raises(CanonicalStateUnavailable, match="replaced"):
            migration.promote(
                candidate_ids[0],
                approved_by="Sparks",
                at=datetime.now(timezone.utc),
            )
    finally:
        migration.close()
        imports.close()
