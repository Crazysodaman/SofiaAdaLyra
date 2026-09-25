"""Provenance-first candidate lifecycle for PKG-MEM.

Candidates are derived claims, never replacements for source conversation
records. Promotion is explicit and reversible. This module is intentionally
storage-agnostic so persistence can be added without changing the contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from sofia.memory.retrieval_projection import SourceMessage


class CandidateStatus(str, Enum):
    PROPOSED = "proposed"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    candidate_id: UUID
    content: str
    sources: tuple[SourceMessage, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("candidate content must be nonempty")
        if not isinstance(self.sources, tuple) or not self.sources:
            raise ValueError("candidate requires at least one exact source")
        if any(not isinstance(source, SourceMessage) for source in self.sources):
            raise TypeError("candidate sources must be SourceMessage instances")
        sessions = {source.session_id for source in self.sources}
        if len(sessions) != 1:
            raise ValueError("one candidate cannot silently combine sessions")
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")


class MemoryCandidateRegistry:
    """Explicit lifecycle. No model output can silently become accepted memory."""

    def __init__(self) -> None:
        self._candidates: dict[UUID, MemoryCandidate] = {}
        self._status: dict[UUID, CandidateStatus] = {}

    def propose(self, candidate: MemoryCandidate) -> None:
        if not isinstance(candidate, MemoryCandidate):
            raise TypeError("candidate must be a MemoryCandidate")
        if candidate.candidate_id in self._candidates:
            raise ValueError("candidate ID already exists")
        self._candidates[candidate.candidate_id] = candidate
        self._status[candidate.candidate_id] = CandidateStatus.PROPOSED

    def status(self, candidate_id: UUID) -> CandidateStatus | None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        return self._status.get(candidate_id)

    def promote(self, candidate_id: UUID) -> None:
        self._transition(candidate_id, CandidateStatus.PROPOSED, CandidateStatus.PROMOTED)

    def reject(self, candidate_id: UUID) -> None:
        self._transition(candidate_id, CandidateStatus.PROPOSED, CandidateStatus.REJECTED)

    def revoke(self, candidate_id: UUID) -> None:
        self._transition(candidate_id, CandidateStatus.PROMOTED, CandidateStatus.REVOKED)

    def get(self, candidate_id: UUID) -> MemoryCandidate | None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        return self._candidates.get(candidate_id)

    def _transition(self, candidate_id: UUID, expected: CandidateStatus, target: CandidateStatus) -> None:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be a UUID")
        if candidate_id not in self._candidates:
            raise LookupError("candidate does not exist")
        if self._status[candidate_id] is not expected:
            raise ValueError(f"candidate must be {expected.value} before {target.value}")
        self._status[candidate_id] = target
