"""Deferred canonical turn receipt fencing across stale runtime failures.

Synthetic state and original admissions only, no LLM or live host.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.core.conversation.lifelong import CanonicalTurnUncertain
from test.test_canonical_conversation_ordering import (
    infrastructure, persist_settled_turn,
)


def test_stale_mismatched_admission_cannot_mark_current_claim_uncertain(tmp_path):
    messages, _social, turns, principal, session = infrastructure(tmp_path)
    now = datetime.now(timezone.utc)
    try:
        real = turns.admit_turn(
            event_id="desktop:uncertainty:1", principal=principal,
            session_id=session.id, channel="desktop", content="original turn",
            runtime_id="runtime:first", now=now,
        )
        changed = replace(real, assistant_message_id="wrong-assistant-id")
        with pytest.raises(CanonicalTurnUncertain, match="admission identity"):
            turns.mark_turn_uncertain(
                admission=changed, interrupted=False,
                now=now + timedelta(seconds=1),
            )
        with sqlite3.connect(tmp_path / "sofia.db") as db:
            assert db.execute(
                "SELECT status FROM canonical_conversation_turn WHERE event_id=?",
                (real.event_id,),
            ).fetchone() == ("processing",)

        turns.mark_turn_uncertain(
            admission=real, interrupted=False,
            now=now + timedelta(seconds=2),
        )
        with sqlite3.connect(tmp_path / "sofia.db") as db:
            assert db.execute(
                "SELECT status FROM canonical_conversation_turn WHERE event_id=?",
                (real.event_id,),
            ).fetchone() == ("uncertain",)
    finally:
        messages.close()


def test_late_exception_never_reverts_completed_turn_to_uncertain(tmp_path):
    messages, _social, turns, principal, session = infrastructure(tmp_path)
    now = datetime.now(timezone.utc)
    try:
        completed, response = persist_settled_turn(
            messages, turns, principal, session,
            event_id="desktop:uncertainty:completed", content="question",
            response="persisted true answer", now=now,
        )
        turns.mark_turn_uncertain(
            admission=completed, interrupted=False,
            now=now + timedelta(seconds=2),
        )
        replay = turns.admit_turn(
            event_id=completed.event_id, principal=principal,
            session_id=session.id, channel="desktop", content="question",
            runtime_id="runtime:new", now=now + timedelta(seconds=3),
        )
        assert replay.status == "completed"
        assert replay.response == response
    finally:
        messages.close()
