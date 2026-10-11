"""Deferred Phase 06 regression: normal turns never load lifetime messages.

The original SQLite conversation remains intact; only local follow-up
context is bounded. Tests intentionally not executed in coding campaign.
"""
from datetime import datetime, timedelta, timezone

from sofia.conversation.model import ConversationMessage, ConversationRole
from test.test_conversation_service import create_application


def test_wardrobe_followup_uses_bounded_recent_context_not_full_transcript(
    tmp_path, monkeypatch,
):
    application = create_application(tmp_path)
    application.start()
    conversation = application.conversation
    store = conversation._conversation_store
    session_id = conversation.session_id
    try:
        # Simulate an existing long Main/session: the clothing stage only
        # needs the last user statement and should not walk old originals.
        beginning = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for index in range(140):
            role = (
                ConversationRole.USER
                if index % 2 == 0 else ConversationRole.ASSISTANT
            )
            store.save(ConversationMessage(
                id=f"legacy:{index:04d}", session_id=session_id,
                role=role,
                content=f"historical #{index}",
                created_at=beginning + timedelta(seconds=index),
            ))

        seen_limits = []
        seen_previous_user = []
        actual_recent = store.recent_messages

        def observed_recent(session, *, limit=24):
            seen_limits.append(limit)
            return actual_recent(session, limit=limit)

        def forbid_full_transcript(_session):
            raise AssertionError("unbounded list_messages invoked on hot turn")

        monkeypatch.setattr(store, "recent_messages", observed_recent)
        monkeypatch.setattr(store, "list_messages", forbid_full_transcript)
        conversation._v2_answer_handler = None
        conversation.set_clothing_action_handler(
            lambda *, previous_user_content, **_kwargs:
                seen_previous_user.append(previous_user_content) or
                "Clothing action inspected bounded follow-up context.",
        )
        reply = conversation.respond("Change my outfit to something practical.")
        assert reply.content
        assert seen_previous_user == ["historical #138"]
        assert seen_limits and all(limit <= 96 for limit in seen_limits)
        assert 64 in seen_limits
        assert len(actual_recent(session_id, limit=500)) == 142
    finally:
        application.shutdown()
