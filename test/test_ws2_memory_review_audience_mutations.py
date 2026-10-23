"""Deferred Phase 06 original-audience mutation authorization regressions.

Synthetic canonical SQLite, no live records, tests authored but not run.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.platform.application.memory_review import MemoryReviewService
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.social.principals import local_sparks_principal
from sofia.social.store import SocialSessionStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)


def _review_setup(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    messages = ConversationStore(path)
    candidates = DurableMemoryCandidateStore(path)
    social = SocialSessionStore(path)
    reviewer = MemoryReviewService(
        conversation_store=messages, candidate_store=candidates,
        state_path=path,
    )
    local = local_sparks_principal()
    foreign = local_sparks_principal("discord:dm:synthetic")
    return messages, candidates, social, reviewer, local, foreign


def _candidate(messages, social, reviewer, principal, index, content):
    session = messages.create_session()
    social.bind(session_id=session.id, principal=principal)
    original = ConversationMessage(
        id=f"original:audience:{index}", session_id=session.id,
        role=ConversationRole.USER, content=content,
        created_at=NOW + timedelta(seconds=index),
    )
    messages.save(original)
    candidate = reviewer.propose(
        session_id=session.id, message_ids=(original.id,),
        content=original.content, created_at=original.created_at,
        candidate_id=uuid4(),
    )
    return candidate.candidate_id


def test_foreign_private_audience_cannot_reject_or_expire_legacy_review_candidate(
    tmp_path,
):
    messages, candidates, social, review, local, foreign = _review_setup(tmp_path)
    try:
        remote_id = _candidate(
            messages, social, review, foreign, 1, "I prefer original blue trains",
        )
        with pytest.raises(PermissionError, match="outside current"):
            review.reject(remote_id, approved_by=local)
        with pytest.raises(PermissionError, match="outside current"):
            review.set_expiration(
                remote_id, expires_at=NOW + timedelta(days=2),
                reason="synthetic review", approved_by=local,
            )
        assert candidates.status(remote_id) is CandidateStatus.PROPOSED
        review.reject(remote_id, approved_by=foreign)
        assert candidates.status(remote_id) is CandidateStatus.REJECTED
    finally:
        candidates.close()
        messages.close()


def test_other_audience_cannot_revoke_a_promoted_candidate(tmp_path):
    messages, candidates, social, review, local, foreign = _review_setup(tmp_path)
    try:
        remote_id = _candidate(
            messages, social, review, foreign, 2,
            "I prefer regional passenger trains",
        )
        review.promote(remote_id, approved_by=foreign)
        assert candidates.status(remote_id) is CandidateStatus.PROMOTED
        with pytest.raises(PermissionError, match="outside current"):
            review.revoke(remote_id, approved_by=local)
        assert candidates.status(remote_id) is CandidateStatus.PROMOTED
        review.revoke(remote_id, approved_by=foreign)
        assert candidates.status(remote_id) is CandidateStatus.REVOKED
    finally:
        candidates.close()
        messages.close()


def test_correction_link_requires_current_scope_for_both_originals(tmp_path):
    messages, candidates, social, review, local, foreign = _review_setup(tmp_path)
    try:
        old_id = _candidate(
            messages, social, review, foreign, 3,
            "I prefer original blue regional trains",
        )
        review.promote(old_id, approved_by=foreign)
        replacement_id = _candidate(
            messages, social, review, local, 4,
            "Actually, I prefer the green regional trains",
        )
        with pytest.raises(PermissionError, match="outside current"):
            review.link_correction(
                replacement_id, old_id, approved_by=local,
            )
        assert candidates.status(old_id) is CandidateStatus.PROMOTED
        assert candidates.status(replacement_id) is CandidateStatus.PROPOSED
    finally:
        candidates.close()
        messages.close()
