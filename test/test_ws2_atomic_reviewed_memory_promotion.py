"""Deferred final-writer original evidence guard for reviewed memory promotion.

Simulates an independently changed source *after* application review and
*before* the candidate store's SQLite promotion. No tests run yet.
"""
from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest

from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.memory.provenance import CandidateStatus
from sofia.social.principals import local_sparks_principal
from test.test_memory_review_source_revalidation import _setup


@pytest.mark.parametrize("mutation", ("delete", "replace_content", "rebind", "move_time"))
def test_reviewed_memory_rechecks_original_at_final_promotion(
    tmp_path, monkeypatch, mutation,
):
    state, messages, candidates, session, source, review, pending = _setup(
        tmp_path,
    )
    actual = candidates.promote

    def mutate_after_review(candidate_id):
        with sqlite3.connect(state) as db:
            if mutation == "delete":
                db.execute(
                    "DELETE FROM conversation_messages WHERE id=?",
                    (source.id,),
                )
            elif mutation == "replace_content":
                db.execute(
                    "UPDATE conversation_messages SET content=? WHERE id=?",
                    ("synthetically changed behind reviewer", source.id),
                )
            elif mutation == "rebind":
                db.execute(
                    "UPDATE social_session_principal SET audience_id=? "
                    "WHERE session_id=?",
                    ("discord:dm:foreign", session.id),
                )
            else:
                db.execute(
                    "UPDATE conversation_messages SET created_at=? WHERE id=?",
                    ((source.created_at + timedelta(hours=2)).isoformat(), source.id),
                )
        return actual(candidate_id)

    monkeypatch.setattr(candidates, "promote", mutate_after_review)
    try:
        with pytest.raises(PermissionError, match="reviewed memory"):
            review.promote(
                pending.candidate_id, approved_by=local_sparks_principal(),
            )
        assert candidates.status(pending.candidate_id) is CandidateStatus.PROPOSED
        with sqlite3.connect(state) as db:
            assert db.execute(
                "SELECT COUNT(*) FROM memory_candidate_source_review "
                "WHERE candidate_id=?", (str(pending.candidate_id),),
            ).fetchone() == (1,)
    finally:
        candidates.close()
        messages.close()


def test_atomic_correction_never_revokes_old_fact_for_stale_new_source(
    tmp_path, monkeypatch,
):
    state, messages, candidates, session, old_source, review, original = _setup(
        tmp_path,
    )
    principal = local_sparks_principal()
    try:
        review.promote(original.candidate_id, approved_by=principal)
        correction_original = ConversationMessage(
            id="reviewed:new-source", session_id=session.id,
            role=ConversationRole.USER,
            content="Actually, Gaia now uses a different verified configuration",
            created_at=old_source.created_at + timedelta(seconds=1),
        )
        messages.save(correction_original)
        replacement = review.propose(
            session_id=session.id,
            message_ids=(correction_original.id,),
            content="Gaia now uses the reviewed new configuration",
            created_at=correction_original.created_at, candidate_id=uuid4(),
        )
        review.link_correction(
            replacement.candidate_id, original.candidate_id,
            approved_by=principal,
        )
        actual = candidates.promote

        def delete_replacement_before_promotion(candidate_id):
            with sqlite3.connect(state) as db:
                db.execute(
                    "DELETE FROM conversation_messages WHERE id=?",
                    (correction_original.id,),
                )
            return actual(candidate_id)

        monkeypatch.setattr(
            candidates, "promote", delete_replacement_before_promotion,
        )
        with pytest.raises(PermissionError, match="reviewed memory"):
            review.promote(replacement.candidate_id, approved_by=principal)
        assert candidates.status(original.candidate_id) is CandidateStatus.PROMOTED
        assert candidates.status(replacement.candidate_id) is CandidateStatus.PROPOSED
    finally:
        candidates.close()
        messages.close()
