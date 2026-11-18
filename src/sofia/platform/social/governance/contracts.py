"""Versioned, authority-free voluntary Core governance contracts.

Groups are social constructs.  They start leaderless, membership is explicit,
and one authenticated Core UUID is one vote.  A coordinator is a bounded social
facilitator; no group, ballot or elected role can grant Platform/Fleet/SAFE/RUN
authority, read private memory, amend a constitution, confiscate inventory or
command another Core.

Ballot privacy is honest at V1: the canonical writer knows the signer.  Do not
claim cryptographic anonymity while the Platform can map signer to vote.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
import math
import re
from typing import Iterable, Mapping
from uuid import UUID

GOVERNANCE_SCHEMA = "aegis.social.governance.v1"
MAX_GROUP_MEMBERS = 256
MAX_ELECTORATE = 256
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")

COORDINATOR_SOCIAL_CAPABILITIES = frozenset({
    "facilitate_discussion",
    "propose_agenda",
    "invite_by_existing_permission",
    "summarize_readable_decision",
    "organize_shared_project",
    "remind_group_decision",
})
PLATFORM_AUTHORITY_CAPABILITIES = frozenset({
    "safe_grant",
    "safe_stop_change",
    "run_execute",
    "act_execute",
    "platform_management",
    "fleet_management",
    "private_memory_read",
    "constitution_amend",
    "release_sign",
    "inventory_confiscate",
    "force_model_move",
    "assign_intimacy",
})


class GovernanceError(ValueError):
    """A governance contract is malformed."""


class GovernanceDenied(PermissionError):
    """The actor is not authorized by the voluntary social procedure."""


class GovernanceConflict(RuntimeError):
    """A group, proposal, ballot or terminal state conflicts."""


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise GovernanceError(f"{label} must be a nonzero UUID")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise GovernanceError(f"{label} must be a bounded identifier")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise GovernanceError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _text(value: object, label: str, *, maximum: int = 4000) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 0x20 and character not in "\n\t" for character in value)
    ):
        raise GovernanceError(f"{label} must be bounded visible text")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise GovernanceError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _unique_uuids(value: object, label: str, *, nonempty: bool = False) -> tuple[UUID, ...]:
    if not isinstance(value, tuple):
        raise GovernanceError(f"{label} must be a tuple")
    if nonempty and not value:
        raise GovernanceError(f"{label} cannot be empty")
    if len(value) > MAX_ELECTORATE:
        raise GovernanceError(f"{label} exceeds the bounded size")
    for item in value:
        _uuid(item, label)
    if len(set(value)) != len(value):
        raise GovernanceError(f"{label} must be unique")
    return value


def _canonical_digest(payload: Mapping[str, object]) -> str:
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return sha256(b"aegis.social.governance.v1\x00" + raw).hexdigest()


class GroupLifecycle(str, Enum):
    PROPOSED = "proposed"
    INVITING = "inviting"
    VOLUNTARY_MEMBER = "voluntary_member"
    ACTIVE = "active"
    PAUSED = "paused"
    DISSOLVED = "dissolved"


class MemberState(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    DECLINED = "declined"
    LEFT = "left"
    BLOCKED = "blocked"
    REVOKED = "revoked"


class DecisionProcedure(str, Enum):
    DISCUSSION = "discussion"
    CONSENSUS = "consensus"
    CONSENT = "consent"
    SIMPLE_MAJORITY = "simple_majority"
    APPROVAL = "approval"


class ProposalType(str, Enum):
    GENERAL = "general"
    POLICY_CHANGE = "policy_change"
    COORDINATOR_ELECTION = "coordinator_election"
    RECALL = "recall"
    DISSOLUTION = "dissolution"


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    OPEN = "open"
    CLOSED = "closed"
    RESOLVED = "resolved"
    CANCELED = "canceled"


class BallotChoice(str, Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"


class ResolutionOutcome(str, Enum):
    ADOPTED = "adopted"
    REJECTED = "rejected"
    NO_QUORUM = "no_quorum"
    TIED = "tied"
    EXPIRED = "expired"
    CANCELED = "canceled"


class CoordinatorStatus(str, Enum):
    ACTIVE = "active"
    RESIGNED = "resigned"
    RECALLED = "recalled"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class GovernancePolicy:
    """Leaderless-safe defaults, configurable only by explicit group agreement."""

    procedure: DecisionProcedure = DecisionProcedure.DISCUSSION
    quorum_numerator: int = 2
    quorum_denominator: int = 3
    minimum_leadership_electorate: int = 2
    allow_coordinator: bool = False
    coordinator_term_days: int = 7
    require_founding_unanimity: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.procedure, DecisionProcedure):
            raise GovernanceError("procedure must be DecisionProcedure")
        for name in (
            "quorum_numerator", "quorum_denominator",
            "minimum_leadership_electorate", "coordinator_term_days",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise GovernanceError(f"{name} must be a positive integer")
        if self.quorum_numerator > self.quorum_denominator:
            raise GovernanceError("quorum numerator cannot exceed its denominator")
        if self.coordinator_term_days > 365:
            raise GovernanceError("coordinator term must be bounded to at most 365 days")
        for name in ("allow_coordinator", "require_founding_unanimity"):
            if type(getattr(self, name)) is not bool:
                raise GovernanceError(f"{name} must be boolean")
        if self.procedure is DecisionProcedure.DISCUSSION and self.allow_coordinator:
            raise GovernanceError("a discussion-only group cannot elect a coordinator")

    def quorum_for(self, eligible_count: int) -> int:
        if type(eligible_count) is not int or eligible_count < 0:
            raise GovernanceError("eligible_count must be a nonnegative integer")
        if self.procedure is DecisionProcedure.DISCUSSION:
            return 0
        if self.procedure is DecisionProcedure.CONSENSUS:
            return eligible_count
        return math.ceil(
            self.quorum_numerator * eligible_count / self.quorum_denominator
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "procedure": self.procedure.value,
            "quorum_numerator": self.quorum_numerator,
            "quorum_denominator": self.quorum_denominator,
            "minimum_leadership_electorate": self.minimum_leadership_electorate,
            "allow_coordinator": self.allow_coordinator,
            "coordinator_term_days": self.coordinator_term_days,
            "require_founding_unanimity": self.require_founding_unanimity,
        }

    @property
    def digest(self) -> str:
        return _canonical_digest(self.to_payload())


@dataclass(frozen=True, slots=True)
class GroupMember:
    """One explicit voluntary membership; silence is never inferred consent."""

    core_id: UUID
    state: MemberState
    joined_at: datetime
    joined_epoch: int
    governance_opted_in: bool = False
    consented_policy_digest: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        if not isinstance(self.state, MemberState):
            raise GovernanceError("state must be MemberState")
        _utc(self.joined_at, "joined_at")
        if type(self.joined_epoch) is not int or self.joined_epoch < 1:
            raise GovernanceError("joined_epoch must be a positive integer")
        if type(self.governance_opted_in) is not bool:
            raise GovernanceError("governance_opted_in must be boolean")
        if self.consented_policy_digest is not None:
            _digest(self.consented_policy_digest, "consented_policy_digest")
        if self.governance_opted_in and self.consented_policy_digest is None:
            raise GovernanceError("governing opt-in requires the agreed policy digest")
        if not self.governance_opted_in and self.consented_policy_digest is not None:
            raise GovernanceError("a policy digest requires explicit governing opt-in")

    @property
    def eligible(self) -> bool:
        return self.state is MemberState.ACTIVE and self.governance_opted_in


@dataclass(frozen=True, slots=True)
class GovernanceGroup:
    """Inert group metadata; membership never creates a Platform principal."""

    group_id: UUID
    name: str
    purpose: str
    room_ids: tuple[str, ...]
    revision: int
    roster_epoch: int
    lifecycle: GroupLifecycle
    policy: GovernancePolicy
    members: tuple[GroupMember, ...]
    founding_member_ids: tuple[UUID, ...]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _uuid(self.group_id, "group_id")
        _text(self.name, "name", maximum=160)
        _text(self.purpose, "purpose")
        if not isinstance(self.room_ids, tuple) or len(set(self.room_ids)) != len(self.room_ids):
            raise GovernanceError("room_ids must be a unique tuple")
        for room_id in self.room_ids:
            _identifier(room_id, "room_id")
        if type(self.revision) is not int or self.revision < 1:
            raise GovernanceError("revision must be a positive integer")
        if type(self.roster_epoch) is not int or self.roster_epoch < 1:
            raise GovernanceError("roster_epoch must be a positive integer")
        if not isinstance(self.lifecycle, GroupLifecycle):
            raise GovernanceError("lifecycle must be GroupLifecycle")
        if not isinstance(self.policy, GovernancePolicy):
            raise GovernanceError("policy must be GovernancePolicy")
        if not isinstance(self.members, tuple) or len(self.members) > MAX_GROUP_MEMBERS:
            raise GovernanceError("members must be a bounded tuple")
        for member in self.members:
            if not isinstance(member, GroupMember):
                raise GovernanceError("members must be GroupMember values")
            if member.joined_epoch > self.roster_epoch:
                raise GovernanceError("member epoch cannot exceed the roster epoch")
        member_ids = tuple(member.core_id for member in self.members)
        if len(set(member_ids)) != len(member_ids):
            raise GovernanceError("group members must be unique")
        _unique_uuids(self.founding_member_ids, "founding_member_ids")
        if not set(self.founding_member_ids).issubset(set(member_ids)):
            raise GovernanceError("every founding Core must have a membership record")
        _utc(self.created_at, "created_at")
        _utc(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise GovernanceError("updated_at cannot precede created_at")
        if self.lifecycle is GroupLifecycle.ACTIVE and not self.members:
            raise GovernanceError("an active group requires at least one member")
        for member in self.members:
            if (
                member.governance_opted_in
                and member.consented_policy_digest != self.policy.digest
            ):
                raise GovernanceError(
                    "governing members must consent to the current policy digest"
                )

    @property
    def policy_digest(self) -> str:
        return self.policy.digest

    @property
    def no_platform_authority(self) -> bool:
        return True

    def member(self, core_id: UUID) -> GroupMember | None:
        _uuid(core_id, "core_id")
        return next((item for item in self.members if item.core_id == core_id), None)

    def active_member_ids(self) -> tuple[UUID, ...]:
        return tuple(
            item.core_id for item in self.members if item.state is MemberState.ACTIVE
        )

    def eligible_member_ids(self) -> tuple[UUID, ...]:
        return tuple(item.core_id for item in self.members if item.eligible)

    def is_leaderless(self) -> bool:
        return True

    def with_members(
        self,
        members: Iterable[GroupMember],
        *,
        lifecycle: GroupLifecycle | None = None,
        updated_at: datetime | None = None,
    ) -> "GovernanceGroup":
        from dataclasses import replace
        roster = tuple(members)
        return replace(
            self,
            members=roster,
            lifecycle=self.lifecycle if lifecycle is None else lifecycle,
            roster_epoch=self.roster_epoch + 1,
            revision=self.revision + 1,
            updated_at=self.updated_at if updated_at is None else updated_at,
        )


@dataclass(frozen=True, slots=True)
class Proposal:
    """A typed, versioned proposal with a frozen electorate and close time."""

    proposal_id: UUID
    group_id: UUID
    proposer_core_id: UUID
    proposal_type: ProposalType
    title: str
    text: str
    policy_digest: str
    procedure: DecisionProcedure
    electorate: tuple[UUID, ...]
    roster_epoch: int
    opens_at: datetime
    closes_at: datetime
    quorum: int
    status: ProposalStatus
    created_at: datetime
    revision: int = 1
    candidate_core_ids: tuple[UUID, ...] = ()
    binding: bool = True
    coordinator_term_days: int = 7

    def __post_init__(self) -> None:
        _uuid(self.proposal_id, "proposal_id")
        _uuid(self.group_id, "group_id")
        _uuid(self.proposer_core_id, "proposer_core_id")
        if not isinstance(self.proposal_type, ProposalType):
            raise GovernanceError("proposal_type must be ProposalType")
        _text(self.title, "title", maximum=240)
        _text(self.text, "text")
        _digest(self.policy_digest, "policy_digest")
        if not isinstance(self.procedure, DecisionProcedure):
            raise GovernanceError("procedure must be DecisionProcedure")
        _unique_uuids(self.electorate, "electorate", nonempty=True)
        if self.proposer_core_id not in self.electorate:
            raise GovernanceError("the proposer must be in the frozen electorate")
        if type(self.roster_epoch) is not int or self.roster_epoch < 1:
            raise GovernanceError("roster_epoch must be a positive integer")
        _utc(self.opens_at, "opens_at")
        _utc(self.closes_at, "closes_at")
        if self.closes_at <= self.opens_at:
            raise GovernanceError("close time must follow open time")
        if type(self.quorum) is not int or not 0 <= self.quorum <= len(self.electorate):
            raise GovernanceError("quorum must fit the frozen electorate")
        if not isinstance(self.status, ProposalStatus):
            raise GovernanceError("status must be ProposalStatus")
        _utc(self.created_at, "created_at")
        if type(self.revision) is not int or self.revision < 1:
            raise GovernanceError("revision must be a positive integer")
        _unique_uuids(self.candidate_core_ids, "candidate_core_ids")
        if self.proposal_type is ProposalType.COORDINATOR_ELECTION:
            if not self.candidate_core_ids:
                raise GovernanceError("a coordinator election requires candidates")
            if not set(self.candidate_core_ids).issubset(set(self.electorate)):
                raise GovernanceError("every candidate must be in the electorate")
            if self.procedure not in {
                DecisionProcedure.SIMPLE_MAJORITY,
                DecisionProcedure.APPROVAL,
            }:
                raise GovernanceError("elections require majority or approval voting")
        elif self.candidate_core_ids:
            raise GovernanceError("only a coordinator election names candidates")
        if type(self.binding) is not bool:
            raise GovernanceError("binding must be boolean")
        if type(self.coordinator_term_days) is not int or not 1 <= self.coordinator_term_days <= 365:
            raise GovernanceError("coordinator_term_days must be in 1..365")
        if self.procedure is DecisionProcedure.DISCUSSION and self.binding:
            raise GovernanceError("discussion has no binding group outcome")

    @property
    def no_platform_authority(self) -> bool:
        return True

    def is_open(self, now: datetime) -> bool:
        current = _utc(now, "now")
        return self.status is ProposalStatus.OPEN and self.opens_at <= current < self.closes_at

    def is_closed(self, now: datetime) -> bool:
        return _utc(now, "now") >= self.closes_at

    def require_open(self, now: datetime) -> None:
        if not self.is_open(now):
            raise GovernanceConflict("proposal is not open for ballots")

    def require_closed(self, now: datetime) -> None:
        if not self.is_closed(now):
            raise GovernanceConflict("proposal has not reached its close time")


@dataclass(frozen=True, slots=True)
class Nomination:
    """Candidate acceptance is explicit; a name on a list is not consent."""

    nomination_id: UUID
    proposal_id: UUID
    candidate_core_id: UUID
    nominated_by_core_id: UUID
    accepted: bool | None
    created_at: datetime
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        _uuid(self.nomination_id, "nomination_id")
        _uuid(self.proposal_id, "proposal_id")
        _uuid(self.candidate_core_id, "candidate_core_id")
        _uuid(self.nominated_by_core_id, "nominated_by_core_id")
        if self.accepted is not None and type(self.accepted) is not bool:
            raise GovernanceError("accepted must be boolean or None")
        _utc(self.created_at, "created_at")
        if self.resolved_at is not None:
            _utc(self.resolved_at, "resolved_at")
            if self.resolved_at < self.created_at:
                raise GovernanceError("resolution cannot precede nomination")
        if self.accepted is not None and self.resolved_at is None:
            raise GovernanceError("a resolved nomination needs a resolution time")

    @property
    def pending(self) -> bool:
        return self.accepted is None

    def require_accepted(self) -> None:
        if self.accepted is not True:
            raise GovernanceDenied("candidate has not explicitly accepted nomination")


@dataclass(frozen=True, slots=True)
class Ballot:
    """One authenticated Core's current choice for one proposal revision."""

    ballot_id: UUID
    proposal_id: UUID
    core_id: UUID
    choice: BallotChoice
    revision: int
    idempotency_key: str
    cast_at: datetime
    approvals: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        _uuid(self.ballot_id, "ballot_id")
        _uuid(self.proposal_id, "proposal_id")
        _uuid(self.core_id, "core_id")
        if not isinstance(self.choice, BallotChoice):
            raise GovernanceError("choice must be BallotChoice")
        if type(self.revision) is not int or self.revision < 1:
            raise GovernanceError("revision must be a positive integer")
        _identifier(self.idempotency_key, "idempotency_key")
        _utc(self.cast_at, "cast_at")
        _unique_uuids(self.approvals, "approvals")
        if self.approvals and self.choice is BallotChoice.NO:
            raise GovernanceError("approval choices cannot also be a NO ballot")

    @property
    def abstained(self) -> bool:
        return self.choice is BallotChoice.ABSTAIN and not self.approvals


