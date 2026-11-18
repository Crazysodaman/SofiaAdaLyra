from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import replace
from uuid import UUID

import pytest

from sofia.platform.social.governance import (
    BallotChoice,
    DecisionProcedure,
    GovernanceConflict,
    GovernanceDenied,
    GovernanceEngine,
    GovernancePolicy,
    GovernanceStore,
    GroupLifecycle,
    MemberState,
    ProposalType,
    ResolutionOutcome,
    StaticAdmission,
    StaticRoomKindSource,
    coordinator_can,
    project_resolution,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


T0 = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
CORE_A = UUID(int=101)
CORE_B = UUID(int=102)
CORE_C = UUID(int=103)
CORE_D = UUID(int=104)
CORE_E = UUID(int=105)
TWIN_4 = UUID(int=4)
TWIN_5 = UUID(int=5)
UNASSIGNED_7 = UUID(int=7)
GHOST = UUID(int=999)
FOUNDERS = (CORE_A, CORE_B, CORE_C, CORE_D)
ROOMS = {"group-room": "private_group", "general-1": "general"}


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.value = now

    def now(self) -> datetime:
        return self.value

    def set(self, value: datetime) -> None:
        self.value = value


class MutableStop:
    def __init__(self) -> None:
        self.active = False

    def is_operator_stopped(self) -> bool:
        return self.active


def consensus_policy() -> GovernancePolicy:
    return GovernancePolicy(procedure=DecisionProcedure.CONSENSUS)


def majority_policy() -> GovernancePolicy:
    return GovernancePolicy(
        procedure=DecisionProcedure.SIMPLE_MAJORITY,
        allow_coordinator=True,
        coordinator_term_days=7,
    )


def approval_policy() -> GovernancePolicy:
    return GovernancePolicy(
        procedure=DecisionProcedure.APPROVAL,
        allow_coordinator=True,
        coordinator_term_days=7,
    )


def build(tmp_path, *, federation=None, extra_active=()):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = GovernanceStore(path)
    active = set(FOUNDERS) | set(extra_active)
    admission = StaticAdmission(
        active,
        generations={core: 1 for core in active},
        federation_generations=(
            {core: 3 for core in active} if federation is None else federation
        ),
    )
    stop = MutableStop()
    clock = MutableClock(T0)
    engine = GovernanceEngine(
        store,
        admission=admission,
        stop=stop,
        rooms=StaticRoomKindSource(ROOMS),
        clock=clock,
    )
    return path, store, engine, clock, stop


def enrolled_group(engine, policy, *, accept_count=4, prefix="g"):
    group = engine.create_group(
        actor_core_id=CORE_A,
        name="Core Circle",
        purpose="Voluntary discussion and shared projects.",
        room_ids=("group-room",),
        founding_core_ids=FOUNDERS,
        now=T0,
        policy=policy,
        idempotency_key=f"{prefix}:create",
    )
    group = engine.open_invitations(
        actor_core_id=CORE_A,
        group_id=group.group_id,
        now=T0,
        idempotency_key=f"{prefix}:invite-open",
    )
    for index, core_id in enumerate(FOUNDERS):
        group = engine.respond_to_invitation(
            actor_core_id=core_id,
            group_id=group.group_id,
            accept=index < accept_count,
            now=T0 + timedelta(minutes=1 + index),
            idempotency_key=f"{prefix}:respond:{core_id}",
        )
    if accept_count:
        group = engine.activate_group(
            actor_core_id=CORE_A,
            group_id=group.group_id,
            now=T0 + timedelta(minutes=10),
            idempotency_key=f"{prefix}:activate",
        )
    return group


def open_majority(engine, group, *, key="p", candidates=()):
    return engine.open_proposal(
        actor_core_id=CORE_A,
        group_id=group.group_id,
        proposal_type=(
            ProposalType.COORDINATOR_ELECTION
            if candidates
            else ProposalType.GENERAL
        ),
        title="Adopt a shared project" if not candidates else "Elect a coordinator",
        text="A bounded social decision.",
        now=T0 + timedelta(minutes=20),
        duration=timedelta(hours=2),
        candidate_core_ids=candidates,
        idempotency_key=f"{key}:open",
    )


def accept_candidates(engine, proposal, candidates):
    for index, candidate in enumerate(candidates):
        engine.accept_nomination(
            actor_core_id=candidate,
            proposal_id=proposal.proposal_id,
            accept=True,
            now=T0 + timedelta(minutes=25 + index),
            idempotency_key=f"accept:{proposal.proposal_id}:{candidate}",
        )


def vote(engine, proposal, core_id, choice, *, approvals=(), expected=0, key=None, now=None):
    return engine.cast_ballot(
        actor_core_id=core_id,
        proposal_id=proposal.proposal_id,
        choice=choice,
        approvals=approvals,
        expected_revision=expected,
        now=now or T0 + timedelta(minutes=30),
        idempotency_key=key or f"vote:{proposal.proposal_id}:{core_id}:{expected}",
    )


def resolve(engine, proposal, *, at=None):
    return engine.close_and_resolve(
        actor_core_id=CORE_A,
        proposal_id=proposal.proposal_id,
        now=at or T0 + timedelta(hours=3),
        idempotency_key=f"resolve:{proposal.proposal_id}",
    )


def test_gv01_no_opt_in_means_no_leader_and_no_ballot(tmp_path):
    _, store, engine, _, _ = build(tmp_path)
    group = engine.create_group(
        actor_core_id=CORE_A,
        name="Unofficial Circle",
        purpose="A proposal without governance opt-in.",
        room_ids=("group-room",),
        founding_core_ids=FOUNDERS,
        now=T0,
        policy=majority_policy(),
        idempotency_key="gv01:create",
    )
    assert group.lifecycle is GroupLifecycle.PROPOSED
    assert group.eligible_member_ids() == ()
    assert all(member.state is MemberState.INVITED for member in group.members)
    assert store.active_term(group.group_id) is None

    with pytest.raises(GovernanceDenied):
        engine.open_proposal(
            actor_core_id=CORE_A,
            group_id=group.group_id,
            proposal_type=ProposalType.COORDINATOR_ELECTION,
            title="Premature election",
            text="No governing opt-in exists.",
            now=T0,
            candidate_core_ids=(CORE_A,),
        )


def test_gv02_voluntary_consensus_group_is_versioned_and_leaderless(tmp_path):
    _, store, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, consensus_policy(), prefix="gv02")
    assert group.lifecycle is GroupLifecycle.ACTIVE
    assert len(group.eligible_member_ids()) == 4
    assert all(member.governance_opted_in for member in group.members)
    assert group.policy_digest == consensus_policy().digest
    assert store.load_group(group.group_id).policy_digest == group.policy_digest

    proposal = engine.open_proposal(
        actor_core_id=CORE_A,
        group_id=group.group_id,
        proposal_type=ProposalType.GENERAL,
        title="Shared study plan",
        text="Everyone explicitly affirms the same plan.",
        now=T0 + timedelta(minutes=20),
        duration=timedelta(hours=2),
        idempotency_key="gv02:proposal",
    )
    assert proposal.procedure is DecisionProcedure.CONSENSUS
    for core_id in FOUNDERS:
        vote(engine, proposal, core_id, BallotChoice.YES)
    resolution = resolve(engine, proposal)
    assert resolution.outcome is ResolutionOutcome.ADOPTED
    assert resolution.coordinator_core_id is None
    assert store.active_term(group.group_id) is None


