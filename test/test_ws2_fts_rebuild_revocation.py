"""Deferred privilege revocation at the final FTS maintenance commit gate.

Only synthetic canonical SQLite and in-process fake independent authority.
No test execution, live rebuild or privileged host migration performed.
"""
from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.conversation.model import ConversationMessage, ConversationRole
from test.test_ws2_fts_count_triggers import _source, _rebuild


def _first_only_authorization():
    count = [0]

    def verify(_authorization):
        count[0] += 1
        return count[0] == 1

    return verify


def test_revoked_during_first_offline_rebuild_leaves_no_ready_index(tmp_path):
    path, source, principal, session, fts, approval = _source(tmp_path)
    try:
        source.save(ConversationMessage(
            "original-1", session.id, ConversationRole.USER,
            "synthetic remembered locomotive",
            datetime.now(timezone.utc),
        ))
        with pytest.raises(PermissionError, match="expired before commit"):
            fts.rebuild_offline(
                authorization=approval,
                independently_verify_fenced_approval=_first_only_authorization(),
            )
        assert fts.status().ready is False
        with sqlite3.connect(path) as db:
            assert db.execute(
                "SELECT 1 FROM sqlite_master WHERE name=?",
                ("conversation_source_fts_insert",),
            ).fetchone() is None
            assert db.execute(
                "SELECT 1 FROM conversation_messages WHERE id='original-1'"
            ).fetchone() == (1,)
    finally:
        source.close()


def test_revoked_rebuild_retains_preexisting_healthy_search_index(tmp_path):
    path, source, principal, session, fts, approval = _source(tmp_path)
    try:
        source.save(ConversationMessage(
            "original-2", session.id, ConversationRole.USER,
            "synthetic purple electric train",
            datetime.now(timezone.utc),
        ))
        initial = _rebuild(fts, approval)
        with pytest.raises(PermissionError, match="expired before commit"):
            fts.rebuild_offline(
                authorization=approval,
                independently_verify_fenced_approval=_first_only_authorization(),
            )
        assert fts.status() == initial
        assert [msg.id for msg in fts.keyword_search(
            session_id=session.id, principal=principal, terms=("purple",),
        )] == ["original-2"]
    finally:
        source.close()