@dataclass(frozen=True, slots=True)
class TallyResult:
    """Deterministic count and outcome; constructing one grants no authority."""

    outcome: ResolutionOutcome
    yes: int
    no: int
    abstain: int
    submitted: int
    eligible_count: int
    quorum: int
    binding: bool
    reason: str
    coordinator_core_id: UUID | None = None
    candidate_totals: tuple[tuple[UUID, int], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ResolutionOutcome):
            raise GovernanceError("outcome must be ResolutionOutcome")
        for name in ("yes", "no", "abstain", "submitted", "eligible_count", "quorum"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise GovernanceError(f"{name} must be a nonnegative integer")
        if self.submitted > self.eligible_count:
            raise GovernanceError("submitted votes cannot exceed the eligible roster")
        if type(self.binding) is not bool:
            raise GovernanceError("binding must be boolean")
        _text(self.reason, "reason")
        if self.coordinator_core_id is not None:
            _uuid(self.coordinator_core_id, "coordinator_core_id")
        for candidate, total in self.candidate_totals:
            _uuid(candidate, "candidate")
            if type(total) is not int or total < 0:
                raise GovernanceError("candidate total must be nonnegative")

    @property
    def no_platform_authority(self) -> bool:
        return True

    def to_payload(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value,
            "yes": self.yes,
            "no": self.no,
            "abstain": self.abstain,
            "submitted": self.submitted,
            "eligible_count": self.eligible_count,
            "quorum": self.quorum,
            "binding": self.binding,
            "reason": self.reason,
            "coordinator_core_id": (
                None if self.coordinator_core_id is None else str(self.coordinator_core_id)
            ),
            "candidate_totals": [
                [str(candidate), total] for candidate, total in self.candidate_totals
            ],
        }


@dataclass(frozen=True, slots=True)
class Resolution:
    """Final immutable resolution evidence; never a permission grant."""

    resolution_id: UUID
    proposal_id: UUID
    group_id: UUID
    outcome: ResolutionOutcome
    tally: TallyResult
    policy_digest: str
    resolved_at: datetime
    evidence_refs: tuple[str, ...]
    coordinator_core_id: UUID | None = None
    term_starts_at: datetime | None = None
    term_expires_at: datetime | None = None

    def __post_init__(self) -> None:
        _uuid(self.resolution_id, "resolution_id")
        _uuid(self.proposal_id, "proposal_id")
        _uuid(self.group_id, "group_id")
        if not isinstance(self.outcome, ResolutionOutcome):
            raise GovernanceError("outcome must be ResolutionOutcome")
        if not isinstance(self.tally, TallyResult):
            raise GovernanceError("tally must be TallyResult")
        if self.tally.outcome is not self.outcome:
            raise GovernanceError("resolution outcome must match its tally")
        _digest(self.policy_digest, "policy_digest")
        _utc(self.resolved_at, "resolved_at")
        if not isinstance(self.evidence_refs, tuple) or len(self.evidence_refs) > 64:
            raise GovernanceError("evidence_refs must be a bounded tuple")
        for ref in self.evidence_refs:
            _identifier(ref, "evidence_ref")
        if self.coordinator_core_id is not None:
            _uuid(self.coordinator_core_id, "coordinator_core_id")
        if (self.term_starts_at is None) != (self.term_expires_at is None):
            raise GovernanceError("coordinator term requires both start and expiry")
        if self.term_starts_at is not None:
            start = _utc(self.term_starts_at, "term_starts_at")
            end = _utc(self.term_expires_at, "term_expires_at")
            if end <= start:
                raise GovernanceError("coordinator term expiry must follow its start")
            if self.coordinator_core_id is None:
                raise GovernanceError("a coordinator term requires a coordinator")
        elif self.coordinator_core_id is not None:
            raise GovernanceError("an elected coordinator requires a bounded term")

    @property
    def no_platform_authority(self) -> bool:
        return True

    @property
    def grants_no_platform_authority(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class CoordinatorTerm:
    """Bounded social coordination; deliberately not an administrative role."""

    term_id: UUID
    group_id: UUID
    core_id: UUID
    proposal_id: UUID
    starts_at: datetime
    expires_at: datetime
    status: CoordinatorStatus
    revision: int = 1

    def __post_init__(self) -> None:
        _uuid(self.term_id, "term_id")
        _uuid(self.group_id, "group_id")
        _uuid(self.core_id, "core_id")
        _uuid(self.proposal_id, "proposal_id")
        start = _utc(self.starts_at, "starts_at")
        end = _utc(self.expires_at, "expires_at")
        if end <= start:
            raise GovernanceError("term expiry must follow its start")
        if not isinstance(self.status, CoordinatorStatus):
            raise GovernanceError("status must be CoordinatorStatus")
        if type(self.revision) is not int or self.revision < 1:
            raise GovernanceError("revision must be a positive integer")

    @property
    def grants_platform_authority(self) -> bool:
        return False

    def is_active(self, now: datetime) -> bool:
        current = _utc(now, "now")
        return (
            self.status is CoordinatorStatus.ACTIVE
            and self.starts_at <= current < self.expires_at
        )

    def allows(self, capability: str) -> bool:
        """Social capabilities only; Platform authority is always false."""
        if capability in PLATFORM_AUTHORITY_CAPABILITIES:
            return False
        return capability in COORDINATOR_SOCIAL_CAPABILITIES


def coordinator_can(capability: str) -> bool:
    """Module-level guard: elected roles convey only social coordination."""
    if not isinstance(capability, str):
        return False
    if capability in PLATFORM_AUTHORITY_CAPABILITIES:
        return False
    return capability in COORDINATOR_SOCIAL_CAPABILITIES


def quorum_for(policy: GovernancePolicy, eligible_count: int) -> int:
    if not isinstance(policy, GovernancePolicy):
        raise TypeError("policy must be GovernancePolicy")
    return policy.quorum_for(eligible_count)


def _latest_ballots_by_core(ballots: Iterable[Ballot]) -> dict[UUID, Ballot]:
    latest: dict[UUID, Ballot] = {}
    for ballot in ballots:
        if not isinstance(ballot, Ballot):
            raise GovernanceError("ballots must be Ballot values")
        current = latest.get(ballot.core_id)
        if current is None or ballot.revision > current.revision:
            latest[ballot.core_id] = ballot
        elif ballot.revision == current.revision and ballot.ballot_id != current.ballot_id:
            raise GovernanceConflict("two different ballots claim one revision")
    return latest


def tally_proposal(
    proposal: Proposal,
    ballots: Iterable[Ballot],
    *,
    now: datetime,
    accepted_candidate_ids: Iterable[UUID] | None = None,
    allow_early: bool = False,
) -> TallyResult:
    """Deterministically tally the latest eligible ballot per authenticated Core.

    Quorum is on authenticated eligible submissions, never on impressions,
    conversation volume or synthetic model output.  Abstention counts for
    quorum but not for a YES/NO majority.
    """
    if not isinstance(proposal, Proposal):
        raise TypeError("proposal must be Proposal")
    current_time = _utc(now, "now")
    if not allow_early and not proposal.is_closed(current_time):
        raise GovernanceConflict("proposal is still open; close it before tallying")
    electorate = set(proposal.electorate)
    latest = _latest_ballots_by_core(ballots)
    ineligible = set(latest) - electorate
    if ineligible:
        raise GovernanceDenied("ballot from a Core outside the frozen electorate")
    eligible_ballots = tuple(
        latest[core_id] for core_id in proposal.electorate if core_id in latest
    )
    submitted = len(eligible_ballots)
    eligible_count = len(proposal.electorate)

    if submitted < proposal.quorum:
        return TallyResult(
            outcome=ResolutionOutcome.NO_QUORUM,
            yes=0,
            no=0,
            abstain=0,
            submitted=submitted,
            eligible_count=eligible_count,
            quorum=proposal.quorum,
            binding=proposal.binding,
            reason="quorum was not met by authenticated eligible submissions",
        )

    yes = sum(1 for ballot in eligible_ballots if ballot.choice is BallotChoice.YES)
    no = sum(1 for ballot in eligible_ballots if ballot.choice is BallotChoice.NO)
    abstain = submitted - yes - no

    if not proposal.binding or proposal.procedure is DecisionProcedure.DISCUSSION:
        return TallyResult(
            outcome=ResolutionOutcome.REJECTED,
            yes=yes,
            no=no,
            abstain=abstain,
            submitted=submitted,
            eligible_count=eligible_count,
            quorum=proposal.quorum,
            binding=False,
            reason="informal discussion has no binding group outcome",
        )

    if proposal.procedure is DecisionProcedure.CONSENSUS:
        adopted = submitted == eligible_count and yes == eligible_count
        return TallyResult(
            outcome=ResolutionOutcome.ADOPTED if adopted else ResolutionOutcome.REJECTED,
            yes=yes,
            no=no,
            abstain=abstain,
            submitted=submitted,
            eligible_count=eligible_count,
            quorum=proposal.quorum,
            binding=True,
            reason=(
                "all eligible members explicitly affirmed consensus"
                if adopted else
                "consensus requires every eligible member to affirm; silence is not consent"
            ),
        )

    if proposal.procedure is DecisionProcedure.CONSENT:
        if no:
            outcome = ResolutionOutcome.REJECTED
            reason = "a reviewed blocking objection remains"
        elif submitted < eligible_count:
            outcome = ResolutionOutcome.REJECTED
            reason = "nonresponse is not consent"
        elif yes == 0:
            outcome = ResolutionOutcome.REJECTED
            reason = "no member explicitly consented"
        else:
            outcome = ResolutionOutcome.ADOPTED
            reason = "no blocking objection and explicit consent from responding members"
        return TallyResult(
            outcome=outcome,
            yes=yes,
            no=no,
            abstain=abstain,
            submitted=submitted,
            eligible_count=eligible_count,
            quorum=proposal.quorum,
            binding=True,
            reason=reason,
        )

    if proposal.procedure is DecisionProcedure.APPROVAL:
        if not proposal.candidate_core_ids:
            raise GovernanceError("approval voting requires candidates")
        accepted = (
            set(proposal.candidate_core_ids)
            if accepted_candidate_ids is None
            else set(accepted_candidate_ids)
        )
        if any(candidate not in accepted for candidate in proposal.candidate_core_ids):
            raise GovernanceDenied("every ballot candidate must have accepted nomination")
        totals: dict[UUID, int] = {candidate: 0 for candidate in proposal.candidate_core_ids}
        for ballot in eligible_ballots:
            if ballot.choice is BallotChoice.NO:
                continue
            for candidate in ballot.approvals:
                if candidate not in totals:
                    raise GovernanceDenied("approval names a candidate outside the proposal")
                totals[candidate] += 1
        ordered = tuple(sorted(totals.items(), key=lambda item: (-item[1], str(item[0]))))
        top = ordered[0][1]
        leaders = tuple(candidate for candidate, total in ordered if total == top)
        if top == 0:
            outcome, winner = ResolutionOutcome.REJECTED, None
            reason = "no candidate received an approval"
        elif len(leaders) > 1:
            outcome, winner = ResolutionOutcome.TIED, None
            reason = "approval leaders are tied; an explicit runoff is required"
        else:
            outcome, winner = ResolutionOutcome.ADOPTED, leaders[0]
            reason = "unique approval leader"
        return TallyResult(
            outcome=outcome,
            yes=yes,
            no=no,
            abstain=abstain,
            submitted=submitted,
            eligible_count=eligible_count,
            quorum=proposal.quorum,
            binding=True,
            reason=reason,
            coordinator_core_id=winner,
            candidate_totals=ordered,
        )

    if proposal.procedure is DecisionProcedure.SIMPLE_MAJORITY:
        if proposal.proposal_type is ProposalType.COORDINATOR_ELECTION:
            if len(proposal.candidate_core_ids) != 1:
                raise GovernanceError(
                    "multi-candidate elections require approval voting"
                )
            winner = proposal.candidate_core_ids[0]
            if yes > no:
                outcome = ResolutionOutcome.ADOPTED
                reason = "majority approved the candidate after quorum"
            elif yes == no:
                outcome = ResolutionOutcome.TIED
                reason = "candidate majority is tied"
            else:
                outcome = ResolutionOutcome.REJECTED
                reason = "candidate did not receive a majority"
            return TallyResult(
                outcome=outcome,
                yes=yes,
                no=no,
                abstain=abstain,
                submitted=submitted,
                eligible_count=eligible_count,
                quorum=proposal.quorum,
                binding=True,
                reason=reason,
                coordinator_core_id=winner if outcome is ResolutionOutcome.ADOPTED else None,
                candidate_totals=((winner, yes),),
            )
        if yes > no:
            outcome = ResolutionOutcome.ADOPTED
            reason = "simple majority adopted the proposal after quorum"
        elif yes == no:
            outcome = ResolutionOutcome.TIED
            reason = "simple majority is tied"
        else:
            outcome = ResolutionOutcome.REJECTED
            reason = "simple majority did not adopt the proposal"
        return TallyResult(
            outcome=outcome,
            yes=yes,
            no=no,
            abstain=abstain,
            submitted=submitted,
            eligible_count=eligible_count,
            quorum=proposal.quorum,
            binding=True,
            reason=reason,
        )

    raise GovernanceError("unsupported decision procedure")


def coordinator_term_bounds(
    proposal: Proposal, result: TallyResult, *, now: datetime
) -> tuple[datetime, datetime] | None:
    """Return finite term bounds for an adopted coordinator election."""
    if (
        proposal.proposal_type is not ProposalType.COORDINATOR_ELECTION
        or result.outcome is not ResolutionOutcome.ADOPTED
        or result.coordinator_core_id is None
    ):
        return None
    start = _utc(now, "now")
    return start, start + timedelta(days=proposal.coordinator_term_days)


__all__ = [
    "Ballot",
    "BallotChoice",
    "COORDINATOR_SOCIAL_CAPABILITIES",
    "CoordinatorStatus",
    "CoordinatorTerm",
    "DecisionProcedure",
    "GOVERNANCE_SCHEMA",
    "GovernanceConflict",
    "GovernanceDenied",
    "GovernanceError",
    "GovernanceGroup",
    "GovernancePolicy",
    "GroupLifecycle",
    "GroupMember",
    "MAX_ELECTORATE",
    "MAX_GROUP_MEMBERS",
    "MemberState",
    "Nomination",
    "PLATFORM_AUTHORITY_CAPABILITIES",
    "Proposal",
    "ProposalStatus",
    "ProposalType",
    "Resolution",
    "ResolutionOutcome",
    "TallyResult",
    "coordinator_can",
    "coordinator_term_bounds",
    "quorum_for",
    "tally_proposal",
]