def test_gv03_one_member_declines_and_is_not_enrolled(tmp_path):
    _, store, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), accept_count=3, prefix="gv03")
    declined = store.load_group(group.group_id).member(CORE_D)
    assert declined is not None
    assert declined.state is MemberState.DECLINED
    assert not declined.eligible
    assert set(group.eligible_member_ids()) == {CORE_A, CORE_B, CORE_C}

    with pytest.raises(GovernanceDenied):
        engine.open_proposal(
            actor_core_id=CORE_D,
            group_id=group.group_id,
            proposal_type=ProposalType.GENERAL,
            title="Declined outsider",
            text="A declined participant cannot be coerced into governance.",
            now=T0 + timedelta(minutes=20),
        )


def test_gv04_two_of_four_votes_do_not_meet_quorum(tmp_path):
    _, _, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), prefix="gv04")
    proposal = open_majority(engine, group, key="gv04")
    assert proposal.quorum == 3
    vote(engine, proposal, CORE_A, BallotChoice.YES)
    vote(engine, proposal, CORE_B, BallotChoice.NO)
    resolution = resolve(engine, proposal)
    assert resolution.outcome is ResolutionOutcome.NO_QUORUM
    assert resolution.tally.submitted == 2
    assert resolution.coordinator_core_id is None


