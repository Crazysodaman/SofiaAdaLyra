"""Application boundary for owner-reviewed memory significance.

Marking a memory significant is a review decision over an already
promoted candidate, so it inherits the exact review authority of memory
promotion: authenticated private Sparks review inside the candidate's
own scope. Non-promoted, revoked, stale-source, or cross-audience
candidates fail closed. Nothing here writes memory content.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.significance import MarkStatus, MemorySignificance, SignificantMemoryStore
from .memory_review import MemoryReviewService


class MemorySignificanceService:
    """Reviewed-owner significance boundary.

    Authority is delegated to the shared review rule so promotion and
    significance always require the same authenticated private Sparks
    session; this module never widens or copies that rule.
    """

    def __init__(
        self,
        *,
        candidate_store: DurableMemoryCandidateStore,
        significance_store: SignificantMemoryStore,
    ) -> None:
        if not isinstance(candidate_store, DurableMemoryCandidateStore):
            raise TypeError("candidate_store must be a DurableMemoryCandidateStore")
        if not isinstance(significance_store, SignificantMemoryStore):
            raise TypeError("significance_store must be a SignificantMemoryStore")
        self._candidates = candidate_store
        self._significance = significance_store

    def _require_reviewed_scope(
        self, candidate_id: UUID, reviewed_by,
    ) -> None:
        MemoryReviewService._require_sparks_reviewer(reviewed_by)
        candidate = self._candidates.get(candidate_id)
        if candidate is None:
            raise LookupError("memory candidate does not exist")
        if (
            candidate.principal_id != reviewed_by.principal_id
            or candidate.audience_id not in (None, reviewed_by.audience_id)
        ):
            raise PermissionError(
                "memory candidate is outside current private review audience"
            )
        return candidate

    def _require_markable(
        self, candidate_id: UUID, reviewed_by,
    ):
        candidate = self._require_reviewed_scope(candidate_id, reviewed_by)
        if self._candidates.status(candidate_id) is not CandidateStatus.PROMOTED:
            raise ValueError(
                "only promoted candidates can carry significance"
            )
        if not self._candidates.is_recall_eligible(candidate_id):
            raise ValueError(
                "revoked or stale memory candidate cannot gain significance"
            )
        return candidate

    def mark(
        self, candidate_id: UUID, *,
        significance: float, reason: str, reviewed_by, now: datetime,
    ) -> MemorySignificance:
        self._require_markable(candidate_id, reviewed_by)
        candidate = self._candidates.get(candidate_id)
        current = self._significance.current(candidate_id)
        value = MemorySignificance(
            candidate_id=candidate_id,
            principal_id=candidate.principal_id,
            audience_id=candidate.audience_id,
            significance=significance, reason=reason,
            decided_by=reviewed_by.principal_id,
            revision=1 if current is None else current.revision + 1,
            status=MarkStatus.ACTIVE,
            decided_at=now,
        )
        self._significance.hold(
            value,
            expected_revision=None if current is None else current.revision,
        )
        return value

    def withdraw(
        self, candidate_id: UUID, *, reason: str, reviewed_by, now: datetime,
    ) -> MemorySignificance:
        self._require_reviewed_scope(candidate_id, reviewed_by)
        current = self._significance.current(candidate_id)
        if current is None or current.status is not MarkStatus.ACTIVE:
            raise ValueError("no active significance mark to withdraw")
        value = MemorySignificance(
            candidate_id=candidate_id,
            principal_id=current.principal_id,
            audience_id=current.audience_id,
            significance=current.significance,
            reason=reason,
            decided_by=reviewed_by.principal_id,
            revision=current.revision + 1,
            status=MarkStatus.REVOKED,
            decided_at=now,
        )
        self._significance.hold(value, expected_revision=current.revision)
        return value

    def marked_for(
        self, *, principal_id: str, audience_id: str | None = None,
    ) -> tuple[MemorySignificance, ...]:
        return self._significance.active_marks(
            principal_id=principal_id, audience_id=audience_id,
        )
