from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sofia.conversation.store import ConversationStore
from sofia.memory.conversation_originals import ConversationOriginalRetriever
from sofia.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.reviewed_workflow import ReviewedMemoryWorkflow
from sofia.social.store import SocialSessionStore


class MemoryReviewService:
    """Application-owned reviewed-memory boundary for authenticated sessions."""

    def __init__(
        self,
        *,
        conversation_store: ConversationStore,
        candidate_store: DurableMemoryCandidateStore,
        state_path,
    ) -> None:
        if not isinstance(conversation_store, ConversationStore):
            raise TypeError("conversation_store must be a ConversationStore")
        if not isinstance(candidate_store, DurableMemoryCandidateStore):
            raise TypeError("candidate_store must be DurableMemoryCandidateStore")
        self._candidates = candidate_store
        self._workflow = ReviewedMemoryWorkflow(
            ConversationOriginalRetriever(conversation_store),
            candidate_store,
            SocialSessionStore(state_path),
        )

    def propose(
        self,
        *,
        session_id: str,
        message_ids: tuple[str, ...],
        content: str,
        created_at: datetime,
        candidate_id: UUID | None = None,
    ) -> MemoryCandidate:
        return self._workflow.propose_from_messages(
            session_id=session_id,
            message_ids=message_ids,
            content=content,
            created_at=created_at,
            candidate_id=candidate_id,
        )

    def promote(
        self,
        candidate_id: UUID,
        *,
        approved_by: str,
    ) -> None:
        if approved_by != "Sparks":
            raise PermissionError("memory promotion requires Sparks review")
        self._candidates.promote(candidate_id)

    def reject(
        self,
        candidate_id: UUID,
        *,
        approved_by: str,
    ) -> None:
        if approved_by != "Sparks":
            raise PermissionError("memory rejection requires Sparks review")
        self._candidates.reject(candidate_id)

    def revoke(
        self,
        candidate_id: UUID,
        *,
        approved_by: str,
    ) -> None:
        if approved_by != "Sparks":
            raise PermissionError("memory revocation requires Sparks review")
        self._candidates.revoke(candidate_id)

    def status(self, candidate_id: UUID) -> CandidateStatus | None:
        return self._candidates.status(candidate_id)

    def get(self, candidate_id: UUID) -> MemoryCandidate | None:
        return self._candidates.get(candidate_id)