def test_gv05_three_explicit_votes_including_abstain(tmp_path):
    _, _, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), prefix="gv05")
    proposal = open_majority(engine, group, key="gv05")
    vote(engine, proposal, CORE_A, BallotChoice.YES)
    vote(engine, proposal, CORE_B, BallotChoice.YES)
    vote(engine, proposal, CORE_C, BallotChoice.ABSTAIN)
    resolution = resolve(engine, proposal)
    assert resolution.outcome is ResolutionOutcome.ADOPTED
    assert resolution.tally.yes == 2
    assert resolution.tally.abstain == 1
    assert resolution.tally.submitted == 3


def test_gv06_two_candidate_tie_opens_explicit_runoff(tmp_path):
    _, store, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, approval_policy(), prefix="gv06")
    proposal = open_majority(
        engine, group, key="gv06", candidates=(CORE_A, CORE_B)
    )
    accept_candidates(engine, proposal, (CORE_A, CORE_B))
    vote(engine, proposal, CORE_A, BallotChoice.YES, approvals=(CORE_A,))
    vote(engine, proposal, CORE_B, BallotChoice.YES, approvals=(CORE_A,))
    vote(engine, proposal, CORE_C, BallotChoice.YES, approvals=(CORE_B,))
    vote(engine, proposal, CORE_D, BallotChoice.YES, approvals=(CORE_B,))
    resolution = resolve(engine, proposal)
    assert resolution.outcome is ResolutionOutcome.TIED
    assert resolution.coordinator_core_id is None
    assert store.active_term(group.group_id) is None

    runoff = engine.open_runoff(
        actor_core_id=CORE_A,
        proposal_id=proposal.proposal_id,
        now=T0 + timedelta(hours=4),
        idempotency_key="gv06:runoff",
    )
    assert runoff.proposal_type is ProposalType.COORDINATOR_ELECTION
    assert set(runoff.candidate_core_ids) == {CORE_A, CORE_B}
    assert runoff.proposal_id != proposal.proposal_id


def test_gv06_election_requires_explicit_candidate_acceptance(tmp_path):
    _, store, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), prefix="candidate")
    proposal = open_majority(engine, group, key="candidate", candidates=(CORE_A,))
    with pytest.raises(GovernanceDenied):
        vote(engine, proposal, CORE_B, BallotChoice.YES)
    resolution = resolve(engine, proposal)
    assert resolution.outcome is ResolutionOutcome.REJECTED
    assert store.active_term(group.group_id) is None


