"""Provenance-first candidate lifecycle for PKG-MEM.

Candidates are derived claims, never replacements for source conversation
records. Promotion is explicit and reversible. Lifecycle persistence is owned by DurableMemoryCandidateStore.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from sofia.memory.originals import SourceMessage


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
    principal_id: str | None = None
    audience_id: str | None = None

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
        for name in ("principal_id", "audience_id"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(f"{name} must be None or nonempty")
        if self.audience_id is not None and self.principal_id is None:
            raise ValueError("audience-scoped memory requires principal_id")
