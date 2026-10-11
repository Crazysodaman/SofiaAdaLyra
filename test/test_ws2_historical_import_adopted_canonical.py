"""Deferred Main historical import and independent canonical link ownership.

This uses only synthetic SQLite and offline approved-review callbacks.
"""
from contextlib import closing
import sqlite3

import pytest

from test.test_lifelong_historical_reviewed_import import (
    _identity, _source, _trusted_review,
)


def test_rollback_refuses_history_link_adopted_by_canonical_turn(tmp_path):
    state, source, store, session, _other = _source(tmp_path)
    try:
        receipt = store.apply_historical_import(
            principal=_identity(), session_id=session,
            message_ids=("original-1",),
            review_ref="synthetic-main-adoption-review",
            reject=False,
            independently_verify_operator_review=_trusted_review,
        )
        thread = store.get_or_create(owner=_identity())
        with closing(sqlite3.connect(state)) as db, db:
            db.execute(
                "UPDATE lifelong_thread_event "
                "SET canonical_sequence=42,turn_position=0 "
                "WHERE thread_id=? AND source_message_id='original-1'",
                (thread.thread_id,),
            )

        with pytest.raises(PermissionError, match="adopted canonical turn"):
            store.rollback_historical_import(
                principal=_identity(), review_ref=receipt.review_ref,
                message_ids=("original-1",),
                independently_verify_operator_review=_trusted_review,
            )
        with closing(sqlite3.connect(state)) as db:
            assert db.execute(
                "SELECT canonical_sequence,turn_position "
                "FROM lifelong_thread_event "
                "WHERE thread_id=? AND source_message_id='original-1'",
                (thread.thread_id,),
            ).fetchone() == (42, 0)
        assert [event.source_message_id for event in store.visible_events(
            thread_id=thread.thread_id, principal=_identity(),
        )] == ["original-1"]
    finally:
        source.close()


def test_unadopted_import_still_rolls_back_without_erasing_original(tmp_path):
    _state, source, store, session, _other = _source(tmp_path)
    try:
        before = source.list_messages(session)
        receipt = store.apply_historical_import(
            principal=_identity(), session_id=session,
            message_ids=("original-1",),
            review_ref="synthetic-unadopted-review",
            reject=False,
            independently_verify_operator_review=_trusted_review,
        )
        undone = store.rollback_historical_import(
            principal=_identity(), review_ref=receipt.review_ref,
            message_ids=("original-1",),
            independently_verify_operator_review=_trusted_review,
        )
        assert undone.status == "rolled_back"
        assert undone.pending_ids == ()
        assert source.list_messages(session) == before
    finally:
        source.close()