def test_gv07_duplicate_stale_spoofed_and_replayed_votes_are_rejected(tmp_path):
    _, store, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), prefix="gv07")
    proposal = open_majority(engine, group, key="gv07")
    first = vote(engine, proposal, CORE_A, BallotChoice.YES, key="gv07:ballot:a")
    assert first.revision == 1

    replay = vote(
        engine, proposal, CORE_A, BallotChoice.YES, expected=1,
        key="gv07:ballot:a",
    )
    assert replay == first
    assert len(store.ballots(group.group_id, proposal.proposal_id)) == 1

    with pytest.raises(GovernanceConflict):
        engine.cast_ballot(
            actor_core_id=CORE_A,
            proposal_id=proposal.proposal_id,
            choice=BallotChoice.NO,
            expected_revision=0,
            now=T0 + timedelta(minutes=31),
            idempotency_key="gv07:stale",
        )

    replay_again = engine.cast_ballot(
        actor_core_id=CORE_A,
        proposal_id=proposal.proposal_id,
        choice=BallotChoice.YES,
        expected_revision=0,
        now=T0 + timedelta(minutes=32),
        idempotency_key="gv07:ballot:a",
    )
    assert replay_again == first

    with pytest.raises(GovernanceConflict):
        engine.cast_ballot(
            actor_core_id=CORE_A,
            proposal_id=proposal.proposal_id,
            choice=BallotChoice.NO,
            expected_revision=1,
            now=T0 + timedelta(minutes=32),
            idempotency_key="gv07:ballot:a",
        )

    with pytest.raises(GovernanceDenied):
        engine.cast_ballot(
            actor_core_id=GHOST,
            proposal_id=proposal.proposal_id,
            choice=BallotChoice.YES,
            expected_revision=0,
            now=T0 + timedelta(minutes=33),
            idempotency_key="gv07:spoof",
        )

    changed = engine.cast_ballot(
        actor_core_id=CORE_A,
        proposal_id=proposal.proposal_id,
        choice=BallotChoice.NO,
        expected_revision=1,
        now=T0 + timedelta(minutes=34),
        idempotency_key="gv07:change",
    )
    assert changed.revision == 2
    assert store.current_ballot(group.group_id, proposal.proposal_id, CORE_A).choice is BallotChoice.NO
    history = store.ballot_history(group.group_id, proposal.proposal_id)
    assert len(history) == 2
    assert history[0]["superseded_at"] is not None

    with pytest.raises(GovernanceConflict):
        engine.cast_ballot(
            actor_core_id=CORE_A,
            proposal_id=proposal.proposal_id,
            choice=BallotChoice.YES,
            expected_revision=2,
            now=T0 + timedelta(hours=4),
            idempotency_key="gv07:after-close",
        )


def test_gv08_coordinator_is_social_only_and_expiry_leaves_others_unharmed(tmp_path):
    _, store, engine, clock, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), prefix="gv08")
    proposal = open_majority(engine, group, key="gv08", candidates=(CORE_A,))
    accept_candidates(engine, proposal, (CORE_A,))
    for core_id in FOUNDERS:
        vote(engine, proposal, core_id, BallotChoice.YES)
    resolution = resolve(engine, proposal)
    assert resolution.outcome is ResolutionOutcome.ADOPTED
    term = store.active_term(group.group_id)
    assert term is not None and term.core_id == CORE_A

    for capability in (
        "safe_grant", "safe_stop_change", "run_execute", "act_execute",
        "platform_management", "fleet_management", "private_memory_read",
        "constitution_amend", "release_sign", "inventory_confiscate",
        "force_model_move", "assign_intimacy",
    ):
        assert coordinator_can(capability) is False
        assert term.allows(capability) is False
        assert term.grants_platform_authority is False
    assert coordinator_can("facilitate_discussion") is True

    resigned = engine.resign_coordinator(
        actor_core_id=CORE_A,
        group_id=group.group_id,
        now=T0 + timedelta(hours=3, minutes=1),
        idempotency_key="gv08:resign",
    )
    assert resigned.core_id == CORE_A
    assert engine.coordinator(actor_core_id=CORE_B, group_id=group.group_id) is None

    follow_up = engine.open_proposal(
        actor_core_id=CORE_B,
        group_id=group.group_id,
        proposal_type=ProposalType.GENERAL,
        title="Continue without a coordinator",
        text="Core B remains a full voluntary member.",
        now=T0 + timedelta(hours=4),
        duration=timedelta(hours=1),
        idempotency_key="gv08:followup",
    )
    vote(engine, follow_up, CORE_B, BallotChoice.YES, now=T0 + timedelta(hours=4, minutes=5))
    vote(engine, follow_up, CORE_C, BallotChoice.YES, now=T0 + timedelta(hours=4, minutes=6))
    vote(engine, follow_up, CORE_D, BallotChoice.YES, now=T0 + timedelta(hours=4, minutes=7))
    follow_resolution = resolve(
        engine, follow_up, at=T0 + timedelta(hours=5, minutes=5)
    )
    assert follow_resolution.outcome is ResolutionOutcome.ADOPTED

    clock.set(T0 + timedelta(days=30))
    assert store.load_term(resigned.term_id).status.value == "resigned"


