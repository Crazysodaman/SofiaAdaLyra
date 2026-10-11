"""Deferred Phase 05 project rename/archive lifecycle and source audience tests.

All fixtures use synthetic canonical SQLite originals. No tests, deployments,
live thread modifications, or external outbound messages are performed here.
"""
from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.conversation.lifelong import LifelongThreadStore
from test.test_lifelong_historical_reviewed_import import _identity, _source


def test_project_rename_archive_and_restore_preserve_original_sources(tmp_path):
    state, originals, threads, session, _other = _source(tmp_path)
    principal = _identity()
    try:
        project = threads.get_or_create(
            owner=principal, kind="project", name="Original Trains",
        )
        threads.link_message(
            thread_id=project.thread_id,
            source_message_id="original-1", principal=principal,
        )
        before = originals.list_messages(session)
        renamed = threads.rename_project(
            principal=principal, thread_id=project.thread_id,
            new_name="Updated Trains",
        )
        assert renamed.thread_id == project.thread_id
        assert renamed.name == "Updated Trains"
        assert renamed.archived_at is None
        assert any(
            t.thread_id == project.thread_id
            for t in threads.list_visible_threads(owner=principal)
        )
        archived = threads.set_project_archived(
            principal=principal, thread_id=project.thread_id, archived=True,
        )
        assert archived.archived_at is not None
        assert not any(
            t.thread_id == project.thread_id
            for t in threads.list_visible_threads(owner=principal)
        )
        assert any(
            t.thread_id == project.thread_id and t.archived_at is not None
            for t in threads.list_visible_threads(
                owner=principal, include_archived=True,
            )
        )
        assert any(
            t.thread_id == project.thread_id
            for t in threads.list_threads(
                owner=principal, include_archived=True,
            )
        )
        restored = threads.set_project_archived(
            principal=principal, thread_id=project.thread_id, archived=False,
        )
        assert restored.archived_at is None
        assert threads.get_or_create(
            owner=principal, kind="project", name="Updated Trains",
        ).thread_id == project.thread_id
        assert originals.list_messages(session) == before
    finally:
        originals.close()


def test_project_metadata_cannot_be_mutated_from_another_private_audience(tmp_path):
    _state, originals, threads, _session, _other = _source(tmp_path)
    local = _identity()
    foreign = _identity("discord:private")
    try:
        project = threads.get_or_create(
            owner=local, kind="project", name="Local Only Project",
        )
        threads.link_message(
            thread_id=project.thread_id,
            source_message_id="original-1", principal=local,
        )
        with pytest.raises(PermissionError, match="audience access"):
            threads.rename_project(
                principal=foreign, thread_id=project.thread_id,
                new_name="Hidden Local Rename",
            )
        with pytest.raises(PermissionError, match="audience access"):
            threads.set_project_archived(
                principal=foreign, thread_id=project.thread_id, archived=True,
            )
        assert all(
            entry.thread_id != project.thread_id
            for entry in threads.list_visible_threads(
                owner=foreign, include_archived=True,
            )
        )
        assert threads.thread_for(
            owner=local, thread_id=project.thread_id,
        ).name == "Local Only Project"
    finally:
        originals.close()


def test_source_free_project_and_main_cannot_be_mutated_as_project(tmp_path):
    _state, originals, threads, _session, _other = _source(tmp_path)
    owner = _identity()
    try:
        free = threads.get_or_create(
            owner=owner, kind="project", name="No Originals Yet",
        )
        with pytest.raises(PermissionError, match="audience access"):
            threads.set_project_archived(
                principal=owner, thread_id=free.thread_id, archived=True,
            )
        main = threads.get_or_create(owner=owner)
        with pytest.raises(PermissionError, match="audience access"):
            threads.rename_project(
                principal=owner, thread_id=main.thread_id, new_name="Not Main",
            )
        visible = threads.list_visible_threads(owner=owner)
        assert any(item.kind == "main" for item in visible)
    finally:
        originals.close()


def test_old_thread_table_adds_archive_column_without_losing_main(tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE lifelong_thread("
            "thread_id TEXT PRIMARY KEY, owner_principal_id TEXT NOT NULL,"
            "kind TEXT NOT NULL CHECK(kind IN ('main','project')),"
            "name TEXT NOT NULL,created_at TEXT NOT NULL,"
            "UNIQUE(owner_principal_id,kind,name))"
        )
        connection.execute(
            "INSERT INTO lifelong_thread VALUES(?,?,?,?,?)",
            ("thread:originalmain", _identity().principal_id, "main",
             "Main", datetime.now(timezone.utc).isoformat()),
        )
    threads = LifelongThreadStore(database)
    original = threads.get_or_create(owner=_identity())
    assert original.thread_id == "thread:originalmain"
    assert original.archived_at is None
    with sqlite3.connect(database) as connection:
        columns = {
            item[1] for item in connection.execute(
                "PRAGMA table_info(lifelong_thread)"
            )
        }
        assert "archived_at" in columns
