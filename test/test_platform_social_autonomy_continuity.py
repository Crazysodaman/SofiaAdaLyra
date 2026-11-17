"""Restart and multi-day continuity with controlled clocks."""
from datetime import datetime, timedelta, timezone

from sofia.platform.social.autonomy.contracts import (
    AutonomyLimits,
    SocialAction,
    SocialEvent,
    SocialEventKind,
)
from sofia.platform.social.autonomy.engine import AutonomousSocialEngine
from sofia.platform.social.autonomy.evidence import EvidenceCategory
from sofia.platform.social.autonomy.models import PeerFacet
from sofia.platform.social.autonomy.store import SocialAutonomyStore
from test.social_autonomy_support import (
    AllowAuthorization,
    FakeStop,
    MutableClock,
    RecordingScheduler,
    RecordingTransport,
    StaticPlanner,
    identity,
    message,
    proposal,
    state_path,
)


NOW = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)


def _engine(store, core, clock, transport=None, scheduler=None, limits=None):
    return AutonomousSocialEngine(
        core,
        store,
        clock=clock,
        stop=FakeStop(),
        authorization=AllowAuthorization(),
        transport=transport,
        scheduler=scheduler,
        limits=limits or AutonomyLimits(contact_cooldown=timedelta(0)),
    )


def _event(core, peer, index, *, chain="restart-chain", now=None, event_id=None):
    moment = now or NOW
    return SocialEvent(
        event_id=event_id or f"event-{index}",
        core_id=core.core_id,
        kind=SocialEventKind.MESSAGE_RECEIVED,
        occurred_at=moment,
        room_id="general-1",
        chain_id=chain,
        message=message(
            peer,
            message_id=f"msg-{index}",
            body="A durable conversational point.",
            now=moment,
            sequence=index,
        ),
    )


def test_relationship_evidence_topics_and_budgets_survive_restart(tmp_path):
    path = state_path(tmp_path)
    core = identity("Ada")
    peer = identity("Lyda")
    clock = MutableClock(NOW)
    store = SocialAutonomyStore(path)
    transport = RecordingTransport()
    engine = _engine(store, core, clock, transport=transport)

    engine.set_facet(
        peer.core_id,
        PeerFacet.AFFINITY,
        level=0.7,
        reason="A durable genuine interest overlap.",
        evidence_refs=("interaction-1",),
    )
    evidence = engine.record_evidence(
        category=EvidenceCategory.VERIFIED_OUTCOME,
        claim="The joint test passed.",
        evidence_ref="receipt-restart",
        peer_core_id=peer.core_id,
    )
    engine.set_interest("robotics", 0.9)
    engine.set_goal("rail-review", "Review the rail safety design.", 0.8)
    engine.record_opinion(
        topic="scheduling",
        statement="Failure isolation matters more than nominal throughput.",
        stance=0.6,
        confidence=0.7,
        evidence_refs=("interaction-1",),
        peer_core_id=peer.core_id,
    )
    engine.set_topic(
        "scheduling",
        summary="Disagreement about failure handling remains open.",
        peer_core_id=peer.core_id,
        room_id="dm-restart",
        next_revisit_at=NOW + timedelta(days=1),
    )
    planner = StaticPlanner(proposal(SocialAction.REPLY, body="A grounded reply."))
    first = engine.receive(_event(core, peer, 1), planner=planner)
    assert first.action is SocialAction.REPLY

    restarted_store = SocialAutonomyStore(path)
    restarted = _engine(restarted_store, core, clock)

    relationship = restarted.relationship(peer.core_id)
    assert relationship.effective(PeerFacet.AFFINITY) == 0.7
    assert restarted.active_evidence(
        peer_core_id=peer.core_id, category=EvidenceCategory.VERIFIED_OUTCOME
    ) == (evidence,)
    assert restarted_store.interests(core.core_id)[0].name == "robotics"
    assert restarted_store.goals(core.core_id)[0].goal_id == "rail-review"
    assert restarted.opinions(peer_core_id=peer.core_id)[0].revision == 1
    assert restarted_store.topic(core.core_id, "scheduling") is not None
    assert restarted_store.turn_count(core.core_id, "restart-chain") == 1
    assert restarted_store.budget_usage(core.core_id, "2026-03-01")[0] == 1

    duplicate = restarted.receive(
        _event(core, peer, 1, event_id="event-duplicate"), planner=planner
    )
    assert duplicate.action is SocialAction.SILENCE
    assert duplicate.duplicate_suppressed


def test_multi_day_clock_advance_resets_budgets_and_expires_cooldowns(tmp_path):
    path = state_path(tmp_path)
    core = identity("Ada")
    peer = identity("Lyda")
    clock = MutableClock(NOW)
    transport = RecordingTransport()
    scheduler = RecordingScheduler()
    engine = _engine(
        SocialAutonomyStore(path),
        core,
        clock,
        transport=transport,
        scheduler=scheduler,
        limits=AutonomyLimits(
            max_chain_turns=20,
            contact_cooldown=timedelta(hours=2),
            max_contacts_per_day=2,
            max_inference_units_per_day=20,
        ),
    )
    planner = StaticPlanner(proposal(SocialAction.REPLY, body="A grounded reply."))
    assert engine.receive(_event(core, peer, 1), planner=planner).action is (
        SocialAction.REPLY
    )
    clock.advance(timedelta(hours=2, minutes=1))
    assert engine.receive(
        _event(core, peer, 2, now=clock.now()), planner=planner
    ).action is SocialAction.REPLY
    clock.advance(timedelta(hours=2, minutes=1))
    exhausted = engine.receive(
        _event(core, peer, 3, now=clock.now()), planner=planner
    )
    assert exhausted.action is SocialAction.DEFER
    assert "contact budget" in exhausted.reason

    clock.advance(timedelta(days=1))
    next_day = engine.receive(
        _event(core, peer, 4, chain="next-day", now=clock.now()), planner=planner
    )
    assert next_day.action is SocialAction.REPLY
    assert len(transport.decisions) == 3


def test_unresolved_topic_continues_after_restart_and_clock_advance(tmp_path):
    path = state_path(tmp_path)
    core = identity("Ada")
    peer = identity("Lyda")
    clock = MutableClock(NOW)
    first_engine = _engine(SocialAutonomyStore(path), core, clock)
    first_engine.set_topic(
        "design-dispute",
        summary="We disagreed about failure-mode handling.",
        peer_core_id=peer.core_id,
        room_id="dm-continuity",
        next_revisit_at=NOW + timedelta(days=1),
    )

    clock.advance(timedelta(days=2))
    restarted = _engine(SocialAutonomyStore(path), core, clock)
    planner = StaticPlanner(
        proposal(
            SocialAction.CONTINUE_TOPIC,
            body="I now have a verified benchmark that may resolve our dispute.",
            topic="design-dispute",
            target_core_id=peer.core_id,
        )
    )
    decision = restarted.continue_topic("design-dispute", planner=planner)

    assert decision.action is SocialAction.CONTINUE_TOPIC
    topic = restarted.store.topic(core.core_id, "design-dispute")
    assert topic.revision == 2
    assert topic.next_revisit_at == clock.now() + timedelta(days=1)
    assert topic.unresolved
    assert len(planner.calls) == 1
