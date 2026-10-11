"""Deferred memory privacy regressions at final model-context projection.

An earlier eligible candidate ID is not sufficient authorization if
scope/revocation changes before the source is sent into cognition.
"""
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.memory.originals import SourceMessage
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.system import MemorySystem
from sofia.social.principals import SPARKS_PRINCIPAL_ID, local_sparks_principal


def _setup(tmp_path):
    state = tmp_path / "sofia.db"
    store = DurableMemoryCandidateStore(state)
    now = datetime.now(timezone.utc)
    candidate = MemoryCandidate(
        candidate_id=uuid4(),
        content="Artemis server configuration",
        sources=(SourceMessage(
            "origin-message", "session", "user",
            "Artemis server configuration", now, 0,
        ),),
        created_at=now,
        principal_id=SPARKS_PRINCIPAL_ID,
        audience_id="local:text",
    )
    store.propose(candidate)
    store.promote(candidate.candidate_id)
    return store, candidate


@pytest.mark.parametrize("changed_field", ("principal_id", "audience_id"))
def test_changed_memory_scope_is_blocked_before_cognitive_context(
    tmp_path, monkeypatch, changed_field,
):
    store, candidate = _setup(tmp_path)
    original_get = store.get
    seen = 0

    def concurrent_scope_change(candidate_id):
        nonlocal seen
        seen += 1
        record = original_get(candidate_id)
        # Earlier ranking and projection checks found a valid memory.
        # The final read receives different scope and must deny it.
        if seen >= 3:
            return replace(record, **{
                changed_field: (
                    "person:other" if changed_field == "principal_id"
                    else "mobile:private:other-device"
                ),
            })
        return record

    monkeypatch.setattr(store, "get", concurrent_scope_change)
    try:
        assert MemorySystem(store).recall_relevant(
            "Artemis server", principal=local_sparks_principal(),
        ) == ()
    finally:
        store.close()


def test_revocation_during_final_memory_read_is_blocked(tmp_path, monkeypatch):
    store, candidate = _setup(tmp_path)
    original_get = store.get
    seen = 0

    def revoke_during_final_get(candidate_id):
        nonlocal seen
        seen += 1
        record = original_get(candidate_id)
        if seen == 3:
            store.revoke(candidate_id)
        return record

    monkeypatch.setattr(store, "get", revoke_during_final_get)
    try:
        assert MemorySystem(store).recall_relevant(
            "Artemis server", principal=local_sparks_principal(),
        ) == ()
    finally:
        store.close()
