"""Bounded, optional Core-initiated social activity.

A Core may propose a message, follow-up, invitation or leave.  Proposals are
inert data: nothing is said or invited until the owning Core (or its host)
explicitly executes the proposal through the canonical chat composition.

This layer owns no database and invents no dialogue.  It tracks only bounded
live initiative state (cooldowns, budgets, open proposals and declined targets)
and delegates every consequential chat action to
:class:`sofia.core.multicore.conversation.MultiCoreConversation`.

Social initiative never grants execution authority, tool access, membership or
identity.  Owner inspection and stop controls are always available.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import re
from typing import Callable, Iterable
from uuid import uuid4

from sofia.core.multicore.conversation import MultiCoreConversation
from sofia.platform.chat import ChatActor, ChatMessage, InvitationStatus, RoomInvitation


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_WHITESPACE = re.compile(r"\s+")


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _positive_int(value: object, label: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _text(value: object, label: str, *, maximum: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    if any(ord(character) < 0x20 and character not in "\t\n\r" for character in value):
        raise ValueError(f"{label} cannot contain control characters")
    return value


def _optional_text(value: object, label: str, *, maximum: int = 4000) -> str | None:
    if value is None:
        return None
    return _text(value, label, maximum=maximum)


class InitiativeAction(str, Enum):
    PROPOSE = "propose"
    FOLLOW_UP = "follow_up"
    INVITE = "invite"
    LEAVE = "leave"


class ProposalStatus(str, Enum):
    PROPOSED = "proposed"
    EXECUTED = "executed"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class InitiativeLimits:
    max_proposals_per_core_per_day: int = 8
    max_open_proposals_per_core: int = 2
    max_follow_ups_per_chain: int = 2
    cooldown: timedelta = timedelta(minutes=10)
    duplicate_window: timedelta = timedelta(hours=24)
    proposal_expiry: timedelta = timedelta(hours=12)
    declined_invitation_cooldown: timedelta = timedelta(hours=24)
    default_budget: int = 12
    max_tracked_proposals: int = 512

    def __post_init__(self) -> None:
        for label in (
            "max_proposals_per_core_per_day",
            "max_open_proposals_per_core",
            "max_follow_ups_per_chain",
            "default_budget",
        ):
            _positive_int(getattr(self, label), label, minimum=0)
        _positive_int(self.default_budget, "default_budget")
        _positive_int(self.max_tracked_proposals, "max_tracked_proposals")
        for label in (
            "cooldown",
            "duplicate_window",
            "proposal_expiry",
            "declined_invitation_cooldown",
        ):
            value = getattr(self, label)
            if not isinstance(value, timedelta) or value < timedelta(0):
                raise ValueError(f"{label} must be a non-negative timedelta")


@dataclass(frozen=True, slots=True)
class SocialProposal:
    proposal_id: str
    core_id: str
    action: InitiativeAction
    status: ProposalStatus
    rationale: str
    created_at: datetime
    expires_at: datetime
    room_id: str | None = None
    target_core_id: str | None = None
    body: str | None = None
    chain_id: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.proposal_id, "proposal_id")
        _identifier(self.core_id, "core_id")
        if not isinstance(self.action, InitiativeAction):
            raise TypeError("action must be an InitiativeAction")
        if not isinstance(self.status, ProposalStatus):
            raise TypeError("status must be a ProposalStatus")
        if not isinstance(self.rationale, str) or len(self.rationale) > 600:
            raise ValueError("rationale must be bounded text")
        _utc(self.created_at, "created_at")
        _utc(self.expires_at, "expires_at")
        if self.room_id is not None:
            _identifier(self.room_id, "room_id")
        if self.target_core_id is not None:
            _identifier(self.target_core_id, "target_core_id")
        if self.body is not None:
            _text(self.body, "body")
        if self.chain_id is not None:
            _identifier(self.chain_id, "chain_id")

    @property
    def permitted(self) -> bool:
        return self.status is ProposalStatus.PROPOSED

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False

    def as_data(self) -> dict[str, object]:
        return {
            "schema": "aegis.core.multicore.social.proposal.v1",
            "proposal_id": self.proposal_id,
            "core_id": self.core_id,
            "action": self.action.value,
            "status": self.status.value,
            "rationale": self.rationale,
            "body": self.body,
            "room_id": self.room_id,
            "target_core_id": self.target_core_id,
            "trust": "DATA",
            "is_instruction": False,
            "grants_authority": False,
        }


@dataclass(frozen=True, slots=True)
class SocialExecution:
    proposal_id: str
    status: ProposalStatus
    executed_at: datetime
    room_id: str | None = None
    message_id: str | None = None
    invitation_id: str | None = None
    reason: str = ""

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class SocialCoreStatus:
    core_id: str
    active: bool
    stopped: bool
    remaining_budget: int
    open_proposals: int
    proposals_today: int


@dataclass(slots=True)
class _CoreSocialState:
    active: bool = True
    stopped: bool = False
    remaining_budget: int = 12
    last_proposal_at: datetime | None = None
    proposal_times: deque[datetime] = field(default_factory=deque)
    open_proposals: set[str] = field(default_factory=set)
    declined_until: dict[tuple[str, str, str], datetime] = field(
        default_factory=dict
    )
    fingerprints: dict[str, datetime] = field(default_factory=dict)
    followups: dict[str, int] = field(default_factory=dict)


class MultiCoreSocial:
    """Bounded optional social initiative for registered Cores."""

    def __init__(
        self,
        conversation: MultiCoreConversation,
        *,
        clock: Callable[[], datetime] | None = None,
        limits: InitiativeLimits | None = None,
    ) -> None:
        if not isinstance(conversation, MultiCoreConversation):
            raise TypeError("conversation must be a MultiCoreConversation")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        if limits is None:
            limits = InitiativeLimits()
        if not isinstance(limits, InitiativeLimits):
            raise TypeError("limits must be InitiativeLimits")
        self._conversation = conversation
        self._clock = clock
        self._limits = limits
        self._states: dict[str, _CoreSocialState] = {}
        self._proposals: dict[str, SocialProposal] = {}
        self._invite_ids: dict[str, str] = {}
        self._stopped_all = False

    @property
    def conversation(self) -> MultiCoreConversation:
        return self._conversation

    @property
    def limits(self) -> InitiativeLimits:
        return self._limits

    def _now(self) -> datetime:
        value = self._clock() if self._clock is not None else datetime.now(timezone.utc)
        return _utc(value, "clock result")

    def _state(self, core_id: str) -> _CoreSocialState:
        _identifier(core_id, "core_id")
        self._conversation.participant(core_id)
        state = self._states.get(core_id)
        if state is None:
            state = _CoreSocialState(remaining_budget=self._limits.default_budget)
            self._states[core_id] = state
        return state

    # ------------------------------------------------------------------
    # Owner controls and inspection
    # ------------------------------------------------------------------
    def set_active(self, core_id: str, active: bool) -> None:
        if type(active) is not bool:
            raise TypeError("active must be bool")
        self._state(core_id).active = active

    def stop_core(self, core_id: str) -> None:
        self._state(core_id).stopped = True

    def resume_core(self, core_id: str) -> None:
        self._state(core_id).stopped = False

    def stop_all(self) -> None:
        self._stopped_all = True

    def resume_all(self) -> None:
        self._stopped_all = False
        for state in self._states.values():
            state.stopped = False

    def set_budget(self, core_id: str, remaining: int) -> None:
        self._state(core_id).remaining_budget = _positive_int(
            remaining, "remaining", minimum=0
        )

    def status(self, core_id: str) -> SocialCoreStatus:
        state = self._state(core_id)
        now = self._now()
        day_cutoff = now - timedelta(days=1)
        while state.proposal_times and state.proposal_times[0] < day_cutoff:
            state.proposal_times.popleft()
        return SocialCoreStatus(
            core_id=core_id,
            active=state.active and not state.stopped and not self._stopped_all,
            stopped=state.stopped or self._stopped_all,
            remaining_budget=state.remaining_budget,
            open_proposals=len(state.open_proposals),
            proposals_today=len(state.proposal_times),
        )

    def statuses(self) -> tuple[SocialCoreStatus, ...]:
        return tuple(self.status(core_id) for core_id in sorted(self._states))

    def proposal(self, proposal_id: str) -> SocialProposal:
        _identifier(proposal_id, "proposal_id")
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise LookupError("social proposal does not exist")
        return proposal

    def inspect(
        self,
        *,
        core_id: str | None = None,
        status: ProposalStatus | None = None,
    ) -> tuple[SocialProposal, ...]:
        if core_id is not None:
            _identifier(core_id, "core_id")
        if status is not None and not isinstance(status, ProposalStatus):
            raise TypeError("status must be a ProposalStatus")
        self.expire()
        values = tuple(
            self._proposals[proposal_id]
            for proposal_id in sorted(self._proposals)
        )
        return tuple(
            proposal
            for proposal in values
            if (core_id is None or proposal.core_id == core_id)
            and (status is None or proposal.status is status)
        )

    def expire(self) -> int:
        now = self._now()
        expired = 0
        for proposal_id, proposal in tuple(self._proposals.items()):
            if (
                proposal.status is ProposalStatus.PROPOSED
                and now >= proposal.expires_at
            ):
                self._set_status(proposal, ProposalStatus.EXPIRED)
                expired += 1
        return expired

    # ------------------------------------------------------------------
    # Proposal creation
    # ------------------------------------------------------------------
    def _remember_proposal(self, proposal: SocialProposal) -> None:
        self._proposals[proposal.proposal_id] = proposal
        while len(self._proposals) > self._limits.max_tracked_proposals:
            for proposal_id, item in tuple(self._proposals.items()):
                if (
                    proposal_id != proposal.proposal_id
                    and item.status is not ProposalStatus.PROPOSED
                ):
                    del self._proposals[proposal_id]
                    break
            else:
                break

    def _blocked(
        self,
        *,
        core_id: str,
        action: InitiativeAction,
        reason: str,
        rationale: str,
        now: datetime,
        room_id: str | None,
        target_core_id: str | None,
        body: str | None,
        chain_id: str | None,
        stopped: bool = False,
    ) -> SocialProposal:
        proposal = SocialProposal(
            proposal_id=f"proposal:{uuid4()}",
            core_id=core_id,
            action=action,
            status=(
                ProposalStatus.STOPPED if stopped else ProposalStatus.BLOCKED
            ),
            rationale=reason,
            created_at=now,
            expires_at=now + self._limits.proposal_expiry,
            room_id=room_id,
            target_core_id=target_core_id,
            body=body,
            chain_id=chain_id,
        )
        self._remember_proposal(proposal)
        return proposal

    def propose(
        self,
        core_id: str,
        action: InitiativeAction,
        *,
        body: str | None = None,
        room_id: str | None = None,
        target_core_id: str | None = None,
        rationale: str = "",
        chain_id: str | None = None,
        expires_in: timedelta | None = None,
    ) -> SocialProposal:
        if not isinstance(action, InitiativeAction):
            raise TypeError("action must be an InitiativeAction")
        self._conversation.participant(core_id)
        state = self._state(core_id)
        now = self._now()
        if room_id is not None:
            _identifier(room_id, "room_id")
        if target_core_id is not None:
            _identifier(target_core_id, "target_core_id")
            self._conversation.participant(target_core_id)
        if chain_id is not None:
            _identifier(chain_id, "chain_id")
        if body is not None:
            _text(body, "body")
        if not isinstance(rationale, str) or len(rationale) > 600:
            raise ValueError("rationale must be bounded text")
        if expires_in is not None:
            if not isinstance(expires_in, timedelta) or expires_in <= timedelta(0):
                raise ValueError("expires_in must be a positive timedelta")
        if action in {
            InitiativeAction.PROPOSE,
            InitiativeAction.FOLLOW_UP,
        }:
            if room_id is None:
                raise ValueError("message proposals require a room_id")
            if body is None:
                raise ValueError("message proposals require a body")
        if action is InitiativeAction.INVITE:
            if target_core_id is None:
                raise ValueError("invitations require a target_core_id")
        if action is InitiativeAction.LEAVE and room_id is None:
            raise ValueError("leave proposals require a room_id")

        common = dict(
            core_id=core_id,
            action=action,
            rationale=rationale,
            now=now,
            room_id=room_id,
            target_core_id=target_core_id,
            body=body,
            chain_id=chain_id,
        )
        if self._stopped_all or state.stopped or not state.active:
            return self._blocked(
                reason="Core social initiative is stopped or inactive",
                stopped=True,
                **common,
            )
        if state.remaining_budget <= 0:
            return self._blocked(
                reason="Core initiative budget is exhausted", **common
            )
        day_cutoff = now - timedelta(days=1)
        while state.proposal_times and state.proposal_times[0] < day_cutoff:
            state.proposal_times.popleft()
        if len(state.proposal_times) >= self._limits.max_proposals_per_core_per_day:
            return self._blocked(
                reason="daily initiative limit reached", **common
            )
        if len(state.open_proposals) >= self._limits.max_open_proposals_per_core:
            return self._blocked(
                reason="too many open proposals", **common
            )
        declined_key = (action.value, room_id or "", target_core_id or "")
        declined_until = state.declined_until.get(declined_key)
        if declined_until is not None:
            if declined_until > now:
                return self._blocked(
                    reason="a declined invitation is being respected", **common
                )
            del state.declined_until[declined_key]
        if (
            state.last_proposal_at is not None
            and now - state.last_proposal_at < self._limits.cooldown
        ):
            return self._blocked(
                reason="initiative cooldown is active", **common
            )
        fingerprint = self._fingerprint(
            core_id, action, room_id, target_core_id, body
        )
        recent = state.fingerprints.get(fingerprint)
        if recent is not None and now - recent < self._limits.duplicate_window:
            return self._blocked(
                reason="duplicate initiative was suppressed", **common
            )
        if action is InitiativeAction.FOLLOW_UP and chain_id is not None:
            if (
                state.followups.get(chain_id, 0)
                >= self._limits.max_follow_ups_per_chain
            ):
                return self._blocked(
                    reason="follow-up limit reached for this chain", **common
                )

        proposal = SocialProposal(
            proposal_id=f"proposal:{uuid4()}",
            core_id=core_id,
            action=action,
            status=ProposalStatus.PROPOSED,
            rationale=rationale,
            created_at=now,
            expires_at=now
            + (self._limits.proposal_expiry if expires_in is None else expires_in),
            room_id=room_id,
            target_core_id=target_core_id,
            body=body,
            chain_id=chain_id,
        )
        self._remember_proposal(proposal)
        state.last_proposal_at = now
        state.proposal_times.append(now)
        state.open_proposals.add(proposal.proposal_id)
        state.fingerprints[fingerprint] = now
        if action is InitiativeAction.FOLLOW_UP and chain_id is not None:
            state.followups[chain_id] = state.followups.get(chain_id, 0) + 1
        return proposal

    def _fingerprint(
        self,
        core_id: str,
        action: InitiativeAction,
        room_id: str | None,
        target_core_id: str | None,
        body: str | None,
    ) -> str:
        material = "|".join(
            (
                core_id,
                action.value,
                room_id or "",
                target_core_id or "",
                _WHITESPACE.sub(" ", (body or "").strip().casefold()),
            )
        )
        return sha256(material.encode("utf-8")).hexdigest()

    def _set_status(
        self, proposal: SocialProposal, status: ProposalStatus
    ) -> SocialProposal:
        updated = SocialProposal(
            proposal_id=proposal.proposal_id,
            core_id=proposal.core_id,
            action=proposal.action,
            status=status,
            rationale=proposal.rationale,
            created_at=proposal.created_at,
            expires_at=proposal.expires_at,
            room_id=proposal.room_id,
            target_core_id=proposal.target_core_id,
            body=proposal.body,
            chain_id=proposal.chain_id,
        )
        self._remember_proposal(updated)
        state = self._states.get(proposal.core_id)
        if state is not None and status is not ProposalStatus.PROPOSED:
            state.open_proposals.discard(proposal.proposal_id)
        return updated

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def execute(self, proposal_id: str) -> SocialExecution:
        proposal = self.proposal(proposal_id)
        if proposal.status is not ProposalStatus.PROPOSED:
            raise ValueError("social proposal is not executable")
        now = self._now()
        if now >= proposal.expires_at:
            self._set_status(proposal, ProposalStatus.EXPIRED)
            return SocialExecution(
                proposal_id,
                ProposalStatus.EXPIRED,
                now,
                reason="proposal expired",
            )
        state = self._state(proposal.core_id)
        if self._stopped_all or state.stopped or not state.active:
            self._set_status(proposal, ProposalStatus.STOPPED)
            return SocialExecution(
                proposal_id,
                ProposalStatus.STOPPED,
                now,
                reason="owner stopped social initiative",
            )
        if state.remaining_budget <= 0:
            self._set_status(proposal, ProposalStatus.BLOCKED)
            return SocialExecution(
                proposal_id,
                ProposalStatus.BLOCKED,
                now,
                reason="initiative budget is exhausted",
            )
        actor = self._conversation.actor(proposal.core_id)
        message: ChatMessage | None = None
        invitation: RoomInvitation | None = None
        room_id = proposal.room_id
        try:
            if proposal.action in {
                InitiativeAction.PROPOSE,
                InitiativeAction.FOLLOW_UP,
            }:
                assert proposal.room_id is not None
                assert proposal.body is not None
                message = self._conversation.post(
                    actor, proposal.room_id, proposal.body
                )
            elif proposal.action is InitiativeAction.INVITE:
                assert proposal.target_core_id is not None
                if proposal.room_id is not None:
                    invitation = self._conversation.invite_core(
                        actor, proposal.room_id, proposal.target_core_id
                    )
                    room_id = proposal.room_id
                else:
                    channel = self._conversation.open_core_direct(
                        proposal.core_id, proposal.target_core_id
                    )
                    room_id = channel.room_id
                    pending = self._conversation.pending_invitations(
                        actor, room_id=room_id
                    )
                    for item in pending:
                        if (
                            item.invitee_id == proposal.target_core_id
                            and item.status is InvitationStatus.PENDING
                        ):
                            invitation = item
                            break
                    if invitation is None:
                        raise LookupError("direct invitation was not created")
                self._invite_ids[proposal.proposal_id] = invitation.invite_id
            elif proposal.action is InitiativeAction.LEAVE:
                assert proposal.room_id is not None
                self._conversation.leave_channel(
                    proposal.core_id, proposal.room_id
                )
            else:
                raise ValueError("unsupported social action")
        except (PermissionError, LookupError, ValueError) as error:
            self._set_status(proposal, ProposalStatus.BLOCKED)
            return SocialExecution(
                proposal_id,
                ProposalStatus.BLOCKED,
                now,
                room_id=room_id,
                reason=f"chat action was refused: {type(error).__name__}",
            )
        self._set_status(proposal, ProposalStatus.EXECUTED)
        state.remaining_budget -= 1
        return SocialExecution(
            proposal_id,
            ProposalStatus.EXECUTED,
            now,
            room_id=room_id,
            message_id=None if message is None else message.message_id,
            invitation_id=None if invitation is None else invitation.invite_id,
        )

    def decline_invitation(
        self, proposal_id: str, *, by_core_id: str
    ) -> SocialProposal:
        proposal = self.proposal(proposal_id)
        if proposal.action is not InitiativeAction.INVITE:
            raise ValueError("only invitation proposals can be declined")
        _identifier(by_core_id, "by_core_id")
        if (
            proposal.target_core_id is not None
            and proposal.target_core_id != by_core_id
        ):
            raise PermissionError("only the invited Core may decline")
        invite_id = self._invite_ids.get(proposal.proposal_id)
        now = self._now()
        if invite_id is not None:
            self._conversation.decline_invitation(
                self._conversation.actor(by_core_id), invite_id
            )
        key = (
            proposal.action.value,
            proposal.room_id or "",
            proposal.target_core_id or "",
        )
        state = self._state(proposal.core_id)
        state.declined_until[key] = now + self._limits.declined_invitation_cooldown
        return self._set_status(proposal, ProposalStatus.DECLINED)

    def withdraw(self, proposal_id: str, *, core_id: str) -> SocialProposal:
        proposal = self.proposal(proposal_id)
        _identifier(core_id, "core_id")
        if proposal.core_id != core_id:
            raise PermissionError("only the proposing Core may withdraw")
        if proposal.status is not ProposalStatus.PROPOSED:
            raise ValueError("social proposal is not open")
        return self._set_status(proposal, ProposalStatus.WITHDRAWN)


__all__ = [
    "InitiativeAction",
    "InitiativeLimits",
    "MultiCoreSocial",
    "ProposalStatus",
    "SocialCoreStatus",
    "SocialExecution",
    "SocialProposal",
]
