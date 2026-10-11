from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sofia.conversation.store import ConversationStore
from sofia.memory.originals import ConversationOriginalRetriever, OriginalRetrievalRequest
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
        self._originals = ConversationOriginalRetriever(conversation_store)
        self._social = SocialSessionStore(state_path)
        self._workflow = ReviewedMemoryWorkflow(
            self._originals, candidate_store, self._social,
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
        candidate = self._candidates.get(candidate_id)
        if candidate is None:
            raise LookupError("candidate does not exist")
        # The owner may approve only evidence in the actual current
        # authenticated review audience. Shared owner ID does not grant
        # private Android or Discord source text to the desktop panel.
        if (
            candidate.principal_id != approved_by.principal_id
            or candidate.audience_id not in (None, approved_by.audience_id)
        ):
            raise PermissionError(
                "candidate is outside the current private review audience"
            )
        if len(candidate.sources) > 64:
            raise ValueError("memory review requires at most 64 exact originals")
        original_session = candidate.sources[0].session_id
        current_binding = self._social.get(original_session)
        if (
            current_binding is None
            or current_binding.principal_id != approved_by.principal_id
            or current_binding.audience_id != approved_by.audience_id
            or current_binding.audience_kind != approved_by.audience_kind
        ):
            raise PermissionError("memory source session binding has changed")
        requested_ids = tuple(s.message_id for s in candidate.sources)
        projection = self._originals.retrieve(OriginalRetrievalRequest(
            session_id=original_session, message_ids=requested_ids,
            budget_characters=2**31 - 1,
        ))
        if projection.missing_ids or projection.omitted_ids:
            raise LookupError("reviewed memory original was removed or unavailable")
        if projection.selected != candidate.sources:
            raise PermissionError(
                "reviewed memory source bytes, role, order or timestamps changed"
            )
        # Review is authoritative only after *current* immutable original
        # evidence checks. DurableMemoryCandidateStore still owns the
        # transactional lifecycle and atomic correction/revocation.
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

    def link_correction(
        self, replacement_id: UUID, superseded_id: UUID, *,
        approved_by: PrincipalContext,
    ) -> None:
        """Stage source-linked correction; approval to promote stays separate."""
        self._require_sparks_reviewer(approved_by)
        self._candidates.link_correction(replacement_id, superseded_id)

    def set_expiration(
        self, candidate_id: UUID, *, expires_at: datetime | None,
        reason: str, approved_by: PrincipalContext,
    ) -> None:
        """Time-limit a reviewed fact; never erase or infer a new source."""
        self._require_sparks_reviewer(approved_by)
        self._candidates.set_expiration(
            candidate_id, expires_at=expires_at,
            reviewed_by=approved_by.principal_id, reason=reason,
        )

    def correction_link(self, candidate_id: UUID) -> tuple[UUID, UUID] | None:
        return self._candidates.correction_link(candidate_id)

    def status(self, candidate_id: UUID) -> CandidateStatus | None:
        return self._candidates.status(candidate_id)
