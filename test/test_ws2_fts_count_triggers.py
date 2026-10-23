"""Deferred FTS source-count and indexed-message lifecycle regressions.

The FTS5 maintenance call is only invoked over synthetic SQLite with a fake
independently fenced owner approval. No real index is rebuilt or tests run.
"""
from datetime import datetime, timedelta, timezone
import sqlite3

from sofia.core.conversation.fulltext_search import (
    ConversationFullTextSearch, OfflineIndexAuthorization,
)
from sofia.core.conversation.model import ConversationMessage, ConversationRole
from sofia.core.conversation.store import ConversationStore
from sofia.core.social.principals import local_sparks_principal
from sofia.core.social.store import SocialSessionStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


def _source(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    source = ConversationStore(path)
    principal = local_sparks_principal()
    session = source.create_session()
    SocialSessionStore(path).bind(session_id=session.id, principal=principal)
    fts = ConversationFullTextSearch(path)
    approval = OfflineIndexAuthorization(
        canonical_state_path=path, writer_host_id="offline-fixture",
        writer_fence_ref="independent-synthetic-fence",
        operator_approval_ref="owner-reviewed-fixture",
    )
    return path, source, principal, session, fts, approval


def _rebuild(fts, approval):
    return fts.rebuild_offline(
        authorization=approval,
        independently_verify_fenced_approval=lambda reviewed:
            reviewed is approval,
    )


def test_source_add_edit_delete_keep_fts_row_count_and_original_search_current(
    tmp_path,
):
    path, source, principal, session, fts, approval = _source(tmp_path)
    now = datetime.now(timezone.utc)
    try:
        assert _rebuild(fts, approval).row_count == 0
        first = ConversationMessage(
            "original-1", session.id, ConversationRole.USER,
            "Only the original violet locomotive", now,
        )
        source.save(first)
        assert fts.status().row_count == 1
        assert [m.id for m in fts.keyword_search(
            session_id=session.id, principal=principal, terms=("violet",),
        )] == ["original-1"]

        # A separately authorized canonical source edit is indexed without
        # inflating the number of original source rows.
        with sqlite3.connect(path) as db:
            db.execute(
                "UPDATE conversation_messages SET content=? WHERE id=?",
                ("Original cyan locomotive", first.id),
            )
        assert fts.status().row_count == 1
        assert fts.keyword_search(
            session_id=session.id, principal=principal, terms=("violet",),
        ) == ()
        assert [m.id for m in fts.keyword_search(
            session_id=session.id, principal=principal, terms=("cyan",),
        )] == ["original-1"]

        with sqlite3.connect(path) as db:
            db.execute("DELETE FROM conversation_messages WHERE id=?", (first.id,))
        assert fts.status().row_count == 0
        assert fts.keyword_search(
            session_id=session.id, principal=principal, terms=("cyan",),
        ) == ()
    finally:
        source.close()


def test_reauthorized_offline_rebuild_upgrades_old_countless_trigger(tmp_path):
    path, source, principal, session, fts, approval = _source(tmp_path)
    now = datetime.now(timezone.utc)
    try:
        source.save(ConversationMessage(
            "original-early", session.id, ConversationRole.USER,
            "earlier historic record", now,
        ))
        assert _rebuild(fts, approval).row_count == 1
        with sqlite3.connect(path) as db:
            db.execute("DROP TRIGGER conversation_source_fts_insert")
            db.execute(
                "CREATE TRIGGER conversation_source_fts_insert "
                "AFTER INSERT ON conversation_messages BEGIN "
                "INSERT INTO conversation_messages_fts(rowid,content) "
                "VALUES(new.rowid,new.content); END"
            )
        # Only reviewed offline maintenance is allowed to upgrade triggers.
        assert _rebuild(fts, approval).row_count == 1
        source.save(ConversationMessage(
            "original-later", session.id, ConversationRole.USER,
            "later historic record", now + timedelta(seconds=1),
        ))
        assert fts.status().row_count == 2
    finally:
        source.close()
