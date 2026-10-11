"""Deferred FTS5 readiness proof and authenticated degraded source fallback.

Synthetic canonical SQLite and a stub owner-approved offline rebuild only.
No tests, real state rebuild, CI or host changes.
"""
from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.conversation.model import ConversationMessage, ConversationRole
from test.test_ws2_fts_count_triggers import _source, _rebuild


@pytest.mark.parametrize("removed", (
    "conversation_messages_fts",
    "conversation_source_fts_insert",
    "conversation_source_fts_delete",
    "conversation_source_fts_update",
))
def test_missing_index_or_maintenance_trigger_cannot_claim_ready(
    tmp_path, removed,
):
    path, source, principal, session, fts, approval = _source(tmp_path)
    try:
        source.save(ConversationMessage(
            "canonical-source", session.id, ConversationRole.USER,
            "blue model trains are part of this original",
            datetime.now(timezone.utc),
        ))
        assert _rebuild(fts, approval).ready is True
        with sqlite3.connect(path) as db:
            if removed == "conversation_messages_fts":
                db.execute("DROP TABLE conversation_messages_fts")
            else:
                db.execute("DROP TRIGGER " + removed)
        degraded = fts.status()
        assert degraded.ready is False
        assert degraded.row_count == 1
        with pytest.raises(RuntimeError, match="not been explicitly rebuilt"):
            fts.keyword_search(
                session_id=session.id, principal=principal,
                terms=("trains",),
            )
        # The canonical current-audience SQL original fallback remains usable.
        assert [m.id for m in source.search_messages(
            session.id, terms=("trains",),
            authorized_principal=principal, limit=6,
        )] == ["canonical-source"]
    finally:
        source.close()
