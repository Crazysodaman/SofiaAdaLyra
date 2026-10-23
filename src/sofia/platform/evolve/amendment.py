"""Immutable EVOLVE protected-state proposals.

A proposal describes a possible change. It is never approval and never mutates
identity or Constitution state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")


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


def _digest(value: str, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


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
        _identifier(self.proposal_id, "proposal_id")
        if not isinstance(self.target, ProtectedTarget):
            raise TypeError("protected target enum required")
        _digest(self.expected_digest, "expected_digest")
        _digest(self.proposed_digest, "proposed_digest")
        if (
            not isinstance(self.evidence_ids, tuple)
            or not self.evidence_ids
            or len(self.evidence_ids) > 32
        ):
            raise ValueError("distinct bounded evidence IDs required")
        for item in self.evidence_ids:
            _identifier(item, "evidence_id")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("distinct bounded evidence IDs required")
        if not isinstance(self.reason, str) or not self.reason.strip() or len(self.reason) > 1000:
            raise ValueError("bounded reason required")
        if not isinstance(self.rollback_plan, str) or not self.rollback_plan.strip() or len(self.rollback_plan) > 1000:
            raise ValueError("bounded rollback plan required")
        if _time(self.expires_at) <= _time(self.created_at):
            raise ValueError("expiry must follow creation")

    @property
    def fingerprint(self) -> str:
        """Stable digest to bind an independent approval to this exact proposal."""

        document = {
            "proposal_id": self.proposal_id,
            "target": self.target.value,
            "expected_digest": self.expected_digest,
            "proposed_digest": self.proposed_digest,
            "evidence_ids": list(self.evidence_ids),
            "reason": self.reason,
            "rollback_plan": self.rollback_plan,
            "created_at": _time(self.created_at).isoformat(),
            "expires_at": _time(self.expires_at).isoformat(),
        }
        payload = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(payload).hexdigest()


def content_digest(content: str) -> str:
    if not isinstance(content, str):
        raise TypeError("protected content must be text")
    return sha256(content.encode("utf-8")).hexdigest()


def inspect(
    proposal: AmendmentProposal,
    now: datetime,
    *,
    observed_digest: str,
) -> ProposalStatus:
    """A matching source means review is required, never authorization."""

    if not isinstance(proposal, AmendmentProposal):
        raise TypeError("AmendmentProposal required")
    _digest(observed_digest, "observed_digest")
    moment = _time(now)
    if moment < _time(proposal.created_at):
        return ProposalStatus.CLOCK_UNCERTAIN
    if moment >= _time(proposal.expires_at):
        return ProposalStatus.EXPIRED
    if observed_digest != proposal.expected_digest:
        return ProposalStatus.SOURCE_MISMATCH
    if proposal.proposed_digest == proposal.expected_digest:
        return ProposalStatus.UNCHANGED
    return ProposalStatus.REQUIRES_EXPLICIT_REVIEW
