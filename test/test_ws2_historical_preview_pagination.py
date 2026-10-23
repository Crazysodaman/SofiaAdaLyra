"""Deferred bounded multi-batch Main historical-review preview.

Synthetic canonical source messages only. No reviewed links are automatically
created; no tests or migrations are run during this production coding pass.
"""
from datetime import timedelta

import pytest

from sofia.core.conversation.model import ConversationMessage, ConversationRole
from test.test_lifelong_historical_reviewed_import import (
    NOW, _identity, _source,
)


def test_preview_reaches_every_original_after_128_without_importing(tmp_path):
    path, messages, main, session, _foreign = _source(tmp_path)
    try:
        for n in range(4, 164):
            messages.save(ConversationMessage(
                id=f"source-{n:04d}", session_id=session,
                role=ConversationRole.USER,
                content=f"Original source event {n}",
                created_at=NOW + timedelta(seconds=n),
            ))
        first = main.preview_historical_import(
            principal=_identity(), session_id=session, limit=128,
        )
        assert len(first.eligible_message_ids) == 128
        assert first.next_cursor is not None
        second = main.preview_historical_import(
            principal=_identity(), session_id=session,
            limit=128, after=first.next_cursor,
        )
        assert second.next_cursor is None
        full_ids = first.eligible_message_ids + second.eligible_message_ids
        assert len(full_ids) == 163
        assert len(set(full_ids)) == 163
        assert full_ids[0] == "original-1"
        assert full_ids[-1] == "source-0163"
        thread = main.get_or_create(owner=_identity())
        assert main.visible_events(
            thread_id=thread.thread_id, principal=_identity(),
        ) == ()
    finally:
        messages.close()


def test_followup_preview_still_checks_original_current_audience(tmp_path):
    _path, messages, main, session, _foreign = _source(tmp_path)
    try:
        page = main.preview_historical_import(
            principal=_identity(), session_id=session, limit=1,
        )
        assert page.next_cursor is not None
        with pytest.raises(PermissionError, match="audience"):
            main.preview_historical_import(
                principal=_identity("discord:private"),
                session_id=session, limit=2, after=page.next_cursor,
            )
        with pytest.raises(ValueError, match="cursor"):
            main.preview_historical_import(
                principal=_identity(), session_id=session,
                after=("untrusted",),
            )
    finally:
        messages.close()
