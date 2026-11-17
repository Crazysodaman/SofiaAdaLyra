"""Evidence categories that keep observation separate from claim and correction."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from uuid import UUID


_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


class EvidenceCategory(str, Enum):
    OBSERVED = "observed"
    SELF_REPORT = "self_report"
    PEER_CLAIM = "peer_claim"
    VERIFIED_OUTCOME = "verified_outcome"
    INTERPRETATION = "interpretation"
    UNCERTAINTY = "uncertainty"
    CORRECTION = "correction"
    WITHDRAWAL = "withdrawal"


class EvidenceStatus(str, Enum):
    ACTIVE = "active"
    CORRECTED = "corrected"
    WITHDRAWN = "withdrawn"


def _utc(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    core_id: UUID
    peer_core_id: UUID | None
    category: EvidenceCategory
    claim: str
    evidence_ref: str
    recorded_at: datetime
    message_id: str | None
    supersedes: str | None
    status: EvidenceStatus
    sequence: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.evidence_id, str)
            or not self.evidence_id.startswith("evidence:")
            or len(self.evidence_id) > 120
        ):
            raise ValueError("evidence_id must be a canonical evidence id")
        if not isinstance(self.core_id, UUID):
            raise TypeError("core_id must be a UUID")
        if self.peer_core_id is not None and not isinstance(
            self.peer_core_id, UUID
        ):
            raise TypeError("peer_core_id must be a UUID")
        if not isinstance(self.category, EvidenceCategory):
            raise TypeError("category must be EvidenceCategory")
        if (
            not isinstance(self.claim, str)
            or not self.claim.strip()
            or len(self.claim.strip()) > 1000
        ):
            raise ValueError("claim must be bounded nonempty text")
        if (
            not isinstance(self.evidence_ref, str)
            or _REF.fullmatch(self.evidence_ref) is None
        ):
            raise ValueError("evidence_ref must be a bounded reference")
        if _utc(self.recorded_at, "recorded_at") != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")
        if self.message_id is not None and (
            not isinstance(self.message_id, str)
            or _REF.fullmatch(self.message_id) is None
        ):
            raise ValueError("message_id must be a bounded reference")
        if self.supersedes is not None and (
            not isinstance(self.supersedes, str)
            or not self.supersedes.startswith("evidence:")
            or len(self.supersedes) > 120
        ):
            raise ValueError("supersedes must be a canonical evidence id")
        if not isinstance(self.status, EvidenceStatus):
            raise TypeError("status must be EvidenceStatus")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be positive")
        if self.category in {
            EvidenceCategory.CORRECTION,
            EvidenceCategory.WITHDRAWAL,
        } and self.supersedes is None:
            raise ValueError("corrections and withdrawals must supersede evidence")
        if self.category is EvidenceCategory.CORRECTION and (
            self.status is not EvidenceStatus.ACTIVE
        ):
            raise ValueError("correction records remain active corrections")
        if self.category is EvidenceCategory.WITHDRAWAL and (
            self.status is not EvidenceStatus.ACTIVE
        ):
            raise ValueError("withdrawal records remain active withdrawals")

    @property
    def is_verified(self) -> bool:
        return (
            self.category is EvidenceCategory.VERIFIED_OUTCOME
            and self.status is EvidenceStatus.ACTIVE
        )

    @property
    def is_firsthand(self) -> bool:
        return self.category is EvidenceCategory.OBSERVED

    @property
    def is_claim(self) -> bool:
        return self.category in {
            EvidenceCategory.SELF_REPORT,
            EvidenceCategory.PEER_CLAIM,
        }

    @property
    def is_correction(self) -> bool:
        return self.category in {
            EvidenceCategory.CORRECTION,
            EvidenceCategory.WITHDRAWAL,
        }
