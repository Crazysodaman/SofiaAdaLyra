"""Deferred original-audience binding of canonical project threads.

Synthetic canonical SQLite only. No tests or live migrations executed.
"""
from datetime import datetime, timezone
import sqlite3

import pytest

from test.test_lifelong_historical_reviewed_import import _identity, _source


def test_owner_project_title_cannot_attach_a_different_private_channel(tmp_path):
    state, originals, threads, _session, _other_session = _source(tmp_path)
    local = _identity()
    discord = _identity("discord:private")
    try:
        project = threads.get_or_create(
            owner=local, kind="project", name="Local Gaia Work",
        )
        assert threads.get_or_create(
            owner=local, kind="project", name="Local Gaia Work",
        ).thread_id == project.thread_id
        threads.link_message(
            thread_id=project.thread_id,
            source_message_id="original-1", principal=local,
        )
        with pytest.raises(PermissionError, match="unavailable"):
            threads.get_or_create(
                owner=discord, kind="project", name="Local Gaia Work",
            )
        with pytest.raises(PermissionError, match="cross original"):
            threads.link_message(
                thread_id=project.thread_id,
                source_message_id="private-foreign", principal=discord,
            )
        with sqlite3.connect(state) as db:
            scope = db.execute(
                "SELECT project_audience_id,project_audience_kind "
                "FROM lifelong_thread WHERE thread_id=?",
                (project.thread_id,),
            ).fetchone()
        assert scope == (local.audience_id, local.audience_kind.value)
        assert threads.visible_events(
            thread_id=project.thread_id, principal=discord,
        ) == ()
    finally:
        originals.close()


def test_legacy_mixed_audience_project_cannot_be_adopted_or_rewritten(tmp_path):
    state, originals, threads, _session, foreign_session = _source(tmp_path)
    local = _identity()
    foreign = _identity("discord:private")
    try:
        project = threads.get_or_create(
            owner=local, kind="project", name="Legacy Mixed Work",
        )
        threads.link_message(
            thread_id=project.thread_id,
            source_message_id="original-1", principal=local,
        )
        with sqlite3.connect(state) as db:
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
        for principal in (local, foreign):
            with pytest.raises(PermissionError, match="unavailable"):
                threads.get_or_create(
                    owner=principal, kind="project", name="Legacy Mixed Work",
                )
            with pytest.raises(PermissionError, match="audience access"):
                threads.rename_project(
                    principal=principal, thread_id=project.thread_id,
                    new_name="No Cross Channel Rewrite",
                )
        with pytest.raises(PermissionError, match="cross original"):
            threads.link_message(
                thread_id=project.thread_id,
                source_message_id="original-2", principal=local,
            )
        # A mixed-source legacy project stays quarantined in its entirety.
        # Even the individual source audiences cannot render partial content.
        for principal in (local, foreign):
            assert threads.visible_events(
                thread_id=project.thread_id, principal=principal,
            ) == ()
            assert threads.visible_messages(
                thread_id=project.thread_id, principal=principal,
            ) == ()
    finally:
        originals.close()


def test_legacy_project_with_exclusively_local_originals_is_still_usable(tmp_path):
    state, originals, threads, _session, _other_session = _source(tmp_path)
    local = _identity()
    try:
        project = threads.get_or_create(
            owner=local, kind="project", name="Original Scoped Project",
        )
        threads.link_message(
            thread_id=project.thread_id,
            source_message_id="original-1", principal=local,
        )
        with sqlite3.connect(state) as db:
            db.execute(
                "UPDATE lifelong_thread SET project_audience_id=NULL,"
                "project_audience_kind=NULL WHERE thread_id=?",
                (project.thread_id,),
            )
        assert threads.get_or_create(
            owner=local, kind="project", name="Original Scoped Project",
        ).thread_id == project.thread_id
    finally:
        originals.close()
