"""Protected-state amendment *proposal* ledger. No sign-off or mutation API."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class ProtectedTarget(str, Enum):
    IDENTITY = "identity"
    CONSTITUTION = "constitution"


class ProposalStatus(str, Enum):
    REQUIRES_EXPLICIT_REVIEW = "requires_explicit_review"
    UNCHANGED = "unchanged"
    EXPIRED = "expired"
    CLOCK_UNCERTAIN = "clock_uncertain"
    SOURCE_MISMATCH = "source_mismatch"


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamps required")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class AmendmentProposal:
    proposal_id: str
    target: ProtectedTarget
    expected_digest: str
    proposed_digest: str
    evidence_ids: tuple[str, ...]
    reason: str
    rollback_plan: str
    created_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or not self.proposal_id.strip():
            raise ValueError("proposal ID required")
        if not isinstance(self.target, ProtectedTarget):
            raise TypeError("protected target enum required")
        if any(not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None for digest in
               (self.expected_digest, self.proposed_digest)):
            raise ValueError("64-character lowercase SHA-256 digest required")
        if not isinstance(self.evidence_ids, tuple) or not self.evidence_ids or any(
            not isinstance(item, str) or not item.strip() for item in self.evidence_ids
        ) or len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("distinct source evidence IDs required")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason required")
        if not isinstance(self.rollback_plan, str) or not self.rollback_plan.strip():
            raise ValueError("rollback plan required")
        if _time(self.expires_at) <= _time(self.created_at):
            raise ValueError("expiry must follow creation")


def inspect(proposal: AmendmentProposal, now: datetime, *, observed_digest: str) -> ProposalStatus:
    """A match means REVIEW REQUIRED, never authorization to amend state."""
    if not isinstance(proposal, AmendmentProposal):
        raise TypeError("AmendmentProposal required")
    if not isinstance(observed_digest, str) or _DIGEST.fullmatch(observed_digest) is None:
        raise ValueError("observed digest must be a validated SHA-256 value")
    moment = _time(now)
    if moment < _time(proposal.created_at):
        return ProposalStatus.CLOCK_UNCERTAIN
    if moment >= _time(proposal.expires_at):
        return ProposalStatus.EXPIRED
    if observed_digest != proposal.expected_digest:
        return ProposalStatus.SOURCE_MISMATCH  # actual state mismatch: never apply
    if proposal.proposed_digest == proposal.expected_digest:
        return ProposalStatus.UNCHANGED
    return ProposalStatus.REQUIRES_EXPLICIT_REVIEW
