"""Deferred canonical Main replay original-evidence regressions.

Synthetic canonical SQLite only. No models, host services or test execution.
"""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.conversation.lifelong import CanonicalTurnUncertain
from test.test_canonical_conversation_ordering import (
    infrastructure, persist_settled_turn,
)


@pytest.mark.parametrize(
    "mutation",
    ("erase_user", "erase_assistant", "withdraw_main_link", "alter_assistant"),
)
def test_completed_replay_rejects_erased_withdrawn_or_changed_original(
    tmp_path, mutation,
):
    messages, _social, turns, principal, session = infrastructure(tmp_path)
    now = datetime.now(timezone.utc)
    try:
        admission, original_reply = persist_settled_turn(
            messages, turns, principal, session,
            event_id="desktop:reviewed-original:one",
            content="source-authored question",
            response="response tied to exact originals",
            now=now,
        )
        with sqlite3.connect(tmp_path / "sofia.db") as db:
            if mutation == "erase_user":
                db.execute(
                    "DELETE FROM conversation_messages WHERE id=?",
                    (admission.user_message_id,),
                )
            elif mutation == "erase_assistant":
                db.execute(
                    "DELETE FROM conversation_messages WHERE id=?",
                    (admission.assistant_message_id,),
                )
            elif mutation == "withdraw_main_link":
                db.execute(
                    "DELETE FROM lifelong_thread_event WHERE source_message_id=?",
                    (admission.assistant_message_id,),
                )
            else:
                db.execute(
                    "UPDATE conversation_messages SET content=? WHERE id=?",
                    ("changed behind receipt", admission.assistant_message_id),
                )

        with pytest.raises(CanonicalTurnUncertain, match="current original"):
            turns.admit_turn(
                event_id=admission.event_id, principal=principal,
                session_id=session.id, channel="desktop",
                content="source-authored question",
                runtime_id="runtime:restarted",
                now=now + timedelta(seconds=2),
            )
        # Refuse a cached answer without erasing historical completion
        # evidence or creating a synthetic second assistant response.
        with sqlite3.connect(tmp_path / "sofia.db") as db:
            assert db.execute(
                "SELECT status,canonical_sequence FROM canonical_conversation_turn "
                "WHERE event_id=?", (admission.event_id,),
            ).fetchone() == ("completed", admission.canonical_sequence)
        assert original_reply.content == "response tied to exact originals"
    finally:
        messages.close()


def test_completed_replay_with_current_main_originals_preserves_receipt(
    tmp_path,
):
    messages, _social, turns, principal, session = infrastructure(tmp_path)
    now = datetime.now(timezone.utc)
    try:
        admission, original_reply = persist_settled_turn(
            messages, turns, principal, session,
            event_id="desktop:reviewed-original:valid",
            content="still authored here",
            response="same proven response",
            now=now,
        )
        repeat = turns.admit_turn(
            event_id=admission.event_id, principal=principal,
            session_id=session.id, channel="desktop",
            content="still authored here", runtime_id="runtime:restarted",
            now=now + timedelta(seconds=1),
        )
        assert repeat.status == "completed"
        assert repeat.response == original_reply
        assert repeat.canonical_sequence == admission.canonical_sequence
    finally:
        messages.close()
