"""Deferred canonical reviewed temporal memory acceptance regressions.

No tests are executed during the V18 coding workstream.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.application.memory_review import MemoryReviewService
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.promoted_retrieval import retrieve_promoted
from sofia.memory.system import MemorySystem
from sofia.social.principals import local_sparks_principal
from test.test_memory_reviewed_corrections import _candidate


def _reviewed(tmp_path):
    path = tmp_path / "sofia.db"
    store = DurableMemoryCandidateStore(path)
    candidate = _candidate("A temporary Gaia motor calibration", 1)
    store.propose(candidate)
    store.promote(candidate.candidate_id)
    return path, store, candidate


def test_reviewed_expiration_hides_fact_but_preserves_promoted_sources(tmp_path):
    path, store, candidate = _reviewed(tmp_path)
    now = datetime.now(timezone.utc)
    principal = local_sparks_principal()
    try:
        assert MemorySystem(store).recall_relevant(
            "Gaia motor", principal=principal,
        )
        store.set_expiration(
            candidate.candidate_id,
            expires_at=now - timedelta(seconds=1),
            reviewed_by=principal.principal_id,
            reason="Calibration was only valid for the prior build",
        )
        assert store.status(candidate.candidate_id) is CandidateStatus.PROMOTED
        assert store.get(candidate.candidate_id) == candidate
        assert store.is_recall_eligible(candidate.candidate_id) is False
        assert tuple(store.iter_promoted_summaries(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            batch_size=1,
        )) == ()
        assert MemorySystem(store).recall_relevant(
            "Gaia motor", principal=principal,
        ) == ()
        assert retrieve_promoted(
            store, "Gaia motor",
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
        ).selected == ()
    finally:
        store.close()

    reopened = DurableMemoryCandidateStore(path)
    try:
        assert reopened.expiration(candidate.candidate_id) == now - timedelta(seconds=1)
        assert reopened.is_recall_eligible(candidate.candidate_id) is False
        assert reopened.get(candidate.candidate_id) == candidate
    finally:
        reopened.close()


def test_owner_can_review_future_deadline_then_clear_it_without_erasing_history(tmp_path):
    path, store, candidate = _reviewed(tmp_path)
    principal = local_sparks_principal()
    future = datetime.now(timezone.utc) + timedelta(days=7)
    try:
        store.set_expiration(
            candidate.candidate_id, expires_at=future,
            reviewed_by=principal.principal_id,
            reason="Check again next week",
        )
        assert store.is_recall_eligible(candidate.candidate_id)
        store.set_expiration(
            candidate.candidate_id, expires_at=None,
            reviewed_by=principal.principal_id,
            reason="Calibration confirmed permanent",
        )
        assert store.expiration(candidate.candidate_id) is None
        with store._lock:
            events = store._require_db().execute(
                "SELECT previous_expires_at,expires_at,reason "
                "FROM memory_candidate_validity_event WHERE candidate_id=? "
                "ORDER BY event_id", (str(candidate.candidate_id),),
            ).fetchall()
        assert len(events) == 2
        assert events[0][0] is None and events[0][1] == future.isoformat()
        assert events[1][0] == future.isoformat() and events[1][1] is None
        assert store.is_recall_eligible(candidate.candidate_id)
    finally:
        store.close()


def test_temporal_review_does_not_accept_other_owner_or_unreviewed_proposal(tmp_path):
    path, store, candidate = _reviewed(tmp_path)
    future = datetime.now(timezone.utc) + timedelta(days=1)
    proposal = _candidate("A proposed temporary system setting", 2)
    store.propose(proposal)
    try:
        with pytest.raises(PermissionError, match="owner"):
            store.set_expiration(
                candidate.candidate_id, expires_at=future,
                reviewed_by="person:other", reason="Not my authority",
            )
        with pytest.raises(ValueError, match="promoted"):
            store.set_expiration(
                proposal.candidate_id, expires_at=future,
                reviewed_by="person:sparks", reason="Not reviewed yet",
            )
        with pytest.raises(ValueError, match="timezone-aware"):
            store.set_expiration(
                candidate.candidate_id, expires_at=datetime(2026, 10, 11),
                reviewed_by="person:sparks", reason="Missing timezone",
            )
        with pytest.raises(ValueError, match="reviewer reason"):
            store.set_expiration(
                candidate.candidate_id, expires_at=future,
                reviewed_by="person:sparks", reason="",
            )
        assert store.expiration(candidate.candidate_id) is None
        assert store.is_recall_eligible(candidate.candidate_id)
    finally:
        store.close()


def test_last_moment_expiry_is_rechecked_even_after_ranked_selection(tmp_path, monkeypatch):
    _, store, candidate = _reviewed(tmp_path)
    principal = local_sparks_principal()
    original = store.get
    called = 0

    def set_deadline_after_retrieval(candidate_id):
        nonlocal called
        called += 1
        record = original(candidate_id)
        if called >= 2:
            store.set_expiration(
                candidate_id,
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                reviewed_by=principal.principal_id,
                reason="Fact expired while projection was being composed",
            )
        return record

    monkeypatch.setattr(store, "get", set_deadline_after_retrieval)
    try:
        assert MemorySystem(store).recall_relevant(
            "Gaia motor", principal=principal,
        ) == ()
    finally:
        store.close()
