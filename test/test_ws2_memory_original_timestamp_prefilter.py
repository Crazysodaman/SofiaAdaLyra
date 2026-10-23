"""Deferred retrieval candidate rejection for changed original timestamps.

Only isolated canonical SQLite fixture data. No promoted real memories are
rewritten and no tests are run during the coding phase.
"""
from datetime import timedelta
import sqlite3

from sofia.core.memory.provenance import CandidateStatus
from sofia.core.social.principals import local_sparks_principal
from test.test_memory_review_source_revalidation import _setup


def test_changed_original_timestamp_is_filtered_before_relevance_ranking(
    tmp_path,
):
    state, messages, candidates, session, source, review, candidate = _setup(
        tmp_path,
    )
    try:
        principal = local_sparks_principal()
        review.promote(candidate.candidate_id, approved_by=principal)
        assert candidates.is_recall_eligible(candidate.candidate_id)
        assert tuple(candidates.iter_promoted_summaries(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
        )) == ((candidate.candidate_id, candidate.content),)

        # The original user event time has been changed in the canonical
        # source; stored candidate provenance remains immutable. The
        # preliminary relevance scan must now discard it, not merely reject
        # it after it consumes a limited top-N relevance slot.
        altered = source.created_at + timedelta(days=1)
        with sqlite3.connect(state) as db:
            db.execute(
                "UPDATE conversation_messages SET created_at=? WHERE id=?",
                (altered.isoformat(), source.id),
            )
        assert candidates.is_recall_eligible(candidate.candidate_id) is False
        assert tuple(candidates.iter_promoted_summaries(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
        )) == ()
        assert candidates.status(candidate.candidate_id) is CandidateStatus.PROMOTED
    finally:
        candidates.close()
        messages.close()
