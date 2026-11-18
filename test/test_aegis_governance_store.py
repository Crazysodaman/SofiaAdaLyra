from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from sofia.platform.social.governance import (
    BallotChoice,
    DecisionProcedure,
    GovernanceConflict,
    GovernanceEngine,
    GovernancePolicy,
    GovernanceStore,
    MemberState,
    ProposalType,
    StaticAdmission,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


T0 = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
CORE_A = UUID(int=201)
CORE_B = UUID(int=202)
CORE_C = UUID(int=203)
CORE_D = UUID(int=204)
FOUNDERS = (CORE_A, CORE_B, CORE_C, CORE_D)
REQUIRED_TABLES = {
    "governance_group",
    "governance_member",
    "governance_proposal",
    "governance_nomination",
    "governance_ballot",
    "governance_ballot_history",
    "governance_resolution",
    "governance_coordinator_term",
    "governance_audit_event",
}


class Clock:
    def __init__(self) -> None:
        self.value = T0

    def now(self) -> datetime:
        return self.value

    def set(self, value: datetime) -> None:
        self.value = value


class Stop:
    def is_operator_stopped(self) -> bool:
        return False


def policy() -> GovernancePolicy:
    return GovernancePolicy(procedure=DecisionProcedure.SIMPLE_MAJORITY)


def build(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = GovernanceStore(path)
    admission = StaticAdmission(
        FOUNDERS,
        generations={core: 1 for core in FOUNDERS},
        federation_generations={core: 1 for core in FOUNDERS},
    )
    engine = GovernanceEngine(
        store, admission=admission, stop=Stop(), clock=Clock()
    )
    return path, store, engine


def active_group(engine, prefix="store"):
    group = engine.create_group(
        actor_core_id=CORE_A,
        name="Store Circle",
        purpose="Persistence and restart evidence.",
        room_ids=("group-room",),
        founding_core_ids=FOUNDERS,
        now=T0,
        policy=policy(),
        idempotency_key=f"{prefix}:create",
    )
    group = engine.open_invitations(
        actor_core_id=CORE_A,
        group_id=group.group_id,
        now=T0,
        idempotency_key=f"{prefix}:open",
    )
    for index, core_id in enumerate(FOUNDERS):
        group = engine.respond_to_invitation(
            actor_core_id=core_id,
            group_id=group.group_id,
            accept=True,
            now=T0 + timedelta(minutes=index + 1),
            idempotency_key=f"{prefix}:accept:{core_id}",
        )
    group = engine.activate_group(
        actor_core_id=CORE_A,
        group_id=group.group_id,
        now=T0 + timedelta(minutes=10),
        idempotency_key=f"{prefix}:active",
    )
    return group


def majority(engine, group, prefix="store"):
    return engine.open_proposal(
        actor_core_id=CORE_A,
        group_id=group.group_id,
        proposal_type=ProposalType.GENERAL,
        title="Persisted decision",
        text="One canonical row set.",
        now=T0 + timedelta(minutes=20),
        duration=timedelta(hours=2),
        idempotency_key=f"{prefix}:proposal",
    )


def cast(engine, proposal, core_id, choice, *, expected=0, key=None, now=None):
    return engine.cast_ballot(
        actor_core_id=core_id,
        proposal_id=proposal.proposal_id,
        choice=choice,
        expected_revision=expected,
        now=now or T0 + timedelta(minutes=30),
        idempotency_key=key or f"store:{proposal.proposal_id}:{core_id}:{expected}",
    )


def test_store_uses_only_additive_tables_in_one_canonical_file(tmp_path):
    path, store, _ = build(tmp_path)
    with store.reader() as db:
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {row["name"] for row in rows}
    assert REQUIRED_TABLES.issubset(names)
    assert "safe_audit_event" in names
    database_files = sorted(tmp_path.glob("*.db"))
    assert database_files == [path]
    assert path.name == "sofia.db"


def test_group_roundtrip_and_group_scoped_queries(tmp_path):
    _, store, engine = build(tmp_path)
    group = active_group(engine, "scope")
    other = active_group(engine, "other")
    loaded = store.load_group(group.group_id)
    assert loaded is not None
    assert loaded.policy_digest == group.policy_digest
    assert loaded.roster_epoch == group.roster_epoch
    assert all(member.state is MemberState.ACTIVE for member in loaded.members)
    assert set(loaded.eligible_member_ids()) == set(FOUNDERS)
    assert loaded.is_leaderless()

    proposal = majority(engine, group, "scope")
    cast(engine, proposal, CORE_A, BallotChoice.YES, key="scope:vote:a")
    assert store.load_proposal(other.group_id, proposal.proposal_id) is None
    assert store.ballots(other.group_id, proposal.proposal_id) == ()
    assert store.current_ballot(other.group_id, proposal.proposal_id, CORE_A) is None
    assert len(store.ballots(group.group_id, proposal.proposal_id)) == 1


def test_ballot_revision_history_and_idempotency(tmp_path):
    _, store, engine = build(tmp_path)
    group = active_group(engine, "history")
    proposal = majority(engine, group, "history")
    first = cast(engine, proposal, CORE_A, BallotChoice.YES, key="history:vote:a")
    assert first.revision == 1
    second = cast(
        engine,
        proposal,
        CORE_A,
        BallotChoice.NO,
        expected=1,
        key="history:vote:a2",
    )
    assert second.revision == 2
    replay = cast(
        engine,
        proposal,
        CORE_A,
        BallotChoice.NO,
        expected=2,
        key="history:vote:a2",
    )
    assert replay == second
    history = store.ballot_history(group.group_id, proposal.proposal_id)
    assert [row["revision"] for row in history] == [1, 2]
    assert history[0]["superseded_at"] is not None
    assert history[0]["superseded_by"] == f"{second.ballot_id}:2"

    with pytest.raises(GovernanceConflict):
        cast(engine, proposal, CORE_A, BallotChoice.YES, expected=0, key="history:stale")


def test_audit_is_append_only_named_and_verifiable(tmp_path):
    _, store, engine = build(tmp_path)
    group = active_group(engine, "audit")
    proposal = majority(engine, group, "audit")
    cast(engine, proposal, CORE_A, BallotChoice.YES, key="audit:vote:a")

    ok, reason = store.verify_audit()
    assert ok, reason
    events = store.audit_events(group.group_id)
    ballot_events = [
        event for event in events
        if event["event_type"] == "governance.ballot.cast"
    ]
    assert len(ballot_events) == 1
    assert str(CORE_A) in ballot_events[0]["payload_json"]
    assert "choice" in ballot_events[0]["payload_json"]

    store.append_audit(
        actor_id="owner:test",
        event_type="governance.review",
        occurred_at=T0 + timedelta(minutes=40),
        payload={"group_id": str(group.group_id), "note": "reviewed"},
        group_id=group.group_id,
        idempotency_key="audit:review",
    )
    ok, reason = store.verify_audit()
    assert ok, reason
    assert len(store.audit_events(group.group_id)) == len(events) + 1


def test_restart_idempotency_and_resolution_exactly_once(tmp_path):
    path, store, engine = build(tmp_path)
    group = active_group(engine, "restart")
    count_before = len(store.audit_events(group.group_id))

    restart_store = GovernanceStore(path)
    restart_engine = GovernanceEngine(
        restart_store,
        admission=engine.admission,
        stop=engine.stop,
        clock=engine._clock,
    )
    again = restart_engine.create_group(
        actor_core_id=CORE_A,
        name="Store Circle",
        purpose="Persistence and restart evidence.",
        room_ids=("group-room",),
        founding_core_ids=FOUNDERS,
        now=T0,
        policy=policy(),
        idempotency_key="restart:create",
    )
    assert again.group_id == group.group_id
    assert len(restart_store.audit_events(group.group_id)) == count_before

    proposal = majority(restart_engine, group, "restart2")
    for core_id in FOUNDERS:
        cast(restart_engine, proposal, core_id, BallotChoice.YES)
    resolution = restart_engine.close_and_resolve(
        actor_core_id=CORE_A,
        proposal_id=proposal.proposal_id,
        now=T0 + timedelta(hours=3),
        idempotency_key="restart:resolve",
    )
    repeated = restart_engine.close_and_resolve(
        actor_core_id=CORE_B,
        proposal_id=proposal.proposal_id,
        now=T0 + timedelta(hours=3),
        idempotency_key="restart:resolve-again",
    )
    assert repeated.resolution_id == resolution.resolution_id
    assert restart_store.load_resolution(
        group.group_id, proposal.proposal_id
    ).resolution_id == resolution.resolution_id
    ok, reason = restart_store.verify_audit()
    assert ok, reason


def test_duplicate_ballot_idempotency_key_is_not_silently_accepted(tmp_path):
    _, store, engine = build(tmp_path)
    group = active_group(engine, "dup")
    proposal = majority(engine, group, "dup")
    cast(engine, proposal, CORE_A, BallotChoice.YES, key="dup:key")
    with pytest.raises(GovernanceConflict):
        cast(engine, proposal, CORE_B, BallotChoice.YES, key="dup:key")
    assert len(store.ballots(group.group_id, proposal.proposal_id)) == 1
