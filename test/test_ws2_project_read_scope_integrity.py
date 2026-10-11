"""Deferred production project read isolation across every source projection.

Injected mixed-audience rows model old or externally corrupted canonical
metadata. No real messages, channels, tests or migrations are touched.
"""
from datetime import datetime, timezone
import sqlite3

import pytest

from test.test_lifelong_historical_reviewed_import import _identity, _source


def _mixed(tmp_path, *, legacy):
    state, originals, threads, _local_session, foreign_session = _source(tmp_path)
    local = _identity()
    foreign = _identity("discord:private")
    project = threads.get_or_create(
        owner=local, kind="project", name="Original Private Engineering",
    )
    threads.link_message(
        thread_id=project.thread_id,
        source_message_id="original-1", principal=local,
    )
    with sqlite3.connect(state) as db:
        if legacy:
            db.execute(
                "UPDATE lifelong_thread SET project_audience_id=NULL,"
                "project_audience_kind=NULL WHERE thread_id=?",
                (project.thread_id,),
            )
        db.execute(
            "INSERT INTO lifelong_thread_event("
            "thread_id,source_message_id,source_session_id,"
            "source_audience_id,visibility,linked_at,"
            "canonical_sequence,turn_position) "
            "VALUES(?,?,?,?,?,?,NULL,NULL)",
            (project.thread_id, "private-foreign", foreign_session,
             foreign.audience_id, "source_audience",
             datetime.now(timezone.utc).isoformat()),
        )
    return originals, threads, project, local, foreign


@pytest.mark.parametrize("legacy", (True, False))
def test_inconsistent_project_blocks_headers_and_all_original_reads(
    tmp_path, legacy,
):
    originals, threads, project, local, foreign = _mixed(
        tmp_path, legacy=legacy,
    )
    try:
        for principal in (local, foreign):
            assert all(
                item.thread_id != project.thread_id
                for item in threads.list_visible_threads(
                    owner=principal, include_archived=True,
                )
            )
            assert threads.visible_events(
                thread_id=project.thread_id, principal=principal,
            ) == ()
            assert threads.visible_messages(
                thread_id=project.thread_id, principal=principal,
            ) == ()
            with pytest.raises(PermissionError, match="project original audience"):
                threads.visible_message_page(
                    thread_id=project.thread_id, principal=principal,
                )
            with pytest.raises(PermissionError, match="unavailable"):
                threads.get_or_create(
                    owner=principal, kind="project",
                    name="Original Private Engineering",
                )
    finally:
        originals.close()


def test_healthy_source_bounded_project_remains_visible_to_original_owner(tmp_path):
    state, originals, threads, _local, _foreign = _source(tmp_path)
    local = _identity()
    try:
        project = threads.get_or_create(
            owner=local, kind="project", name="Owner Only Trains",
        )
        threads.link_message(
            thread_id=project.thread_id,
            source_message_id="original-1", principal=local,
        )
        assert project.thread_id in {
            item.thread_id for item in threads.list_visible_threads(owner=local)
        }
        assert [item.source_message_id for item in threads.visible_events(
            thread_id=project.thread_id, principal=local,
        )] == ["original-1"]
        assert [item.id for item in threads.visible_messages(
            thread_id=project.thread_id, principal=local,
        )] == ["original-1"]
        assert [item.message.id for item in threads.visible_message_page(
            thread_id=project.thread_id, principal=local,
        )] == ["original-1"]
    finally:
        originals.close()
