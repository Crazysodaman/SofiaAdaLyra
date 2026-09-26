from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.retrieval_projection import SourceMessage


def candidate():
    source = SourceMessage(
        "m1", "s1", "user", "  exact source  ",
        datetime.now(timezone.utc), 7,
    )
    return MemoryCandidate(
        uuid4(), "derived claim", (source,), datetime.now(timezone.utc)
    )


def test_candidate_and_exact_provenance_survive_restart(tmp_path):
    path = tmp_path / "memory.db"
    item = candidate()
    first = DurableMemoryCandidateStore(path)
    first.propose(item)
    first.close()

    reopened = DurableMemoryCandidateStore(path)
    loaded = reopened.get(item.candidate_id)
    assert loaded == item
    assert loaded.sources[0].content == "  exact source  "
    assert loaded.sources[0].position == 7
    assert reopened.status(item.candidate_id) is CandidateStatus.PROPOSED
    reopened.close()


def test_promotion_and_revocation_survive_restart(tmp_path):
    path = tmp_path / "memory.db"
    item = candidate()
    store = DurableMemoryCandidateStore(path)
    store.propose(item)
    store.promote(item.candidate_id)
    store.close()

    reopened = DurableMemoryCandidateStore(path)
    assert reopened.status(item.candidate_id) is CandidateStatus.PROMOTED
    reopened.revoke(item.candidate_id)
    reopened.close()

    final = DurableMemoryCandidateStore(path)
    assert final.status(item.candidate_id) is CandidateStatus.REVOKED
    final.close()


def test_rejection_is_terminal(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "memory.db")
    item = candidate()
    store.propose(item)
    store.reject(item.candidate_id)
    with pytest.raises(ValueError):
        store.promote(item.candidate_id)
    store.close()


def test_duplicate_id_does_not_replace_provenance(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "memory.db")
    item = candidate()
    store.propose(item)
    replacement = MemoryCandidate(
        item.candidate_id, "different claim", item.sources, item.created_at
    )
    with pytest.raises(ValueError):
        store.propose(replacement)
    assert store.get(item.candidate_id).content == "derived claim"
    store.close()


def test_missing_candidate_transition_fails(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "memory.db")
    with pytest.raises(LookupError):
        store.promote(uuid4())
    store.close()


def test_in_memory_database_is_rejected():
    with pytest.raises(ValueError):
        DurableMemoryCandidateStore(":memory:")


def test_reviewed_store_can_be_read_from_worker_thread(tmp_path):
    path = tmp_path / "memory.db"
    item = candidate()
    store = DurableMemoryCandidateStore(path)
    store.propose(item)
    store.promote(item.candidate_id)

    with ThreadPoolExecutor(max_workers=1) as executor:
        ids = executor.submit(
            store.list_ids,
            status=CandidateStatus.PROMOTED,
        ).result(timeout=5)

    assert ids == (item.candidate_id,)
    store.close()
