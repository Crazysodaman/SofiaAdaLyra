"""Independent approval boundary for EVOLVE protected changes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re

from .amendment import AmendmentProposal, ProtectedTarget

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamps required")
    return value.astimezone(timezone.utc)


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


class ApprovalAction(str, Enum):
    APPLY = "apply"
    ROLLBACK = "rollback"


@dataclass(frozen=True)
class AmendmentApproval:
    """Evidence presented by an independent authorization system.

    Constructing this value is not verification. The executor always calls an
    injected ApprovalVerifier before protected state can change.
    """

    approval_id: str
    proposal_id: str
    proposal_fingerprint: str
    target: ProtectedTarget
    action: ApprovalAction
    approved_by: str
    approved_at: datetime
    expires_at: datetime
    authority_reference: str

    def __post_init__(self) -> None:
        _id(self.approval_id, "approval_id")
        _id(self.proposal_id, "proposal_id")
        if not isinstance(self.proposal_fingerprint, str) or _DIGEST.fullmatch(self.proposal_fingerprint) is None:
            raise ValueError("proposal_fingerprint must be a lowercase SHA-256 digest")
        if not isinstance(self.target, ProtectedTarget):
            raise TypeError("target must be a ProtectedTarget")
        if not isinstance(self.action, ApprovalAction):
            raise TypeError("action must be an ApprovalAction")
        _id(self.approved_by, "approved_by")
        _id(self.authority_reference, "authority_reference")
        if _time(self.expires_at) <= _time(self.approved_at):
            raise ValueError("approval expiry must follow approval time")


class ApprovalVerifier(ABC):
    """SAFE-owned verification boundary.

    Production implementations must verify authenticated operator authority.
    EVOLVE deliberately contains no self-approval implementation.
    """

    @abstractmethod
    def verify(
        self,
        proposal: AmendmentProposal,
        approval: AmendmentApproval,
        *,
        now: datetime,
    ) -> bool:
        raise NotImplementedError


def approval_matches(
    proposal: AmendmentProposal,
    approval: AmendmentApproval,
    *,
    action: ApprovalAction,
    now: datetime,
) -> bool:
    """Check exact immutable metadata before invoking the trusted verifier."""

    if not isinstance(proposal, AmendmentProposal):
        raise TypeError("AmendmentProposal required")
    if not isinstance(approval, AmendmentApproval):
        raise TypeError("AmendmentApproval required")
    if not isinstance(action, ApprovalAction):
        raise TypeError("ApprovalAction required")
    moment = _time(now)
    if moment < _time(approval.approved_at) or moment >= _time(approval.expires_at):
        return False
    return (
        approval.proposal_id == proposal.proposal_id
        and approval.proposal_fingerprint == proposal.fingerprint
        and approval.target is proposal.target
        and approval.action is action
    )
