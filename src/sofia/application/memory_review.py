from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sofia.conversation.store import ConversationStore
from sofia.memory.conversation_originals import ConversationOriginalRetriever
from sofia.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.reviewed_workflow import ReviewedMemoryWorkflow
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID
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

    @staticmethod
    def _require_sparks_reviewer(
        approved_by: PrincipalContext,
    ) -> None:
        if not isinstance(approved_by, PrincipalContext):
            raise TypeError(
                "memory review requires an authenticated PrincipalContext"
            )
        if (
            approved_by.principal_id != SPARKS_PRINCIPAL_ID
            or approved_by.audience_kind is not AudienceKind.PRIVATE
        ):
            raise PermissionError(
                "memory review requires authenticated private Sparks review"
            )

    def promote(
        self,
        candidate_id: UUID,
        *,
        approved_by: PrincipalContext,
    ) -> None:
        self._require_sparks_reviewer(approved_by)
        self._candidates.promote(candidate_id)

    def reject(
        self,
        candidate_id: UUID,
        *,
        approved_by: PrincipalContext,
    ) -> None:
        self._require_sparks_reviewer(approved_by)
        self._candidates.reject(candidate_id)

    def revoke(
        self,
        candidate_id: UUID,
        *,
        approved_by: PrincipalContext,
    ) -> None:
        self._require_sparks_reviewer(approved_by)
        self._candidates.revoke(candidate_id)

    def status(self, candidate_id: UUID) -> CandidateStatus | None:
        return self._candidates.status(candidate_id)