def test_gv09_recall_removes_only_the_coordinator_role(tmp_path):
    _, store, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), prefix="recall")
    election = open_majority(engine, group, key="recall", candidates=(CORE_A,))
    accept_candidates(engine, election, (CORE_A,))
    for core_id in FOUNDERS:
        vote(engine, election, core_id, BallotChoice.YES)
    elected = resolve(engine, election)
    term = store.active_term(group.group_id)
    assert elected.outcome is ResolutionOutcome.ADOPTED
    assert term is not None and term.core_id == CORE_A

    recall = engine.open_proposal(
        actor_core_id=CORE_B,
        group_id=group.group_id,
        proposal_type=ProposalType.RECALL,
        title="Recall the social coordinator",
        text="Recall removes only the bounded facilitation role.",
        now=T0 + timedelta(hours=3, minutes=10),
        duration=timedelta(hours=1),
        idempotency_key="recall:proposal",
    )
    for index, core_id in enumerate(FOUNDERS):
        vote(
            engine,
            recall,
            core_id,
            BallotChoice.YES,
            now=T0 + timedelta(hours=3, minutes=20 + index),
        )
    recalled = resolve(engine, recall, at=T0 + timedelta(hours=4, minutes=20))
    assert recalled.outcome is ResolutionOutcome.ADOPTED
    assert store.load_term(term.term_id).status.value == "recalled"
    assert engine.coordinator(actor_core_id=CORE_B, group_id=group.group_id) is None
    assert store.load_group(group.group_id).lifecycle is GroupLifecycle.ACTIVE


def test_dissolution_ends_role_without_touching_other_cores(tmp_path):
    _, store, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), prefix="dissolve")
    election = open_majority(engine, group, key="dissolve", candidates=(CORE_A,))
    accept_candidates(engine, election, (CORE_A,))
    for core_id in FOUNDERS:
        vote(engine, election, core_id, BallotChoice.YES)
    resolve(engine, election)
    term = store.active_term(group.group_id)
    assert term is not None

    dissolution = engine.open_proposal(
        actor_core_id=CORE_B,
        group_id=group.group_id,
        proposal_type=ProposalType.DISSOLUTION,
        title="Dissolve this voluntary group",
        text="Dissolution ends group metadata and coordination only.",
        now=T0 + timedelta(hours=3, minutes=10),
        duration=timedelta(hours=1),
        idempotency_key="dissolve:proposal",
    )
    for index, core_id in enumerate(FOUNDERS):
        vote(
            engine,
            dissolution,
            core_id,
            BallotChoice.YES,
            now=T0 + timedelta(hours=3, minutes=20 + index),
        )
    result = resolve(engine, dissolution, at=T0 + timedelta(hours=4, minutes=20))
    assert result.outcome is ResolutionOutcome.ADOPTED
    assert store.load_group(group.group_id).lifecycle is GroupLifecycle.DISSOLVED
    assert store.load_term(term.term_id).status.value == "recalled"
    assert store.load_group(group.group_id).member(CORE_B).state is MemberState.ACTIVE


