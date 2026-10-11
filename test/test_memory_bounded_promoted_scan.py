"""Deferred bounded canonical promoted-memory retrieval regressions.

No synthetic data is promoted in live state; tests use temporary fixtures.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.memory.originals import SourceMessage
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.promoted_retrieval import retrieve_promoted


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _add(store, index, text, *, principal="person:sparks", audience=None):
    at = BASE + timedelta(seconds=index)
    item = MemoryCandidate(
        candidate_id=uuid4(),
        content=text,
        sources=(SourceMessage(
            f"source-{index}", "original-session", "user",
            "evidence for " + text, at, index,
        ),),
        created_at=at,
        principal_id=principal,
        audience_id=audience,
    )
    store.propose(item)
    store.promote(item.candidate_id)
    return item


def test_keyset_summary_scan_is_ordered_scope_filtered_and_bounded(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "sofia.db")
    try:
        global_item = _add(store, 1, "global model trains")
        private_item = _add(store, 2, "local model trains", audience="local:text")
        _add(store, 3, "other device model trains", audience="mobile:private:device")
        _add(store, 4, "someone else model trains", principal="person:other")
        visible = tuple(store.iter_promoted_summaries(
            principal_id="person:sparks", audience_id="local:text", batch_size=1,
        ))
        assert visible == (
            (global_item.candidate_id, global_item.content),
            (private_item.candidate_id, private_item.content),
        )
        with pytest.raises(ValueError, match="batch_size"):
            tuple(store.iter_promoted_summaries(batch_size=0))
        with pytest.raises(ValueError, match="requires principal_id"):
            tuple(store.iter_promoted_summaries(audience_id="local:text"))
    finally:
        store.close()


def test_long_memory_scan_ranks_late_relevant_item_without_list_ids(tmp_path, monkeypatch):
    store = DurableMemoryCandidateStore(tmp_path / "sofia.db")
    try:
        for index in range(265):
            _add(store, index, f"unrelated evidence {index}")
        early = _add(store, 265, "trains preference")
        for index in range(266, 535):
            _add(store, index, f"unrelated archive {index}")
        late = _add(store, 535, "model trains are my favorite")
        _add(store, 536, "unrelated last record")
        # The old source path materialized every candidate ID then loaded
        # original source rows to rank. The new source must not call it.
        def refuse_unbounded_id_materialization(**_kwargs):
            raise AssertionError("retrieval must use bounded keyset summaries")
        monkeypatch.setattr(store, "list_ids", refuse_unbounded_id_materialization)

        out = retrieve_promoted(
            store, "model trains", limit=2, budget_characters=200,
            principal_id="person:sparks", audience_id="local:text",
        )
        assert [m.candidate_id for m in out.selected] == [
            late.candidate_id, early.candidate_id,
        ]
    finally:
        store.close()
