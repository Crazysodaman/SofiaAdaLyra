from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.memory.provenance import CandidateStatus, MemoryCandidate, MemoryCandidateRegistry
from sofia.memory.retrieval_projection import SourceMessage


def source(mid="m1", session="s1"):
    return SourceMessage(mid, session, "user", "exact source", datetime.now(timezone.utc), 0)


def candidate(*sources):
    return MemoryCandidate(uuid4(), "derived claim", tuple(sources or (source(),)), datetime.now(timezone.utc))


def test_candidate_requires_exact_source():
    with pytest.raises(ValueError):
        MemoryCandidate(uuid4(), "claim", (), datetime.now(timezone.utc))


def test_candidate_cannot_silently_combine_sessions():
    with pytest.raises(ValueError):
        candidate(source("a", "s1"), source("b", "s2"))


def test_propose_promote_revoke_lifecycle():
    registry = MemoryCandidateRegistry()
    item = candidate()
    registry.propose(item)
    assert registry.status(item.candidate_id) is CandidateStatus.PROPOSED
    registry.promote(item.candidate_id)
    assert registry.status(item.candidate_id) is CandidateStatus.PROMOTED
    registry.revoke(item.candidate_id)
    assert registry.status(item.candidate_id) is CandidateStatus.REVOKED


def test_rejected_candidate_cannot_be_promoted():
    registry = MemoryCandidateRegistry()
    item = candidate()
    registry.propose(item)
    registry.reject(item.candidate_id)
    assert registry.status(item.candidate_id) is CandidateStatus.REJECTED
    with pytest.raises(ValueError):
        registry.promote(item.candidate_id)


def test_duplicate_candidate_id_fails_closed():
    registry = MemoryCandidateRegistry()
    item = candidate()
    registry.propose(item)
    with pytest.raises(ValueError):
        registry.propose(item)
