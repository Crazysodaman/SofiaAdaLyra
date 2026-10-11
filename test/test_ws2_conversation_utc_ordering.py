"""Deferred Phase 06 mixed-timezone canonical event ordering regressions.

New timezone-aware original timestamps use UTC. Historical rows remain
unchanged until a separately reviewed offline migration. No tests run here.
"""
from datetime import timedelta, timezone

import pytest

from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore


def test_new_mixed_offset_sources_are_stored_and_paged_in_true_utc_order(tmp_path):
    store = ConversationStore(tmp_path / "sofia.db")
    try:
        session = store.create_session()
        before = session.created_at + timedelta(seconds=10)
        after = session.created_at + timedelta(seconds=20)
        ahead = timezone(timedelta(hours=5))
        behind = timezone(timedelta(hours=-5))
        older = ConversationMessage(
            "source:older", session.id, ConversationRole.USER,
            "Older source despite a lexically later local wall clock",
            before.astimezone(ahead),
        )
        newer = ConversationMessage(
            "source:newer", session.id, ConversationRole.ASSISTANT,
            "Newer source despite a lexically earlier local wall clock",
            after.astimezone(behind),
        )
        store.save(newer)
        store.save(older)
        page = store.list_messages_page(session.id, limit=2)
        assert [message.id for message in page] == [
            "source:older", "source:newer",
        ]
        assert all(
            message.created_at.utcoffset() == timedelta(0)
            for message in page
        )
        assert [message.id for message in store.recent_messages(
            session.id, limit=2,
        )] == ["source:older", "source:newer"]
        assert store.get_session(session.id).updated_at == after

        second_page = store.list_messages_page(
            session.id, after=(page[0].created_at, page[0].id), limit=2,
        )
        assert [message.id for message in second_page] == ["source:newer"]
    finally:
        store.close()


def test_original_idempotency_accepts_equivalent_timezone_offset_not_new_instant(
    tmp_path,
):
    store = ConversationStore(tmp_path / "sofia.db")
    try:
        session = store.create_session()
        original_time = session.created_at + timedelta(seconds=30)
        message = ConversationMessage(
            "source:stable-id", session.id, ConversationRole.USER,
            "Original source text", original_time,
        )
        store.save(message)
        store.save(ConversationMessage(
            message.id, message.session_id, message.role, message.content,
            original_time.astimezone(timezone(timedelta(hours=-7))),
        ))
        assert len(store.list_messages(session.id)) == 1
        with pytest.raises(ValueError, match="different timestamp"):
            store.save(ConversationMessage(
                message.id, message.session_id, message.role,
                message.content, original_time + timedelta(seconds=1),
            ))
    finally:
        store.close()
