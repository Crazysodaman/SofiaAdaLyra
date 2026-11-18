"""Voluntary Core governance engine.

The engine composes the inert governance contracts with explicit membership,
deterministic ballots and canonical persistence.  It is not a Platform
authority: every consequential capability remains behind the existing SAFE,
RUN, ACT, Fleet and Platform authorization owners.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Iterable
from uuid import UUID, uuid4

from sofia.platform.social.autonomy.contracts import SystemClock
from sofia.platform.social.governance.contracts import (
    Ballot,
    BallotChoice,
    CoordinatorStatus,
    CoordinatorTerm,
    DecisionProcedure,
    GovernanceConflict,
    GovernanceDenied,
    GovernanceError,
    GovernanceGroup,
    GovernancePolicy,
    GroupLifecycle,
    GroupMember,
    MemberState,
    Nomination,
    Proposal,
    ProposalStatus,
    ProposalType,
    Resolution,
    ResolutionOutcome,
    TallyResult,
    coordinator_term_bounds,
    tally_proposal,
)
from sofia.platform.social.governance.integration import (
    CoreAdmission,
    DenyAllAdmission,
    NotStopped,
    RoomKindSource,
    StopSeam,
)
from sofia.platform.social.governance.store import GovernanceStore


PUBLIC_ROOM_KINDS = frozenset({"general", "public", "direct"})


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    expired_term_ids: tuple[UUID, ...] = ()
    resolved_proposal_ids: tuple[UUID, ...] = ()
    deferred: bool = False


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise GovernanceError(f"{label} must be a nonzero UUID")
    return value


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise GovernanceError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


class GovernanceEngine:
    """Leaderless-by-default group, proposal and ballot service."""

    def __init__(
        self,
        store: GovernanceStore,
        *,
        admission: CoreAdmission | None = None,
        stop: StopSeam | None = None,
        rooms: RoomKindSource | None = None,
        clock=None,
    ) -> None:
        if not isinstance(store, GovernanceStore):
            raise TypeError("store must be GovernanceStore")
        self.store = store
        self.admission = admission or DenyAllAdmission()
        self.stop = stop or NotStopped()
        self.rooms = rooms
        self._clock = clock or SystemClock()

    # ------------------------------------------------------------------
    # Common validation
    # ------------------------------------------------------------------
    def _now(self, value: datetime | None) -> datetime:
        return _utc(self._clock.now() if value is None else value, "now")

    def _is_stopped(self) -> bool:
        probe = getattr(self.stop, "is_operator_stopped", None)
        return bool(probe()) if callable(probe) else True

    def _require_actor(
        self,
        core_id: UUID,
        *,
        generation: int | None = None,
        federation_generation: int | None = None,
    ) -> UUID:
        _uuid(core_id, "core_id")
        if self._is_stopped():
            raise GovernanceDenied("operator STOP suspends governance mutations")
        if not self.admission.is_active_approved(core_id):
            raise GovernanceDenied("Core is not an active approved installed Core")
        if generation is not None:
            current = self.admission.generation(core_id)
            if current is None or current != generation:
                raise GovernanceDenied("stale Core generation")
        if federation_generation is not None:
            current_federation = self.admission.federation_generation(core_id)
            if (
                current_federation is None
                or current_federation != federation_generation
            ):
                raise GovernanceDenied("stale federation generation")
        return core_id

    def _require_group(self, group_id: UUID) -> GovernanceGroup:
        group = self.store.load_group(group_id)
        if group is None:
            raise LookupError("governance group does not exist")
        return group

    def _require_eligible_member(
        self,
        group: GovernanceGroup,
        core_id: UUID,
        *,
        generation: int | None = None,
        federation_generation: int | None = None,
    ) -> GroupMember:
        self._require_actor(
            core_id,
            generation=generation,
            federation_generation=federation_generation,
        )
        member = group.member(core_id)
        if member is None or not member.eligible:
            raise GovernanceDenied("Core is not an explicit governing member")
        return member

    def _require_group_room(
        self, group: GovernanceGroup, room_id: str | None
    ) -> None:
        if room_id is None:
            return
        if room_id not in group.room_ids:
            raise GovernanceDenied("room is outside the group audience")
        if self.rooms is not None:
            kind = self.rooms.room_kind(room_id)
            if kind in PUBLIC_ROOM_KINDS or kind is None:
                raise GovernanceDenied(
                    "governance evidence cannot be read or projected in a "
                    "general, public or direct room"
                )

    def _idempotent(
        self, idempotency_key: str | None, event_type: str
    ) -> dict[str, object] | None:
        if idempotency_key is None:
            return None
        prior = self.store.lookup_idempotency(idempotency_key)
        if prior is None:
            return None
        if prior["event_type"] != event_type:
            raise GovernanceConflict(
                "idempotency key belongs to a different governance operation"
            )
        payload = prior["payload"]
        if not isinstance(payload, dict):
            raise GovernanceConflict("idempotency evidence is malformed")
        return payload

    def _idempotent_group(
        self, prior: dict[str, object], group_id: UUID
    ) -> GovernanceGroup:
        if prior.get("group_id") != str(group_id):
            raise GovernanceConflict(
                "idempotency key belongs to a different governance group"
            )
        return self._require_group(group_id)

    @staticmethod
    def _with_lifecycle(
        group: GovernanceGroup, lifecycle: GroupLifecycle, now: datetime
    ) -> GovernanceGroup:
        return replace(
            group,
            lifecycle=lifecycle,
            revision=group.revision + 1,
            updated_at=now,
        )

    @staticmethod
    def _founders_resolved(
        group: GovernanceGroup,
        members: tuple[GroupMember, ...] | None = None,
    ) -> bool:
        founding = set(group.founding_member_ids)
        roster = group.members if members is None else members
        return all(
            member.state is not MemberState.INVITED
            for member in roster
            if member.core_id in founding
        )

    def _accepted_candidates(self, proposal_id: UUID) -> frozenset[UUID]:
        return frozenset(
            nomination.candidate_core_id
            for nomination in self.store.nominations(proposal_id)
            if nomination.accepted is True
        )

    # ------------------------------------------------------------------
    # Groups and voluntary membership
    # ------------------------------------------------------------------
    def create_group(
        self,
        *,
        actor_core_id: UUID,
        name: str,
        purpose: str,
        room_ids: Iterable[str],
        founding_core_ids: Iterable[UUID],
        now: datetime | None = None,
        policy: GovernancePolicy | None = None,
        idempotency_key: str | None = None,
        generation: int | None = None,
        federation_generation: int | None = None,
    ) -> GovernanceGroup:
        stamp = self._now(now)
        self._require_actor(
            actor_core_id,
            generation=generation,
            federation_generation=federation_generation,
        )
        founders = tuple(founding_core_ids)
        rooms = tuple(room_ids)
        prior = self._idempotent(idempotency_key, "governance.group.created")
        if prior is not None:
            if (
                prior.get("name") != name
                or prior.get("purpose") != purpose
                or prior.get("founding_core_ids")
                != [str(item) for item in founders]
            ):
                raise GovernanceConflict(
                    "idempotency key was reused for a different group request"
                )
            group = self.store.load_group(prior["group_id"])
            if group is None:
                raise GovernanceConflict("idempotent group evidence is incomplete")
            return group

        if actor_core_id not in founders:
            raise GovernanceDenied("the proposing Core must be a founder")
        for core_id in founders:
            self._require_actor(core_id)
        effective_policy = policy or GovernancePolicy()
        members = tuple(
            GroupMember(
                core_id=core_id,
                state=MemberState.INVITED,
                joined_at=stamp,
                joined_epoch=1,
                governance_opted_in=False,
                consented_policy_digest=None,
            )
            for core_id in founders
        )
        group = GovernanceGroup(
            group_id=uuid4(),
            name=name,
            purpose=purpose,
            room_ids=rooms,
            revision=1,
            roster_epoch=1,
            lifecycle=GroupLifecycle.PROPOSED,
            policy=effective_policy,
            members=members,
            founding_member_ids=founders,
            created_at=stamp,
            updated_at=stamp,
        )
        self.store.save_group(
            group,
            actor_id=str(actor_core_id),
            occurred_at=stamp,
            event_type="governance.group.created",
            idempotency_key=idempotency_key,
            extra_payload={
                "name": name,
                "purpose": purpose,
                "founding_core_ids": [str(item) for item in founders],
            },
        )
        return group

    def open_invitations(
        self,
        *,
        actor_core_id: UUID,
        group_id: UUID,
        now: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> GovernanceGroup:
        stamp = self._now(now)
        self._require_actor(actor_core_id)
        prior = self._idempotent(idempotency_key, "governance.group.inviting")
        if prior is not None:
            return self._idempotent_group(prior, group_id)
        group = self._require_group(group_id)
        if actor_core_id not in group.founding_member_ids:
            raise GovernanceDenied("only a founder can open group invitations")
        if group.lifecycle is not GroupLifecycle.PROPOSED:
            raise GovernanceConflict("group invitations are already open")
        updated = self._with_lifecycle(group, GroupLifecycle.INVITING, stamp)
        self.store.save_group(
            updated,
            actor_id=str(actor_core_id),
            occurred_at=stamp,
            expected_revision=group.revision,
            event_type="governance.group.inviting",
            idempotency_key=idempotency_key,
        )
        return updated

    def respond_to_invitation(
        self,
        *,
        actor_core_id: UUID,
        group_id: UUID,
        accept: bool,
        now: datetime | None = None,
        idempotency_key: str | None = None,
        generation: int | None = None,
        federation_generation: int | None = None,
    ) -> GovernanceGroup:
        stamp = self._now(now)
        self._require_actor(
            actor_core_id,
            generation=generation,
            federation_generation=federation_generation,
        )
        if type(accept) is not bool:
            raise GovernanceError("accept must be boolean")
        event_type = (
            "governance.member.accepted" if accept else "governance.member.declined"
        )
        prior = self._idempotent(idempotency_key, event_type)
        if prior is not None:
            if prior.get("core_id") != str(actor_core_id) or prior.get("accept") is not accept:
                raise GovernanceConflict("idempotency evidence does not match this response")
            return self._idempotent_group(prior, group_id)

        group = self._require_group(group_id)
        if group.lifecycle is GroupLifecycle.DISSOLVED:
            raise GovernanceConflict("a dissolved group cannot enroll members")
        member = group.member(actor_core_id)
        if member is None:
            raise GovernanceDenied("Core was not invited to this group")
        if member.state is not MemberState.INVITED:
            if accept and member.eligible:
                return group
            raise GovernanceConflict("this invitation was already resolved")

        new_epoch = group.roster_epoch + 1
        if accept:
            replacement = GroupMember(
                core_id=member.core_id,
                state=MemberState.ACTIVE,
                joined_at=stamp,
                joined_epoch=new_epoch,
                governance_opted_in=True,
                consented_policy_digest=group.policy.digest,
            )
        else:
            replacement = GroupMember(
                core_id=member.core_id,
                state=MemberState.DECLINED,
                joined_at=member.joined_at,
                joined_epoch=member.joined_epoch,
                governance_opted_in=False,
                consented_policy_digest=None,
            )
        roster = tuple(
            replacement if item.core_id == actor_core_id else item
            for item in group.members
        )
        lifecycle = group.lifecycle
        if group.lifecycle in {
            GroupLifecycle.PROPOSED,
            GroupLifecycle.INVITING,
            GroupLifecycle.VOLUNTARY_MEMBER,
        }:
            lifecycle = (
                GroupLifecycle.VOLUNTARY_MEMBER
                if self._founders_resolved(group, roster)
                else GroupLifecycle.INVITING
            )
        updated = group.with_members(
            roster, lifecycle=lifecycle, updated_at=stamp
        )
        self.store.save_group(
            updated,
            actor_id=str(actor_core_id),
            occurred_at=stamp,
            expected_revision=group.revision,
            event_type=event_type,
            idempotency_key=idempotency_key,
            extra_payload={
                "core_id": str(actor_core_id),
                "accept": accept,
            },
        )
        return updated

    def activate_group(
        self,
        *,
        actor_core_id: UUID,
        group_id: UUID,
        now: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> GovernanceGroup:
        stamp = self._now(now)
        prior = self._idempotent(idempotency_key, "governance.group.active")
        if prior is not None:
            return self._idempotent_group(prior, group_id)
        group = self._require_group(group_id)
        self._require_eligible_member(group, actor_core_id)
        if group.lifecycle is GroupLifecycle.ACTIVE:
            return group
        if group.lifecycle is not GroupLifecycle.VOLUNTARY_MEMBER:
            raise GovernanceConflict(
                "all founding participants must respond before activation"
            )
        if not self._founders_resolved(group):
            raise GovernanceConflict("founding invitations are still pending")
        if not group.eligible_member_ids():
            raise GovernanceDenied("an active group requires at least one eligible member")
        updated = self._with_lifecycle(group, GroupLifecycle.ACTIVE, stamp)
        self.store.save_group(
            updated,
            actor_id=str(actor_core_id),
            occurred_at=stamp,
            expected_revision=group.revision,
            event_type="governance.group.active",
            idempotency_key=idempotency_key,
        )
        return updated

    def invite_member(
        self,
        *,
        actor_core_id: UUID,
        group_id: UUID,
        core_id: UUID,
        now: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> GovernanceGroup:
        stamp = self._now(now)
        prior = self._idempotent(idempotency_key, "governance.member.invited")
        if prior is not None:
            return self._idempotent_group(prior, group_id)
        group = self._require_group(group_id)
        self._require_eligible_member(group, actor_core_id)
        if group.lifecycle not in {
            GroupLifecycle.VOLUNTARY_MEMBER,
            GroupLifecycle.ACTIVE,
        }:
            raise GovernanceConflict("group is not accepting invitations")
        self._require_actor(core_id)
        if group.member(core_id) is not None:
            raise GovernanceConflict("Core already has a group membership record")
        invited = GroupMember(
            core_id=core_id,
            state=MemberState.INVITED,
            joined_at=stamp,
            joined_epoch=group.roster_epoch + 1,
            governance_opted_in=False,
            consented_policy_digest=None,
        )
        updated = group.with_members(
            (*group.members, invited),
            lifecycle=group.lifecycle,
            updated_at=stamp,
        )
        self.store.save_group(
            updated,
            actor_id=str(actor_core_id),
            occurred_at=stamp,
            expected_revision=group.revision,
            event_type="governance.member.invited",
            idempotency_key=idempotency_key,
        )
        return updated

    def leave_group(
        self,
        *,
        actor_core_id: UUID,
        group_id: UUID,
        now: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> GovernanceGroup:
        stamp = self._now(now)
        prior = self._idempotent(idempotency_key, "governance.member.left")
        if prior is not None:
            return self._idempotent_group(prior, group_id)
        group = self._require_group(group_id)
        member = self._require_eligible_member(group, actor_core_id)
        replacement = GroupMember(
            core_id=member.core_id,
            state=MemberState.LEFT,
            joined_at=member.joined_at,
            joined_epoch=member.joined_epoch,
            governance_opted_in=False,
            consented_policy_digest=None,
        )
        roster = tuple(
            replacement if item.core_id == actor_core_id else item
            for item in group.members
        )
        lifecycle = group.lifecycle
        if not any(item.eligible for item in roster):
            lifecycle = GroupLifecycle.PAUSED
        updated = group.with_members(
            roster, lifecycle=lifecycle, updated_at=stamp
        )
        self.store.save_group(
            updated,
            actor_id=str(actor_core_id),
            occurred_at=stamp,
            expected_revision=group.revision,
            event_type="governance.member.left",
            idempotency_key=idempotency_key,
        )
        return updated

    # ------------------------------------------------------------------
    # Proposals and nominations
    # ------------------------------------------------------------------
    def open_proposal(
        self,
        *,
        actor_core_id: UUID,
        group_id: UUID,
        proposal_type: ProposalType,
        title: str,
        text: str,
        now: datetime | None = None,
        duration: timedelta = timedelta(days=1),
        procedure: DecisionProcedure | None = None,
        candidate_core_ids: Iterable[UUID] = (),
        idempotency_key: str | None = None,
        generation: int | None = None,
        federation_generation: int | None = None,
    ) -> Proposal:
        stamp = self._now(now)
        if not isinstance(proposal_type, ProposalType):
            raise GovernanceError("proposal_type must be ProposalType")
        if not isinstance(duration, timedelta) or duration <= timedelta(0):
            raise GovernanceError("duration must be positive")
        prior = self._idempotent(idempotency_key, "governance.proposal.opened")
        if prior is not None:
            if prior.get("group_id") != str(group_id):
                raise GovernanceConflict(
                    "idempotency key belongs to a different governance group"
                )
            group = self._require_group(prior["group_id"])
            proposal = self.store.load_proposal(group.group_id, prior["proposal_id"])
            if proposal is None:
                raise GovernanceConflict("idempotent proposal evidence is incomplete")
            if (
                proposal.proposal_type is not proposal_type
                or proposal.title != title
            ):
                raise GovernanceConflict(
                    "idempotency key was reused for a different proposal"
                )
            return proposal

        group = self._require_group(group_id)
        self._require_eligible_member(
            group,
            actor_core_id,
            generation=generation,
            federation_generation=federation_generation,
        )
        if group.lifecycle is not GroupLifecycle.ACTIVE:
            raise GovernanceConflict("only an active group can consider proposals")
        selected = procedure or group.policy.procedure
        if selected is not group.policy.procedure:
            raise GovernanceDenied(
                "a proposal cannot silently replace the adopted group procedure"
            )
        if proposal_type is ProposalType.COORDINATOR_ELECTION:
            if not group.policy.allow_coordinator:
                raise GovernanceDenied("this group has not opted into a coordinator")
            if selected not in {
                DecisionProcedure.SIMPLE_MAJORITY,
                DecisionProcedure.APPROVAL,
            }:
                raise GovernanceDenied("elections require majority or approval voting")
        candidates = tuple(candidate_core_ids)
        eligible = tuple(
            core_id
            for core_id in group.eligible_member_ids()
            if self.admission.is_active_approved(core_id)
        )
        if not eligible:
            raise GovernanceConflict("no active approved eligible members")
        if actor_core_id not in eligible:
            raise GovernanceDenied("proposer is not in the eligible snapshot")
        if proposal_type is ProposalType.COORDINATOR_ELECTION:
            if len(eligible) < group.policy.minimum_leadership_electorate:
                raise GovernanceDenied("too few eligible members for an election")
        binding = selected is not DecisionProcedure.DISCUSSION
        proposal = Proposal(
            proposal_id=uuid4(),
            group_id=group.group_id,
            proposer_core_id=actor_core_id,
            proposal_type=proposal_type,
            title=title,
            text=text,
            policy_digest=group.policy.digest,
            procedure=selected,
            electorate=eligible,
            roster_epoch=group.roster_epoch,
            opens_at=stamp,
            closes_at=stamp + duration,
            quorum=group.policy.quorum_for(len(eligible)),
            status=ProposalStatus.OPEN,
            created_at=stamp,
            revision=1,
            candidate_core_ids=candidates,
            binding=binding,
            coordinator_term_days=group.policy.coordinator_term_days,
        )
        self.store.save_proposal(
            proposal,
            actor_id=str(actor_core_id),
            occurred_at=stamp,
            event_type="governance.proposal.opened",
            idempotency_key=idempotency_key,
        )
        for candidate in candidates:
            self.store.save_nomination(
                Nomination(
                    nomination_id=uuid4(),
                    proposal_id=proposal.proposal_id,
                    candidate_core_id=candidate,
                    nominated_by_core_id=actor_core_id,
                    accepted=None,
                    created_at=stamp,
                    resolved_at=None,
                ),
                actor_id=str(actor_core_id),
                occurred_at=stamp,
            )
        return proposal

    def accept_nomination(
        self,
        *,
        actor_core_id: UUID,
        proposal_id: UUID,
        accept: bool,
        now: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> Nomination:
        stamp = self._now(now)
        if type(accept) is not bool:
            raise GovernanceError("accept must be boolean")
        self._require_actor(actor_core_id)
        prior = self._idempotent(idempotency_key, "governance.nomination.resolved")
        if prior is not None:
            if prior.get("proposal_id") != str(proposal_id):
                raise GovernanceConflict("idempotency evidence names another proposal")
            for nomination in self.store.nominations(proposal_id):
                if nomination.candidate_core_id == actor_core_id:
                    return nomination
            raise GovernanceConflict("idempotent nomination evidence is incomplete")

        proposal = self.store.resolution_for_proposal(proposal_id)
        if proposal is not None:
            raise GovernanceConflict("proposal is already resolved")
        target = self._proposal_by_id(proposal_id)
        if target.proposal_type is not ProposalType.COORDINATOR_ELECTION:
            raise GovernanceConflict("only elections have candidate nominations")
        if actor_core_id not in target.candidate_core_ids:
            raise GovernanceDenied("Core is not a candidate in this election")
        if actor_core_id not in target.electorate:
            raise GovernanceDenied("candidate is outside the frozen electorate")
        if not target.is_open(stamp):
            raise GovernanceConflict("candidate acceptance is closed")
        group = self._require_group(target.group_id)
        self._require_eligible_member(group, actor_core_id)

        existing = next(
            (
                item for item in self.store.nominations(proposal_id)
                if item.candidate_core_id == actor_core_id
            ),
            None,
        )
        nomination = Nomination(
            nomination_id=uuid4() if existing is None else existing.nomination_id,
            proposal_id=proposal_id,
            candidate_core_id=actor_core_id,
            nominated_by_core_id=(
                target.proposer_core_id if existing is None
                else existing.nominated_by_core_id
            ),
            accepted=accept,
            created_at=stamp if existing is None else existing.created_at,
            resolved_at=stamp,
        )
        self.store.save_nomination(
            nomination,
            actor_id=str(actor_core_id),
            occurred_at=stamp,
            idempotency_key=idempotency_key,
        )
        return nomination

    def _proposal_by_id(self, proposal_id: UUID) -> Proposal:
        with self.store.reader() as db:
            row = db.execute(
                "SELECT group_id FROM governance_proposal WHERE proposal_id=?",
                (str(proposal_id),),
            ).fetchone()
        if row is None:
            raise LookupError("proposal does not exist")
        proposal = self.store.load_proposal(row["group_id"], proposal_id)
        if proposal is None:
            raise LookupError("proposal does not exist")
        return proposal

    # ------------------------------------------------------------------
    # Ballots
    # ------------------------------------------------------------------
    def cast_ballot(
        self,
        *,
        actor_core_id: UUID,
        proposal_id: UUID,
        choice: BallotChoice,
        idempotency_key: str,
        expected_revision: int | None = 0,
        approvals: Iterable[UUID] = (),
        now: datetime | None = None,
        generation: int | None = None,
        federation_generation: int | None = None,
    ) -> Ballot:
        stamp = self._now(now)
        if not isinstance(choice, BallotChoice):
            raise GovernanceError("choice must be BallotChoice")
        self._require_actor(
            actor_core_id,
            generation=generation,
            federation_generation=federation_generation,
        )
        approval_ids = tuple(approvals)
        prior = self._idempotent(idempotency_key, "governance.ballot.cast")
        if prior is not None:
            if (
                prior.get("core_id") != str(actor_core_id)
                or prior.get("proposal_id") != str(proposal_id)
                or prior.get("choice") != choice.value
                or prior.get("approvals") != [str(item) for item in approval_ids]
            ):
                raise GovernanceConflict(
                    "idempotency key was reused for a different ballot"
                )
            proposal = self._proposal_by_id(proposal_id)
            current = self.store.current_ballot(
                proposal.group_id, proposal_id, actor_core_id
            )
            if current is None:
                raise GovernanceConflict("idempotent ballot evidence is incomplete")
            return current

        if approval_ids and choice is not BallotChoice.YES:
            raise GovernanceError("approval selections require a YES ballot")
        proposal = self._proposal_by_id(proposal_id)
        group = self._require_group(proposal.group_id)
        if group.lifecycle is not GroupLifecycle.ACTIVE:
            raise GovernanceConflict("group is not active")
        if group.roster_epoch != proposal.roster_epoch:
            raise GovernanceConflict("proposal roster epoch is stale")
        if group.policy.digest != proposal.policy_digest:
            raise GovernanceConflict("proposal policy digest is stale")
        if actor_core_id not in proposal.electorate:
            raise GovernanceDenied("Core is outside the frozen electorate")
        self._require_eligible_member(group, actor_core_id)
        proposal.require_open(stamp)

        if proposal.proposal_type is ProposalType.COORDINATOR_ELECTION:
            accepted = self._accepted_candidates(proposal_id)
            if any(
                candidate not in accepted
                for candidate in proposal.candidate_core_ids
            ):
                raise GovernanceDenied(
                    "every candidate must explicitly accept before balloting"
                )
            if any(candidate not in proposal.candidate_core_ids for candidate in approval_ids):
                raise GovernanceDenied("approval names a candidate outside the ballot")
        elif approval_ids:
            raise GovernanceDenied("approval selections belong to elections only")

        current = self.store.current_ballot(
            group.group_id, proposal_id, actor_core_id
        )
        if current is None:
            if expected_revision not in (None, 0):
                raise GovernanceConflict("first ballot must use expected revision 0")
            revision = 1
            ballot_id = uuid4()
        else:
            if expected_revision is None or expected_revision != current.revision:
                raise GovernanceConflict("ballot revision changed concurrently")
            revision = current.revision + 1
            ballot_id = current.ballot_id
        ballot = Ballot(
            ballot_id=ballot_id,
            proposal_id=proposal_id,
            core_id=actor_core_id,
            choice=choice,
            revision=revision,
            idempotency_key=idempotency_key,
            cast_at=stamp,
            approvals=approval_ids,
        )
        return self.store.save_ballot(
            group.group_id,
            ballot,
            actor_id=str(actor_core_id),
            occurred_at=stamp,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
        )

    # ------------------------------------------------------------------
    # Resolution, elections, recall and resignation
    # ------------------------------------------------------------------
    def _build_rejected_election_tally(
        self, proposal: Proposal, ballots: tuple[Ballot, ...]
    ) -> TallyResult:
        yes = sum(1 for ballot in ballots if ballot.choice is BallotChoice.YES)
        no = sum(1 for ballot in ballots if ballot.choice is BallotChoice.NO)
        return TallyResult(
            outcome=ResolutionOutcome.REJECTED,
            yes=yes,
            no=no,
            abstain=len(ballots) - yes - no,
            submitted=len(ballots),
            eligible_count=len(proposal.electorate),
            quorum=proposal.quorum,
            binding=True,
            reason="candidate did not explicitly accept nomination",
        )

    def _resolve_proposal(
        self,
        proposal: Proposal,
        group: GovernanceGroup,
        *,
        now: datetime,
        actor_id: str,
        idempotency_key: str | None,
    ) -> Resolution:
        existing = self.store.resolution_for_proposal(proposal.proposal_id)
        if existing is not None:
            return existing
        ballots = self.store.ballots(group.group_id, proposal.proposal_id)
        accepted = self._accepted_candidates(proposal.proposal_id)
        if (
            proposal.proposal_type is ProposalType.COORDINATOR_ELECTION
            and any(
                candidate not in accepted
                for candidate in proposal.candidate_core_ids
            )
        ):
            tally = self._build_rejected_election_tally(proposal, ballots)
        else:
            tally = tally_proposal(
                proposal,
                ballots,
                now=now,
                accepted_candidate_ids=accepted,
            )

        term: CoordinatorTerm | None = None
        superseded: tuple[CoordinatorTerm, ...] = ()
        group_update: GovernanceGroup | None = None
        evidence = tuple(
            f"ballot:{ballot.ballot_id}:{ballot.revision}" for ballot in ballots[:64]
        )

        if proposal.proposal_type is ProposalType.COORDINATOR_ELECTION:
            boundary = coordinator_term_bounds(proposal, tally, now=now)
            previous = self.store.active_term(group.group_id)
            if previous is not None:
                superseded = (
                    replace(
                        previous,
                        status=CoordinatorStatus.EXPIRED,
                        revision=previous.revision + 1,
                    ),
                )
                evidence = evidence + (f"term:{previous.term_id}",)
            if boundary is not None and tally.coordinator_core_id is not None:
                term = CoordinatorTerm(
                    term_id=uuid4(),
                    group_id=group.group_id,
                    core_id=tally.coordinator_core_id,
                    proposal_id=proposal.proposal_id,
                    starts_at=boundary[0],
                    expires_at=boundary[1],
                    status=CoordinatorStatus.ACTIVE,
                    revision=1,
                )
        elif (
            proposal.proposal_type in {ProposalType.RECALL, ProposalType.DISSOLUTION}
            and tally.outcome is ResolutionOutcome.ADOPTED
        ):
            previous = self.store.active_term(group.group_id)
            if previous is not None:
                superseded = (
                    replace(
                        previous,
                        status=CoordinatorStatus.RECALLED,
                        revision=previous.revision + 1,
                    ),
                )
                evidence = evidence + (f"term:{previous.term_id}",)
            if proposal.proposal_type is ProposalType.DISSOLUTION:
                group_update = self._with_lifecycle(
                    group, GroupLifecycle.DISSOLVED, now
                )

        resolution = Resolution(
            resolution_id=uuid4(),
            proposal_id=proposal.proposal_id,
            group_id=group.group_id,
            outcome=tally.outcome,
            tally=tally,
            policy_digest=proposal.policy_digest,
            resolved_at=now,
            evidence_refs=evidence,
            coordinator_core_id=(
                None if term is None else term.core_id
            ),
            term_starts_at=None if term is None else term.starts_at,
            term_expires_at=None if term is None else term.expires_at,
        )
        resolved = replace(
            proposal,
            status=ProposalStatus.RESOLVED,
            revision=proposal.revision + 1,
        )
        return self.store.finalize_proposal(
            proposal=resolved,
            resolution=resolution,
            actor_id=actor_id,
            occurred_at=now,
            term=term,
            superseded_terms=superseded,
            group_update=group_update,
            idempotency_key=idempotency_key,
        )

    def close_and_resolve(
        self,
        *,
        actor_core_id: UUID,
        proposal_id: UUID,
        now: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> Resolution:
        stamp = self._now(now)
        prior = self._idempotent(idempotency_key, "governance.proposal.resolved")
        if prior is not None:
            resolution = self.store.resolution_for_proposal(proposal_id)
            if resolution is None:
                raise GovernanceConflict("idempotent resolution evidence is incomplete")
            return resolution
        proposal = self._proposal_by_id(proposal_id)
        group = self._require_group(proposal.group_id)
        self._require_eligible_member(group, actor_core_id)
        existing = self.store.resolution_for_proposal(proposal_id)
        if existing is not None:
            return existing
        if proposal.status is not ProposalStatus.OPEN:
            raise GovernanceConflict("proposal is not open")
        proposal.require_closed(stamp)
        return self._resolve_proposal(
            proposal,
            group,
            now=stamp,
            actor_id=str(actor_core_id),
            idempotency_key=idempotency_key,
        )

    def open_runoff(
        self,
        *,
        actor_core_id: UUID,
        proposal_id: UUID,
        now: datetime | None = None,
        duration: timedelta | None = None,
        idempotency_key: str | None = None,
    ) -> Proposal:
        stamp = self._now(now)
        previous = self._proposal_by_id(proposal_id)
        group = self._require_group(previous.group_id)
        self._require_eligible_member(group, actor_core_id)
        resolution = self.store.resolution_for_proposal(proposal_id)
        if resolution is None or resolution.outcome is not ResolutionOutcome.TIED:
            raise GovernanceConflict("a runoff is available only after a tie")
        if previous.proposal_type is not ProposalType.COORDINATOR_ELECTION:
            raise GovernanceConflict("only elections support runoffs")
        if not resolution.tally.candidate_totals:
            raise GovernanceConflict("the tie has no candidate totals")
        top = max(total for _, total in resolution.tally.candidate_totals)
        candidates = tuple(
            candidate
            for candidate, total in resolution.tally.candidate_totals
            if total == top
        )
        if len(candidates) < 2:
            raise GovernanceConflict("the recorded result is not a tie")
        return self.open_proposal(
            actor_core_id=actor_core_id,
            group_id=group.group_id,
            proposal_type=ProposalType.COORDINATOR_ELECTION,
            title=f"Runoff: {previous.title}"[:240],
            text=f"Explicit runoff for tie in proposal {previous.proposal_id}.",
            now=stamp,
            duration=(
                duration
                if duration is not None
                else previous.closes_at - previous.opens_at
            ),
            procedure=previous.procedure,
            candidate_core_ids=candidates,
            idempotency_key=idempotency_key,
        )

    def resign_coordinator(
        self,
        *,
        actor_core_id: UUID,
        group_id: UUID,
        now: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> CoordinatorTerm:
        stamp = self._now(now)
        self._require_actor(actor_core_id)
        prior = self._idempotent(idempotency_key, "governance.coordinator.resigned")
        if prior is not None:
            if prior.get("group_id") != str(group_id):
                raise GovernanceConflict(
                    "idempotency key belongs to a different governance group"
                )
            term = self.store.load_term(prior["term_id"])
            if term is None:
                raise GovernanceConflict("idempotent resignation is incomplete")
            return term
        group = self._require_group(group_id)
        self._require_eligible_member(group, actor_core_id)
        term = self.store.active_term(group_id)
        if term is None:
            raise GovernanceConflict("group has no active coordinator")
        if term.core_id != actor_core_id:
            raise GovernanceDenied("only the coordinator can resign this term")
        if stamp >= term.expires_at:
            updated = replace(
                term,
                status=CoordinatorStatus.EXPIRED,
                revision=term.revision + 1,
            )
            event_type = "governance.coordinator.expired"
        else:
            updated = replace(
                term,
                status=CoordinatorStatus.RESIGNED,
                revision=term.revision + 1,
            )
            event_type = "governance.coordinator.resigned"
        return self.store.save_term(
            updated,
            actor_id=str(actor_core_id),
            occurred_at=stamp,
            expected_revision=term.revision,
            event_type=event_type,
            idempotency_key=idempotency_key,
        )

    # ------------------------------------------------------------------
    # Restart reconciliation (exactly once)
    # ------------------------------------------------------------------
    def reconcile(self, now: datetime | None = None) -> ReconciliationResult:
        stamp = self._now(now)
        if self._is_stopped():
            return ReconciliationResult(deferred=True)
        expired: list[UUID] = []
        resolved: list[UUID] = []
        for term in self.store.active_terms():
            if self._is_stopped():
                return ReconciliationResult(
                    tuple(expired), tuple(resolved), deferred=True
                )
            if stamp < term.expires_at:
                continue
            key = f"reconcile:term:{term.term_id}:{term.expires_at.isoformat()}"
            if self.store.lookup_idempotency(key) is not None:
                continue
            try:
                updated = self.store.save_term(
                    replace(
                        term,
                        status=CoordinatorStatus.EXPIRED,
                        revision=term.revision + 1,
                    ),
                    actor_id="system:governance",
                    occurred_at=stamp,
                    expected_revision=term.revision,
                    event_type="governance.coordinator.expired",
                    idempotency_key=key,
                )
            except GovernanceConflict:
                continue
            expired.append(updated.term_id)

        for proposal in self.store.open_proposals():
            if self._is_stopped():
                return ReconciliationResult(
                    tuple(expired), tuple(resolved), deferred=True
                )
            if stamp < proposal.closes_at:
                continue
            key = f"reconcile:proposal:{proposal.proposal_id}"
            if self.store.lookup_idempotency(key) is not None:
                continue
            group = self.store.load_group(proposal.group_id)
            if group is None:
                continue
            try:
                resolution = self._resolve_proposal(
                    proposal,
                    group,
                    now=stamp,
                    actor_id="system:governance",
                    idempotency_key=key,
                )
            except GovernanceConflict:
                continue
            resolved.append(resolution.proposal_id)
        return ReconciliationResult(tuple(expired), tuple(resolved))

    # ------------------------------------------------------------------
    # Group-scoped read APIs
    # ------------------------------------------------------------------
    def group(self, *, actor_core_id: UUID, group_id: UUID) -> GovernanceGroup:
        group = self._require_group(group_id)
        self._require_eligible_member(group, actor_core_id)
        return group

    def proposals(
        self, *, actor_core_id: UUID, group_id: UUID
    ) -> tuple[Proposal, ...]:
        group = self._require_group(group_id)
        self._require_eligible_member(group, actor_core_id)
        return self.store.list_proposals(group_id)

    def proposal(
        self, *, actor_core_id: UUID, group_id: UUID, proposal_id: UUID
    ) -> Proposal:
        group = self._require_group(group_id)
        self._require_eligible_member(group, actor_core_id)
        proposal = self.store.load_proposal(group_id, proposal_id)
        if proposal is None:
            raise LookupError("proposal does not exist")
        return proposal

    def ballots(
        self, *, actor_core_id: UUID, group_id: UUID, proposal_id: UUID
    ) -> tuple[Ballot, ...]:
        group = self._require_group(group_id)
        self._require_eligible_member(group, actor_core_id)
        return self.store.ballots(group_id, proposal_id)

    def resolution(
        self,
        *,
        actor_core_id: UUID,
        proposal_id: UUID,
        group_id: UUID | None = None,
        room_id: str | None = None,
    ) -> Resolution:
        if group_id is None:
            resolution = self.store.resolution_for_proposal(proposal_id)
            if resolution is None:
                raise LookupError("resolution does not exist")
            group_id = resolution.group_id
        else:
            resolution = self.store.load_resolution(group_id, proposal_id)
            if resolution is None:
                raise LookupError("resolution does not exist")
        group = self._require_group(group_id)
        self._require_eligible_member(group, actor_core_id)
        self._require_group_room(group, room_id)
        return resolution

    def coordinator(
        self, *, actor_core_id: UUID, group_id: UUID, now: datetime | None = None
    ) -> CoordinatorTerm | None:
        stamp = self._now(now)
        group = self._require_group(group_id)
        self._require_eligible_member(group, actor_core_id)
        term = self.store.active_term(group_id)
        if term is None:
            return None
        if stamp >= term.expires_at:
            return None
        return term


__all__ = ["GovernanceEngine", "ReconciliationResult"]
