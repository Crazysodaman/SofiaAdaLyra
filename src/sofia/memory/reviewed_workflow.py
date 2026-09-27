"""High-level reviewed-memory workflow built on exact conversation originals.

This service deliberately requires callers to identify the exact source
messages. It does not let model text silently promote itself into memory.
"""
from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4

from sofia.memory.conversation_originals import ConversationOriginalRetriever, OriginalRetrievalRequest
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.social.store import SocialSessionStore


class ReviewedMemoryWorkflow:
    def __init__(
        self,
        originals: ConversationOriginalRetriever,
        candidates: DurableMemoryCandidateStore,
        social: SocialSessionStore | None = None,
    ) -> None:
        if not isinstance(originals, ConversationOriginalRetriever):
            raise TypeError("originals must be ConversationOriginalRetriever")
        if not isinstance(candidates, DurableMemoryCandidateStore):
            raise TypeError("candidates must be DurableMemoryCandidateStore")
        if social is not None and not isinstance(social, SocialSessionStore):
            raise TypeError("social must be SocialSessionStore or None")
        self._originals=originals
        self._candidates=candidates
        self._social=social

    def propose_from_messages(self, *, session_id: str, message_ids: tuple[str, ...],
                              content: str, created_at: datetime,
                              candidate_id: UUID | None = None) -> MemoryCandidate:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be nonempty")
        if not isinstance(created_at, datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        principal=(
            None
            if self._social is None
            else self._social.get(session_id)
        )
        if self._social is not None and principal is None:
            raise PermissionError(
                "reviewed memory requires an authenticated principal-bound session"
            )
        projection=self._originals.retrieve(OriginalRetrievalRequest(session_id,message_ids,2**31-1))
        if projection.missing_ids:
            raise LookupError("all requested source messages must exist in the authorized session")
        if projection.omitted_ids:
            raise RuntimeError("source retrieval unexpectedly omitted evidence")
        candidate=MemoryCandidate(
            candidate_id or uuid4(),
            content,
            projection.selected,
            created_at,
            principal_id=(
                None if principal is None else principal.principal_id
            ),
            audience_id=(
                None if principal is None else principal.audience_id
            ),
        )
        self._candidates.propose(candidate)
        return candidate