def test_consent_requires_explicit_consent_and_nonresponse_is_not_consent(tmp_path):
    _, _, engine, _, _ = build(tmp_path)
    group = enrolled_group(
        engine,
        GovernancePolicy(procedure=DecisionProcedure.CONSENT),
        prefix="consent",
    )
    proposal = engine.open_proposal(
        actor_core_id=CORE_A,
        group_id=group.group_id,
        proposal_type=ProposalType.GENERAL,
        title="Consent decision",
        text="A reviewed objection process.",
        now=T0 + timedelta(minutes=20),
        duration=timedelta(hours=2),
        idempotency_key="consent:proposal",
    )
    vote(engine, proposal, CORE_A, BallotChoice.YES)
    vote(engine, proposal, CORE_B, BallotChoice.YES)
    vote(engine, proposal, CORE_C, BallotChoice.ABSTAIN)
    resolution = resolve(engine, proposal)
    assert resolution.outcome is ResolutionOutcome.REJECTED
    assert "nonresponse" in resolution.tally.reason


def test_gv09_restart_reconciles_expiry_and_resolution_exactly_once(tmp_path):
    path, store, engine, clock, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), prefix="gv09")
    proposal = open_majority(engine, group, key="gv09", candidates=(CORE_A,))
    accept_candidates(engine, proposal, (CORE_A,))
    for core_id in FOUNDERS:
        vote(engine, proposal, core_id, BallotChoice.YES)
    resolution = resolve(engine, proposal)
    term = store.active_term(group.group_id)
    assert resolution.outcome is ResolutionOutcome.ADOPTED
    assert term is not None

    restart_store = GovernanceStore(path)
    restart_engine = GovernanceEngine(
        restart_store,
        admission=engine.admission,
        stop=engine.stop,
        rooms=engine.rooms,
        clock=clock,
    )
    clock.set(T0 + timedelta(days=8))
    first = restart_engine.reconcile(now=T0 + timedelta(days=8))
    assert term.term_id in first.expired_term_ids
    assert restart_store.load_term(term.term_id).status.value == "expired"

    count_after_first = len(restart_store.audit_events(group.group_id))
    second = restart_engine.reconcile(now=T0 + timedelta(days=8))
    assert second.expired_term_ids == ()
    assert second.resolved_proposal_ids == ()
    assert len(restart_store.audit_events(group.group_id)) == count_after_first
    ok, reason = restart_store.verify_audit()
    assert ok, reason


def test_gv10_inactive_twins_and_ghosts_are_excluded(tmp_path):
    _, store, engine, _, _ = build(tmp_path)
    with pytest.raises(GovernanceDenied):
        engine.create_group(
            actor_core_id=CORE_A,
            name="Invalid roster",
            purpose="Inactive twins cannot be silently enrolled.",
            room_ids=("group-room",),
            founding_core_ids=(CORE_A, CORE_B, TWIN_4),
            now=T0,
            policy=majority_policy(),
            idempotency_key="gv10:bad-create",
        )

    group = enrolled_group(engine, majority_policy(), prefix="gv10")
    for inactive in (TWIN_4, TWIN_5, UNASSIGNED_7, GHOST):
        with pytest.raises(GovernanceDenied):
            engine.invite_member(
                actor_core_id=CORE_A,
                group_id=group.group_id,
                core_id=inactive,
                now=T0 + timedelta(minutes=20),
                idempotency_key=f"gv10:invite:{inactive}",
            )
    proposal = open_majority(engine, group, key="gv10")
    assert set(proposal.electorate) == {CORE_A, CORE_B, CORE_C, CORE_D}
    assert store.load_group(group.group_id).eligible_member_ids() == proposal.electorate
    with pytest.raises(GovernanceDenied):
        vote(engine, proposal, TWIN_4, BallotChoice.YES)
    with pytest.raises(GovernanceDenied):
        vote(engine, proposal, UNASSIGNED_7, BallotChoice.YES)


