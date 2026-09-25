"""Source invalidation for provenance-backed memory.

If an original message is withdrawn/invalidated, any memory derived from it
must stop being cognition-visible. The source text is not silently rewritten.
"""
from __future__ import annotations
from uuid import UUID
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore


class SourceInvalidator:
    def __init__(self, store: DurableMemoryCandidateStore) -> None:
        if not isinstance(store, DurableMemoryCandidateStore):
            raise TypeError("store must be a DurableMemoryCandidateStore")
        self._store = store

    def invalidate_message(self, *, session_id: str, message_id: str) -> tuple[UUID, ...]:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be nonempty")
        if not isinstance(message_id, str) or not message_id.strip():
            raise ValueError("message_id must be nonempty")
        affected = self._store.candidate_ids_for_source(session_id=session_id, message_id=message_id)
        revoked: list[UUID] = []
        for candidate_id in affected:
            if self._store.status(candidate_id) is CandidateStatus.PROMOTED:
                self._store.revoke(candidate_id)
                revoked.append(candidate_id)
        return tuple(revoked)
