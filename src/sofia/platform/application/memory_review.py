from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sofia.core.conversation.store import ConversationStore
from sofia.core.memory.originals import ConversationOriginalRetriever, OriginalRetrievalRequest
from sofia.core.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.core.memory.provenance_store import DurableMemoryCandidateStore
from sofia.core.memory.reviewed_workflow import ReviewedMemoryWorkflow
from sofia.core.memory.ranking import MemoryRankingService, RelevanceJudgment
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import SPARKS_PRINCIPAL_ID
from sofia.core.social.store import SocialSessionStore


class MemoryReviewService:
    """Application-owned reviewed-memory boundary for authenticated sessions."""

    def __init__(
        self,
        *,
        conversation_store: ConversationStore,
        candidate_store: DurableMemoryCandidateStore,
        state_path,
        ranking_service: MemoryRankingService | None = None,
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
        self._ranking = ranking_service or MemoryRankingService(
            state_path, candidate_store,
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

    def _require_current_review_scope(
        self, candidate_id: UUID, approved_by: PrincipalContext,
    ) -> MemoryCandidate:
        """An authenticated owner is not universal cross-audience access.

        The durable candidate's original principal/audience identifies the
        authority of all lifecycle writes, not only promotions. Legacy
        principal-owned unscoped candidates retain the existing exception.
        """
        self._require_sparks_reviewer(approved_by)
        candidate = self._candidates.get(candidate_id)
        if candidate is None:
            raise LookupError("candidate does not exist")
        if (
            candidate.principal_id != approved_by.principal_id
            or candidate.audience_id not in (None, approved_by.audience_id)
        ):
            raise PermissionError(
                "memory candidate is outside current private review audience"
            )
        return candidate

    def promote(
        self,
        candidate_id: UUID,
        *,
        approved_by: PrincipalContext,
    ) -> None:
        candidate = self._require_current_review_scope(
            candidate_id, approved_by,
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
        # A reviewed candidate carries this source-binding guard into
        # future model-context reads. Erasing or rebinding the original
        # afterwards makes recall fail closed without erasing the audit
        # record or rewriting a memory candidate.
        self._candidates.require_current_original_at_recall(
            candidate_id,
            session_id=original_session,
            principal_id=current_binding.principal_id,
            audience_id=current_binding.audience_id,
            audience_kind=current_binding.audience_kind.value,
        )
        # DurableMemoryCandidateStore still owns the atomic promotion and
        # correction/revocation lifecycle.
        self._candidates.promote(candidate_id)

    def reject(
        self,
        candidate_id: UUID,
        *,
        approved_by: PrincipalContext,
    ) -> None:
        self._require_current_review_scope(candidate_id, approved_by)
        self._candidates.reject(candidate_id)

    def revoke(
        self,
        candidate_id: UUID,
        *,
        approved_by: PrincipalContext,
    ) -> None:
        self._require_current_review_scope(candidate_id, approved_by)
        self._candidates.revoke(candidate_id)
        self._invalidate_ranking(candidate_id, "owner revoked canonical memory")

    def link_correction(
        self, replacement_id: UUID, superseded_id: UUID, *,
        approved_by: PrincipalContext,
    ) -> None:
        """Stage source-linked correction; approval to promote stays separate."""
        self._require_current_review_scope(replacement_id, approved_by)
        self._require_current_review_scope(superseded_id, approved_by)
        self._candidates.link_correction(replacement_id, superseded_id)
        self._invalidate_ranking(
            superseded_id, f"owner linked correction {replacement_id}",
        )

    def set_expiration(
        self, candidate_id: UUID, *, expires_at: datetime | None,
        reason: str, approved_by: PrincipalContext,
    ) -> None:
        """Time-limit a reviewed fact; never erase or infer a new source."""
        self._require_current_review_scope(candidate_id, approved_by)
        self._candidates.set_expiration(
            candidate_id, expires_at=expires_at,
            reviewed_by=approved_by.principal_id, reason=reason,
        )

    def correction_link(self, candidate_id: UUID) -> tuple[UUID, UUID] | None:
        return self._candidates.correction_link(candidate_id)

    def status(self, candidate_id: UUID) -> CandidateStatus | None:
        return self._candidates.status(candidate_id)

    def _invalidate_ranking(self, candidate_id: UUID, reason: str) -> None:
        """Invalidate derived influence when the optional projection exists.

        Minimal compatibility fixtures predating the projection construct this
        service without running ``__init__``. Production composition always
        supplies the canonical service; absence grants no learned influence.
        """
        ranking = getattr(self, "_ranking", None)
        if ranking is not None:
            ranking.invalidate_candidate(
                candidate_id, reason=reason, at=datetime.now(timezone.utc),
            )

    def record_relevance_feedback(
        self, *, retrieval_id: str, candidate_id: UUID, feedback: str,
        approved_by: PrincipalContext, at: datetime,
        preferred_over_id: UUID | None = None,
    ) -> str:
        """Store one explicit judgment for a previously eligible retrieval."""
        self._require_current_review_scope(candidate_id, approved_by)
        try:
            judgment = RelevanceJudgment(feedback)
        except ValueError as exc:
            raise ValueError("feedback must be relevant, not_relevant, correction, or unknown") from exc
        return self._ranking.record_judgment(
            retrieval_id=retrieval_id, candidate_id=candidate_id,
            judgment=judgment, principal=approved_by, at=at,
            preferred_over_id=preferred_over_id,
        )

    def train_relevance_ranker(
        self, *, approved_by: PrincipalContext, at: datetime,
    ) -> str | None:
        """Build a bounded scoped scorer; this grants no recall eligibility."""
        self._require_sparks_reviewer(approved_by)
        return self._ranking.train(principal=approved_by, at=at)

    def record_ranking_truth_review(
        self, *, retrieval_id: str, candidate_id: UUID,
        approved_by: PrincipalContext, at: datetime,
        timeline_truth: str, correction_truth: str, source_accuracy: str,
    ) -> str:
        """Record explicit held-out evaluation labels, not canonical facts."""
        self._require_sparks_reviewer(approved_by)
        return self._ranking.record_truth_review(
            retrieval_id=retrieval_id, candidate_id=candidate_id,
            principal=approved_by, at=at,
            timeline_truth=timeline_truth,
            correction_truth=correction_truth,
            source_accuracy=source_accuracy,
        )

    def evaluate_relevance_ranker(
        self, *, approved_by: PrincipalContext, trained_before: datetime,
    ):
        """Evaluate only prospectively recorded, audience-scoped reviews."""
        self._require_sparks_reviewer(approved_by)
        return self._ranking.evaluate_future(
            principal=approved_by, trained_before=trained_before,
        )