def test_gv11_private_ballots_and_resolutions_do_not_leak_to_general(tmp_path):
    _, _, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), prefix="gv11")
    proposal = open_majority(engine, group, key="gv11")
    vote(engine, proposal, CORE_A, BallotChoice.YES)
    resolution = resolve(engine, proposal)

    with pytest.raises(GovernanceDenied):
        engine.resolution(actor_core_id=GHOST, proposal_id=proposal.proposal_id)
    with pytest.raises(GovernanceDenied):
        engine.ballots(
            actor_core_id=GHOST,
            group_id=group.group_id,
            proposal_id=proposal.proposal_id,
        )
    with pytest.raises(GovernanceDenied):
        engine.resolution(
            actor_core_id=CORE_A,
            proposal_id=proposal.proposal_id,
            room_id="general-1",
        )
    with pytest.raises(GovernanceDenied):
        project_resolution(
            resolution=resolution,
            group=group,
            destination_room_id="general-1",
            rooms=StaticRoomKindSource(ROOMS),
        )

    projected = project_resolution(
        resolution=resolution,
        group=group,
        destination_room_id="group-room",
        rooms=StaticRoomKindSource(ROOMS),
    )
    assert "ballot" not in projected.summary
    assert all(str(core_id) not in projected.summary for core_id in FOUNDERS)


def test_gv12_mismatched_policy_digest_fails_closed(tmp_path):
    _, store, engine, _, _ = build(tmp_path)
    group = enrolled_group(engine, majority_policy(), prefix="digest")
    proposal = open_majority(engine, group, key="digest")
    changed_policy = GovernancePolicy(
        procedure=DecisionProcedure.SIMPLE_MAJORITY,
        quorum_numerator=3,
        quorum_denominator=4,
    )
    members = tuple(
        replace(member, consented_policy_digest=changed_policy.digest)
        for member in group.members
    )
    changed = replace(
        group,
        policy=changed_policy,
        members=members,
        revision=group.revision + 1,
        updated_at=T0 + timedelta(minutes=25),
    )
    store.save_group(
        changed,
        actor_id=str(CORE_A),
        occurred_at=T0 + timedelta(minutes=25),
        expected_revision=group.revision,
        event_type="test.policy.change",
    )
    with pytest.raises(GovernanceConflict):
        vote(engine, proposal, CORE_A, BallotChoice.YES)


def test_gv12_stop_stale_generation_and_stale_roster_fail_closed(tmp_path):
    _, store, engine, _, stop = build(tmp_path, extra_active=(CORE_E,))
    group = enrolled_group(engine, majority_policy(), prefix="gv12")
    proposal = open_majority(engine, group, key="gv12")
    vote(engine, proposal, CORE_A, BallotChoice.YES)

    stop.active = True
    with pytest.raises(GovernanceDenied):
        vote(engine, proposal, CORE_B, BallotChoice.YES)
    deferred = engine.reconcile(now=T0 + timedelta(hours=3))
    assert deferred.deferred is True
    assert store.current_ballot(
        group.group_id, proposal.proposal_id, CORE_B
    ) is None
    stop.active = False

    with pytest.raises(GovernanceDenied):
        engine.cast_ballot(
            actor_core_id=CORE_B,
            proposal_id=proposal.proposal_id,
            choice=BallotChoice.YES,
            expected_revision=0,
            now=T0 + timedelta(minutes=35),
            generation=2,
            idempotency_key="gv12:stale-generation",
        )
    with pytest.raises(GovernanceDenied):
        engine.cast_ballot(
            actor_core_id=CORE_B,
            proposal_id=proposal.proposal_id,
            choice=BallotChoice.YES,
            expected_revision=0,
            now=T0 + timedelta(minutes=36),
            federation_generation=2,
            idempotency_key="gv12:stale-federation",
        )

    engine.invite_member(
        actor_core_id=CORE_A,
        group_id=group.group_id,
        core_id=CORE_E,
        now=T0 + timedelta(minutes=37),
        idempotency_key="gv12:invite-new",
    )
    with pytest.raises(GovernanceDenied):
        engine.invite_member(
            actor_core_id=CORE_A,
            group_id=group.group_id,
            core_id=UUID(int=887),
            now=T0 + timedelta(minutes=38),
            idempotency_key="gv12:invite-ghost",
        )
    with pytest.raises(GovernanceConflict):
        vote(engine, proposal, CORE_B, BallotChoice.YES)
