"""CA-5502 operator-reviewed, reversible same-audience historic Main import.

No external system, model instruction or background migration can authorize
this workflow. These regression cases are authored but NOT executed.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.conversation.lifelong import LifelongThreadStore
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.store import SocialSessionStore


NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


def _identity(audience="local:text"):
    return PrincipalContext(
        principal_id="owner:validated", audience_id=audience,
        audience_kind=AudienceKind.PRIVATE, display_name="Owner",
    )


def _source(tmp_path):
    state = tmp_path / "sofia.db"
    source = ConversationStore(state)
    social = SocialSessionStore(state)
    main = LifelongThreadStore(state)
    original = source.create_session()
    other = source.create_session()
    social.bind(session_id=original.id, principal=_identity())
    social.bind(session_id=other.id, principal=_identity("discord:private"))
    for number in (1, 2, 3):
        source.save(ConversationMessage(
            id=f"original-{number}", session_id=original.id,
            role=ConversationRole.USER, content=f"Unaltered content {number}",
            created_at=NOW + timedelta(seconds=number),
        ))
    source.save(ConversationMessage(
        id="private-foreign", session_id=other.id,
        role=ConversationRole.USER, content="Audience other",
        created_at=NOW + timedelta(seconds=4),
    ))
    return state, source, main, original.id, other.id


def _trusted_review(_review_ref, digest):
    # Test harness stands in for independent host owner approval.
    return isinstance(digest, str) and len(digest) == 64


def test_preview_and_same_audience_import_preserve_original_source_and_timestamps(
    tmp_path,
):
    state, source, store, session, other = _source(tmp_path)
    try:
        p = store.preview_historical_import(
            principal=_identity(), session_id=session,
        )
        assert p.eligible_message_ids == (
            "original-1", "original-2", "original-3",
        )
        assert p.already_linked_ids == ()
        before = source.list_messages(session)
        receipt = store.apply_historical_import(
            principal=_identity(), session_id=session,
            message_ids=("original-1", "original-2"),
            review_ref="approved-history-batch-01", reject=False,
            independently_verify_operator_review=_trusted_review,
        )
        assert receipt.status == "committed"
        assert receipt.pending_ids == ("original-1", "original-2")
        assert source.list_messages(session) == before
        thread = store.get_or_create(owner=_identity())
        events = store.visible_events(
            thread_id=thread.thread_id, principal=_identity(),
        )
        assert {e.source_message_id for e in events} == {
            "original-1", "original-2",
        }
        assert all(e.source_session_id == session for e in events)
        assert store.visible_events(
            thread_id=thread.thread_id,
            principal=_identity("discord:private"),
        ) == ()
        replay = store.apply_historical_import(
            principal=_identity(), session_id=session,
            message_ids=("original-1", "original-2"),
            review_ref="approved-history-batch-01", reject=False,
            independently_verify_operator_review=_trusted_review,
        )
        assert replay == receipt
    finally:
        source.close()


def test_explicit_partial_rollback_removes_only_batch_created_links(tmp_path):
    state, source, store, session, other = _source(tmp_path)
    try:
        thread = store.get_or_create(owner=_identity())
        store.link_message(
            thread_id=thread.thread_id, source_message_id="original-3",
            principal=_identity(),
        )
        receipt = store.apply_historical_import(
            principal=_identity(), session_id=session,
            message_ids=("original-1", "original-2", "original-3"),
            review_ref="approved-history-batch-02", reject=False,
            independently_verify_operator_review=_trusted_review,
        )
        assert receipt.added_ids == ("original-1", "original-2")
        assert "original-3" not in receipt.added_ids
        one = store.rollback_historical_import(
            principal=_identity(), review_ref="approved-history-batch-02",
            message_ids=("original-1",),
            independently_verify_operator_review=_trusted_review,
        )
        assert one.status == "partially_rolled_back"
        assert one.pending_ids == ("original-2",)
        done = store.rollback_historical_import(
            principal=_identity(), review_ref="approved-history-batch-02",
            message_ids=("original-2",),
            independently_verify_operator_review=_trusted_review,
        )
        assert done.status == "rolled_back"
        assert done.pending_ids == ()
        events = store.visible_events(
            thread_id=thread.thread_id, principal=_identity(),
        )
        assert [e.source_message_id for e in events] == ["original-3"]
        with pytest.raises(PermissionError, match="preexisting"):
            store.rollback_historical_import(
                principal=_identity(), review_ref="approved-history-batch-02",
                message_ids=("original-3",),
                independently_verify_operator_review=_trusted_review,
            )
    finally:
        source.close()


def test_reject_and_foreign_audience_fail_closed_without_source_edits(tmp_path):
    state, source, store, session, other = _source(tmp_path)
    try:
        before = source.list_messages(session)
        with pytest.raises(PermissionError, match="audience"):
            store.preview_historical_import(
                principal=_identity(), session_id=other,
            )
        with pytest.raises(LookupError, match="exact reviewed source"):
            store.apply_historical_import(
                principal=_identity(), session_id=session,
                message_ids=("original-1", "private-foreign"),
                review_ref="approved-history-batch-03", reject=False,
                independently_verify_operator_review=_trusted_review,
            )
        rejected = store.apply_historical_import(
            principal=_identity(), session_id=session,
            message_ids=("original-1",), review_ref="approved-history-batch-04",
            reject=True, independently_verify_operator_review=_trusted_review,
        )
        assert rejected.status == "rejected"
        assert rejected.added_ids == ()
        assert source.list_messages(session) == before
        with pytest.raises(PermissionError, match="different sources"):
            store.apply_historical_import(
                principal=_identity(), session_id=session,
                message_ids=("original-2",), review_ref="approved-history-batch-04",
                reject=True, independently_verify_operator_review=_trusted_review,
            )
    finally:
        source.close()


def test_operator_review_required_at_each_mutating_boundary(tmp_path):
    state, source, store, session, other = _source(tmp_path)
    try:
        with pytest.raises(PermissionError, match="independent"):
            store.apply_historical_import(
                principal=_identity(), session_id=session,
                message_ids=("original-1",),
                review_ref="approved-history-batch-05", reject=False,
                independently_verify_operator_review=lambda *_: False,
            )
        with closing(sqlite3.connect(state)) as db:
            assert db.execute(
                "SELECT COUNT(*) FROM lifelong_historical_import"
            ).fetchone()[0] == 0
    finally:
        source.close()
