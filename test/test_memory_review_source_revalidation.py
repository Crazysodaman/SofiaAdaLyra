"""Deferred canonical source integrity at owner-reviewed MEM promotion.

No model call, runtime startup, real user memory mutation or test execution
occurs during the V18 source-coding workstream.
"""
from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

import pytest

from sofia.application.memory_review import MemoryReviewService
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.social.principals import local_sparks_principal
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.store import SocialSessionStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


NOW = datetime(2026, 10, 11, 15, 0, tzinfo=timezone.utc)


def _setup(tmp_path, *, private_owner=None):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    conversations = ConversationStore(state)
    candidates = DurableMemoryCandidateStore(state)
    social = SocialSessionStore(state)
    principal = private_owner or local_sparks_principal()
    session = conversations.create_session()
    social.bind(session_id=session.id, principal=principal)
    source = ConversationMessage(
        id=str(uuid4()), session_id=session.id, role=ConversationRole.USER,
        content="Gaia hexapod uses 18 servos", created_at=NOW,
    )
    conversations.save(source)
    review = MemoryReviewService(
        conversation_store=conversations,
        candidate_store=candidates, state_path=state,
    )
    pending = review.propose(
        session_id=session.id, message_ids=(source.id,),
        content="Gaia robot has 18 servos",
        created_at=NOW,
    )
    return state, conversations, candidates, session, source, review, pending


def test_verified_original_is_promoted_from_current_private_owner_session(tmp_path):
    state, conversations, candidates, session, source, review, pending = _setup(
        tmp_path,
    )
    try:
        review.promote(pending.candidate_id, approved_by=local_sparks_principal())
        assert candidates.status(pending.candidate_id) is CandidateStatus.PROMOTED
    finally:
        candidates.close()
        conversations.close()


def test_erased_original_cannot_be_promoted_even_with_old_candidate_copy(tmp_path):
    state, conversations, candidates, session, source, review, pending = _setup(
        tmp_path,
    )
    try:
        with sqlite3.connect(state) as db:
            db.execute("DELETE FROM conversation_messages WHERE id=?", (source.id,))
        with pytest.raises(LookupError, match="original"):
            review.promote(
                pending.candidate_id, approved_by=local_sparks_principal(),
            )
        assert candidates.status(pending.candidate_id) is CandidateStatus.PROPOSED
    finally:
        candidates.close()
        conversations.close()


def test_modified_original_content_blocks_candidate_without_losing_it(tmp_path):
    state, conversations, candidates, session, source, review, pending = _setup(
        tmp_path,
    )
    try:
        with sqlite3.connect(state) as db:
            db.execute(
                "UPDATE conversation_messages SET content=? WHERE id=?",
                ("source was tampered", source.id),
            )
        with pytest.raises(PermissionError, match="source bytes"):
            review.promote(
                pending.candidate_id, approved_by=local_sparks_principal(),
            )
        assert candidates.status(pending.candidate_id) is CandidateStatus.PROPOSED
    finally:
        candidates.close()
        conversations.close()


def test_rebound_original_audience_blocks_private_desktop_review(tmp_path):
    state, conversations, candidates, session, source, review, pending = _setup(
        tmp_path,
    )
    try:
        with sqlite3.connect(state) as db:
            db.execute(
                "UPDATE social_session_principal SET audience_id=? "
                "WHERE session_id=?",
                ("discord:private-channel", session.id),
            )
        with pytest.raises(PermissionError, match="session binding"):
            review.promote(
                pending.candidate_id, approved_by=local_sparks_principal(),
            )
        assert candidates.status(pending.candidate_id) is CandidateStatus.PROPOSED
    finally:
        candidates.close()
        conversations.close()


def test_other_private_audience_is_not_implicitly_desktop_reviewer_authority(
    tmp_path,
):
    remote = PrincipalContext(
        principal_id=local_sparks_principal().principal_id,
        audience_id="discord:private:owner",
        audience_kind=AudienceKind.PRIVATE,
        display_name="Fixture Owner",
    )
    state, conversations, candidates, session, source, review, pending = _setup(
        tmp_path, private_owner=remote,
    )
    try:
        with pytest.raises(PermissionError, match="review audience"):
            review.promote(
                pending.candidate_id, approved_by=local_sparks_principal(),
            )
        assert pending.candidate_id not in candidates.list_ids(
            principal_id=local_sparks_principal().principal_id,
            audience_id="local:text",
        )
    finally:
        candidates.close()
        conversations.close()


def test_local_review_candidate_is_listed_without_exposing_foreign_scope(tmp_path):
    state, conversations, candidates, session, source, review, pending = _setup(
        tmp_path,
    )
    try:
        assert pending.candidate_id in candidates.list_ids(
            principal_id=local_sparks_principal().principal_id,
            audience_id="local:text",
        )
        assert pending.candidate_id not in candidates.list_ids(
            principal_id=local_sparks_principal().principal_id,
            audience_id="mobile:private:another",
        )
    finally:
        candidates.close()
        conversations.close()
