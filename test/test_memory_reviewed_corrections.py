"""Deferred end-to-end reviewed correction, provenance and restart contracts."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.memory.originals import SourceMessage
from sofia.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.system import MemorySystem
from sofia.social.principals import local_sparks_principal


NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)


def _candidate(text, index, *, audience="local:text"):
    created = NOW + timedelta(minutes=index)
    return MemoryCandidate(
        candidate_id=uuid4(),
        content=text,
        sources=(SourceMessage(
            f"original-message-{index}", f"original-session-{index}",
            "user", f"exact correction evidence {index}",
            created, 0,
        ),),
        created_at=created,
        principal_id="person:sparks",
        audience_id=audience,
    )


def test_reviewed_memory_correction_supersedes_in_one_transaction_and_survives_restart(tmp_path):
    state = tmp_path / "sofia.db"
    store = DurableMemoryCandidateStore(state)
    original = _candidate("Sparks prefers red model trains", 1)
    corrected = _candidate("Sparks prefers blue model trains", 2)
    store.propose(original)
    store.promote(original.candidate_id)
    store.propose(corrected)

    store.link_correction(corrected.candidate_id, original.candidate_id)
    assert store.status(original.candidate_id) is CandidateStatus.PROMOTED
    assert store.status(corrected.candidate_id) is CandidateStatus.PROPOSED
    assert store.correction_link(original.candidate_id) == (
        corrected.candidate_id, original.candidate_id,
    )
    store.promote(corrected.candidate_id)
    assert store.status(original.candidate_id) is CandidateStatus.REVOKED
    assert store.status(corrected.candidate_id) is CandidateStatus.PROMOTED
    store.close()

    reopened = DurableMemoryCandidateStore(state)
    try:
        assert reopened.get(original.candidate_id) == original
        assert reopened.get(corrected.candidate_id) == corrected
        recalled = MemorySystem(reopened).recall_relevant(
            "model trains", principal=local_sparks_principal(),
        )
        assert [x.id for x in recalled] == [str(corrected.candidate_id)]
        assert reopened.correction_link(corrected.candidate_id) == (
            corrected.candidate_id, original.candidate_id,
        )
    finally:
        reopened.close()


def test_correction_cannot_join_different_audiences(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "sofia.db")
    original = _candidate("Private desktop details", 1)
    replacement = _candidate(
        "Private phone details", 2, audience="mobile:private:phone",
    )
    try:
        store.propose(original)
        store.promote(original.candidate_id)
        store.propose(replacement)
        with pytest.raises(ValueError, match="same-scope"):
            store.link_correction(replacement.candidate_id, original.candidate_id)
        assert store.status(original.candidate_id) is CandidateStatus.PROMOTED
        assert store.status(replacement.candidate_id) is CandidateStatus.PROPOSED
    finally:
        store.close()


def test_rejected_or_pre_revoked_correction_cannot_partially_promote(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "sofia.db")
    original = _candidate("Old model trains hobby", 1)
    replacement = _candidate("New model trains hobby", 2)
    try:
        store.propose(original)
        store.promote(original.candidate_id)
        store.propose(replacement)
        store.link_correction(replacement.candidate_id, original.candidate_id)
        store.revoke(original.candidate_id)
        with pytest.raises(ValueError, match="promoted original"):
            store.promote(replacement.candidate_id)
        assert store.status(original.candidate_id) is CandidateStatus.REVOKED
        assert store.status(replacement.candidate_id) is CandidateStatus.PROPOSED
    finally:
        store.close()


def test_correction_duplicate_or_competing_replacement_is_rejected(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "sofia.db")
    original = _candidate("Old preference", 1)
    replacement = _candidate("Corrected preference", 2)
    other = _candidate("Another conflicting preference", 3)
    try:
        store.propose(original)
        store.promote(original.candidate_id)
        store.propose(replacement)
        store.propose(other)
        store.link_correction(replacement.candidate_id, original.candidate_id)
        store.link_correction(replacement.candidate_id, original.candidate_id)
        with pytest.raises(ValueError, match="already part"):
            store.link_correction(other.candidate_id, original.candidate_id)
    finally:
        store.close()

def test_normal_promotion_preserves_previous_error_contract(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "sofia.db")
    try:
        with pytest.raises(LookupError, match="does not exist"):
            store.promote(uuid4())
        original = _candidate("Owner's reviewed evidence", 1)
        store.propose(original)
        store.promote(original.candidate_id)
        with pytest.raises(ValueError, match="must be proposed"):
            store.promote(original.candidate_id)
        assert store.status(original.candidate_id) is CandidateStatus.PROMOTED
    finally:
        store.close()
