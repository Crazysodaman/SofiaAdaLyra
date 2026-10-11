"""Deferred independent owner review rechecks on historical Main mutations.

The approval callback is synthetic and changes from allowed to revoked
between preliminary and final checks. No real operator grant or live Main
conversation is touched. Tests authored but deliberately not run.
"""
from contextlib import closing
import sqlite3

import pytest

from test.test_lifelong_historical_reviewed_import import (
    _identity, _source, _trusted_review,
)


def _approval_then_revoke(_ref, _digest):
    """Independent source grants can be withdrawn during SQL preparation."""
    _approval_then_revoke.calls += 1
    return _approval_then_revoke.calls == 1


def test_expired_import_review_cannot_create_historical_main_links(tmp_path):
    state, messages, store, session, _foreign = _source(tmp_path)
    try:
        _approval_then_revoke.calls = 0
        with pytest.raises(PermissionError, match="expired before publication"):
            store.apply_historical_import(
                principal=_identity(), session_id=session,
                message_ids=("original-1", "original-2"),
                review_ref="owner-approved-import-revoked",
                reject=False,
                independently_verify_operator_review=_approval_then_revoke,
            )
        with closing(sqlite3.connect(state)) as db:
            assert db.execute(
                "SELECT COUNT(*) FROM lifelong_historical_import"
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT COUNT(*) FROM lifelong_thread_event"
            ).fetchone()[0] == 0
    finally:
        messages.close()


def test_expired_rollback_review_preserves_import_links(tmp_path):
    _state, messages, store, session, _foreign = _source(tmp_path)
    try:
        imported = store.apply_historical_import(
            principal=_identity(), session_id=session,
            message_ids=("original-1",),
            review_ref="owner-approved-rollback-revoked",
            reject=False, independently_verify_operator_review=_trusted_review,
        )
        _approval_then_revoke.calls = 0
        with pytest.raises(PermissionError, match="expired before publication"):
            store.rollback_historical_import(
                principal=_identity(), review_ref=imported.review_ref,
                message_ids=("original-1",),
                independently_verify_operator_review=_approval_then_revoke,
            )
        thread = store.get_or_create(owner=_identity())
        assert [e.source_message_id for e in store.visible_events(
            thread_id=thread.thread_id, principal=_identity(),
        )] == ["original-1"]
        assert imported.pending_ids == ("original-1",)
    finally:
        messages.close()
