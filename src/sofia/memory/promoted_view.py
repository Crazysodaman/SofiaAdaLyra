"""Current promoted-memory view and explicit supersession for PKG-MEM."""
from __future__ import annotations

from uuid import UUID

from sofia.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore


class PromotedMemoryView:
    """Expose only currently promoted candidates to cognition."""

    def __init__(self, store: DurableMemoryCandidateStore) -> None:
        if not isinstance(store, DurableMemoryCandidateStore):
            raise TypeError("store must be a DurableMemoryCandidateStore")
        self._store = store

    def get(self, candidate_id: UUID) -> MemoryCandidate | None:
        if self._store.status(candidate_id) is not CandidateStatus.PROMOTED:
            return None
        return self._store.get(candidate_id)

    def supersede(self, old_id: UUID, replacement_id: UUID) -> MemoryCandidate:
        """Atomically change the visible winner after replacement is promoted.

        The replacement must already be promoted. The old candidate is then
        revoked. This avoids a window where an unreviewed replacement becomes
        cognition-visible merely because it was proposed.
        """
        if not isinstance(old_id, UUID) or not isinstance(replacement_id, UUID):
            raise TypeError("candidate IDs must be UUIDs")
        if old_id == replacement_id:
            raise ValueError("a memory cannot supersede itself")
        if self._store.status(old_id) is not CandidateStatus.PROMOTED:
            raise ValueError("old memory must be promoted")
        if self._store.status(replacement_id) is not CandidateStatus.PROMOTED:
            raise ValueError("replacement memory must be promoted")
        replacement = self._store.get(replacement_id)
        if replacement is None:
            raise LookupError("replacement memory does not exist")
        self._store.revoke(old_id)
        return replacement
