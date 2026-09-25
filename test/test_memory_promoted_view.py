from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.memory.promoted_view import PromotedMemoryView
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.retrieval_projection import SourceMessage


def item(content, mid):
    src = SourceMessage(mid, "s1", "user", content, datetime.now(timezone.utc), 0)
    return MemoryCandidate(uuid4(), content, (src,), datetime.now(timezone.utc))


def test_only_promoted_memory_is_visible(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "mem.db")
    view = PromotedMemoryView(store)
    proposed = item("old", "m1")
    store.propose(proposed)
    assert view.get(proposed.candidate_id) is None
    store.promote(proposed.candidate_id)
    assert view.get(proposed.candidate_id) == proposed
    store.close()


def test_revoked_memory_disappears(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "mem.db")
    view = PromotedMemoryView(store)
    memory = item("old", "m1")
    store.propose(memory); store.promote(memory.candidate_id); store.revoke(memory.candidate_id)
    assert view.get(memory.candidate_id) is None
    store.close()


def test_supersession_requires_promoted_replacement(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "mem.db")
    view = PromotedMemoryView(store)
    old, new = item("old", "m1"), item("new", "m2")
    store.propose(old); store.promote(old.candidate_id); store.propose(new)
    with pytest.raises(ValueError):
        view.supersede(old.candidate_id, new.candidate_id)
    assert view.get(old.candidate_id) == old
    store.close()


def test_supersession_hides_old_and_returns_new(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "mem.db")
    view = PromotedMemoryView(store)
    old, new = item("old", "m1"), item("new", "m2")
    for memory in (old, new):
        store.propose(memory); store.promote(memory.candidate_id)
    assert view.supersede(old.candidate_id, new.candidate_id) == new
    assert view.get(old.candidate_id) is None
    assert view.get(new.candidate_id) == new
    store.close()
