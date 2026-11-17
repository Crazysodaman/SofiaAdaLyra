"""Bounded autonomous social decisions: silence, relevance, caps and cooldowns."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sofia.platform.social.autonomy.contracts import (
    AutonomyLimits,
    SocialAction,
    SocialEvent,
    SocialEventKind,
)
from sofia.platform.social.autonomy.engine import AutonomousSocialEngine
from sofia.platform.social.autonomy.store import SocialAutonomyStore
from test.social_autonomy_support import (
    AllowAuthorization,
    FakeStop,
    MutableClock,
    RecordingScheduler,
    RecordingTransport,
    SequencePlanner,
    StaticPlanner,
    identity,
    message,
    proposal,
    state_path,
)


NOW = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)


def _runtime(tmp_path, *, limits=None):
    store = SocialAutonomyStore(state_path(tmp_path))
    core = identity("Ada")
    peer = identity("Lyda")
    clock = MutableClock(NOW)
    transport = RecordingTransport()
    scheduler = RecordingScheduler()
    authorization = AllowAuthorization()
    engine = AutonomousSocialEngine(
        core,
        store,
        clock=clock,
        stop=FakeStop(),
        authorization=authorization,
        transport=transport,
        scheduler=scheduler,
        limits=limits or AutonomyLimits(contact_cooldown=timedelta(0)),
    )
    return engine, core, peer, clock, transport, scheduler, authorization, store


def _event(core, peer, index, *, chain="chain-1", body="A relevant question.", event_id=None):
    msg = message(
        peer,
        message_id=f"msg-{index}",
        body=body,
        now=NOW,
        sequence=index,
    )
    return SocialEvent(
        event_id=event_id or f"event-{index}",
        core_id=core.core_id,
        kind=SocialEventKind.MESSAGE_RECEIVED,
        occurred_at=NOW,
        room_id=msg.room_id,
        chain_id=chain,
        message=msg,
    )


def test_no_planner_and_unmeaningful_proposals_choose_silence(tmp_path):
    engine, core, peer, *_ = _runtime(tmp_path)
    no_planner = engine.receive(_event(core, peer, 1), planner=None)
    assert no_planner.action is SocialAction.SILENCE
    assert "silence" in no_planner.reason

    unmeaningful = engine.receive(
        _event(core, peer, 2),
        planner=StaticPlanner(proposal(SocialAction.REPLY, meaningful=False)),
    )
    assert unmeaningful.action is SocialAction.SILENCE

    low_relevance = engine.receive(
        _event(core, peer, 3),
        planner=StaticPlanner(proposal(SocialAction.REPLY, relevance=0.1)),
    )
    assert low_relevance.action is SocialAction.SILENCE
    assert "relevance" in low_relevance.reason


def test_duplicate_messages_are_suppressed_without_extra_inference(tmp_path):
    engine, core, peer, *_ , transport, scheduler, authorization, store = _runtime(
        tmp_path
    )
    planner = StaticPlanner(proposal(SocialAction.REPLY, body="Useful reply."))
    first = engine.receive(_event(core, peer, 1), planner=planner)
    duplicate = engine.receive(
        _event(core, peer, 1, event_id="event-duplicate"), planner=planner
    )

    assert first.action is SocialAction.REPLY
    assert first.permitted and first.delivery_ref == "delivery:1"
    assert duplicate.action is SocialAction.SILENCE
    assert duplicate.duplicate_suppressed
    assert len(planner.calls) == 1
    assert len(transport.decisions) == 1
    assert len(authorization.calls) == 1
    assert len(scheduler.wakes) == 0


def test_turn_chain_cap_stops_recursive_ping_pong(tmp_path):
    engine, core, peer, *_ = _runtime(
        tmp_path,
        limits=AutonomyLimits(
            max_chain_turns=2,
            contact_cooldown=timedelta(0),
            max_contacts_per_day=10,
            max_inference_units_per_day=10,
        ),
    )
    planner = StaticPlanner(proposal(SocialAction.REPLY, body="Grounded reply."))
    decisions = [
        engine.receive(_event(core, peer, index), planner=planner)
        for index in (1, 2, 3)
    ]

    assert [item.action for item in decisions] == [
        SocialAction.REPLY,
        SocialAction.REPLY,
        SocialAction.SILENCE,
    ]
    assert "chain cap" in decisions[-1].reason
    assert len(planner.calls) == 2


def test_contact_cooldown_defers_and_wakes_the_scheduler(tmp_path):
    engine, core, peer, clock, transport, scheduler, *_ = _runtime(
        tmp_path,
        limits=AutonomyLimits(
            max_chain_turns=10,
            contact_cooldown=timedelta(hours=1),
            max_contacts_per_day=10,
            max_inference_units_per_day=10,
        ),
    )
    planner = StaticPlanner(proposal(SocialAction.REPLY, body="Grounded reply."))
    first = engine.receive(_event(core, peer, 1), planner=planner)
    deferred = engine.receive(_event(core, peer, 2), planner=planner)

    assert first.action is SocialAction.REPLY
    assert deferred.action is SocialAction.DEFER
    assert deferred.deferred_until == NOW + timedelta(hours=1)
    assert len(planner.calls) == 1
    assert len(transport.decisions) == 1
    assert scheduler.wakes[0]["reason"] == "contact_cooldown_expired"
    assert scheduler.wakes[0]["due_at"] == NOW + timedelta(hours=1)

    clock.advance(timedelta(hours=1, seconds=1))
    resumed = engine.receive(
        SocialEvent(
            event_id="event-3",
            core_id=core.core_id,
            kind=SocialEventKind.MESSAGE_RECEIVED,
            occurred_at=clock.now(),
            room_id="general-1",
            chain_id="chain-2",
            message=message(
                peer,
                message_id="msg-3",
                now=clock.now(),
                sequence=3,
            ),
        ),
        planner=planner,
    )
    assert resumed.action is SocialAction.REPLY


def test_daily_contact_and_inference_budgets_are_bounded(tmp_path):
    engine, core, peer, clock, transport, scheduler, *_ = _runtime(
        tmp_path,
        limits=AutonomyLimits(
            max_chain_turns=10,
            contact_cooldown=timedelta(0),
            max_contacts_per_day=1,
            max_inference_units_per_day=10,
        ),
    )
    planner = StaticPlanner(proposal(SocialAction.REPLY, body="Grounded reply."))
    first = engine.receive(_event(core, peer, 1), planner=planner)
    deferred = engine.receive(_event(core, peer, 2), planner=planner)

    assert first.action is SocialAction.REPLY
    assert deferred.action is SocialAction.DEFER
    assert "contact budget" in deferred.reason
    assert len(planner.calls) == 1
    assert len(transport.decisions) == 1
    assert scheduler.wakes[0]["reason"] == "daily_contact_budget_exhausted"

    clock.advance(timedelta(days=1))
    next_day = engine.receive(
        SocialEvent(
            event_id="event-3",
            core_id=core.core_id,
            kind=SocialEventKind.MESSAGE_RECEIVED,
            occurred_at=clock.now(),
            room_id="general-1",
            chain_id="chain-2",
            message=message(
                peer,
                message_id="msg-3",
                now=clock.now(),
                sequence=3,
            ),
        ),
        planner=planner,
    )
    assert next_day.action is SocialAction.REPLY


def test_inference_budget_prevents_polling_or_extra_planning(tmp_path):
    engine, core, peer, *_ , transport, scheduler, authorization, store = _runtime(
        tmp_path,
        limits=AutonomyLimits(
            max_chain_turns=10,
            contact_cooldown=timedelta(0),
            max_contacts_per_day=10,
            max_inference_units_per_day=1,
        ),
    )
    planner = StaticPlanner(proposal(SocialAction.REPLY, body="Grounded reply."))
    first = engine.receive(_event(core, peer, 1), planner=planner)
    deferred = engine.receive(_event(core, peer, 2), planner=planner)

    assert first.action is SocialAction.REPLY
    assert deferred.action is SocialAction.DEFER
    assert "inference budget" in deferred.reason
    assert len(planner.calls) == 1
    assert scheduler.wakes[0]["reason"] == "daily_inference_budget_exhausted"


def test_join_invite_and_private_discussion_are_explicit_actions(tmp_path):
    engine, core, peer, *_ , transport, scheduler, authorization, store = _runtime(
        tmp_path
    )
    join = engine.consider_room(
        "general-1",
        (message(peer, message_id="msg-join", body="A relevant design debate."),),
        planner=StaticPlanner(
            proposal(
                SocialAction.JOIN,
                body=None,
                audience="participants",
                target_core_id=peer.core_id,
            )
        ),
    )
    assert join.action is SocialAction.JOIN
    assert transport.actions[-1] is SocialAction.JOIN

    invite = engine.receive(
        _event(core, peer, 2),
        planner=StaticPlanner(
            proposal(
                SocialAction.INVITE,
                body="Would you join the rail-safety review?",
                target_core_id=peer.core_id,
                audience="private",
            )
        ),
    )
    assert invite.action is SocialAction.INVITE
    assert transport.actions[-1] is SocialAction.INVITE

    private = engine.receive(
        _event(core, peer, 3, body="Can we discuss this privately?"),
        planner=StaticPlanner(
            proposal(
                SocialAction.START_PRIVATE,
                body="Yes, let us keep this between us.",
                target_core_id=peer.core_id,
                audience="private",
                room_id="dm-1",
            )
        ),
    )
    assert private.action is SocialAction.START_PRIVATE
    assert private.room_id == "dm-1"
    assert transport.actions[-1] is SocialAction.START_PRIVATE
    assert len(scheduler.wakes) == 0


def test_core_authored_body_is_required_and_never_scripted(tmp_path):
    engine, core, peer, *_ , transport, scheduler, authorization, store = _runtime(
        tmp_path
    )
    decision = engine.receive(
        _event(core, peer, 1),
        planner=StaticPlanner(
            proposal(SocialAction.SEND_MESSAGE, body=None, target_core_id=peer.core_id)
        ),
    )
    assert decision.action is SocialAction.SILENCE
    assert "script" in decision.reason
    assert transport.decisions == []


def test_unresolved_topic_is_continued_only_when_due(tmp_path):
    engine, core, peer, clock, transport, scheduler, authorization, store = _runtime(
        tmp_path
    )
    engine.set_topic(
        "scheduling",
        summary="We disagreed about scheduler failure handling.",
        peer_core_id=peer.core_id,
        room_id="dm-2",
        next_revisit_at=NOW - timedelta(minutes=5),
    )
    planner = StaticPlanner(
        proposal(
            SocialAction.CONTINUE_TOPIC,
            body="I found a verified failure mode worth revisiting.",
            topic="scheduling",
            target_core_id=peer.core_id,
        )
    )
    continued = engine.continue_topic("scheduling", planner=planner)

    assert continued.action is SocialAction.CONTINUE_TOPIC
    topic = store.topic(core.core_id, "scheduling")
    assert topic.revision == 2
    assert topic.next_revisit_at > NOW
    assert topic.status.value == "open"

    engine.set_topic(
        "later",
        summary="A future question.",
        peer_core_id=peer.core_id,
        room_id="dm-2",
        next_revisit_at=NOW + timedelta(hours=2),
    )
    future_planner = StaticPlanner(
        proposal(
            SocialAction.CONTINUE_TOPIC,
            body="This should not be sent yet.",
            topic="later",
            target_core_id=peer.core_id,
        )
    )
    deferred = engine.continue_topic("later", planner=future_planner)
    assert deferred.action is SocialAction.DEFER
    assert future_planner.calls == []
    assert scheduler.wakes[-1]["reason"] == "topic_revisit_due"


def test_decline_pause_leave_and_block_are_independent_choices(tmp_path):
    engine, core, peer, clock, transport, scheduler, authorization, store = _runtime(
        tmp_path
    )
    declined = engine.receive(
        _event(core, peer, 1),
        planner=StaticPlanner(
            proposal(
                SocialAction.DECLINE,
                body="I do not want to debate that topic.",
                target_core_id=peer.core_id,
            )
        ),
    )
    assert declined.action is SocialAction.DECLINE
    assert transport.actions[-1] is SocialAction.DECLINE

    paused = engine.pause_peer(
        peer.core_id, until_at=NOW + timedelta(days=2), reason="Focus elsewhere."
    )
    assert paused.action is SocialAction.PAUSE
    after_pause = engine.receive(
        _event(core, peer, 2),
        planner=StaticPlanner(proposal(SocialAction.REPLY)),
    )
    assert after_pause.action is SocialAction.DEFER

    left = engine.leave_room("general-1", reason="Conversation is not relevant.")
    assert left.action is SocialAction.LEAVE

    blocked_engine, blocked_core, blocked_peer, *_ = _runtime(
        tmp_path / "blocked"
    )
    blocked = blocked_engine.block_peer(
        blocked_peer.core_id, reason="Repeated boundary violation."
    )
    assert blocked.action is SocialAction.BLOCK
    ignored = blocked_engine.receive(
        _event(blocked_core, blocked_peer, 1), planner=None
    )
    assert ignored.action is SocialAction.SILENCE
    assert "boundary" in ignored.reason


def test_initiation_is_voluntary_and_event_driven(tmp_path):
    engine, core, peer, clock, transport, scheduler, authorization, store = _runtime(
        tmp_path
    )
    planner = StaticPlanner(
        proposal(
            SocialAction.SEND_MESSAGE,
            body="I have a verified result you may find relevant.",
            target_core_id=peer.core_id,
        )
    )
    assert planner.calls == []
    decision = engine.initiate(
        peer.core_id,
        topic_key="robotics",
        room_id="dm-3",
        planner=planner,
    )
    assert decision.action is SocialAction.SEND_MESSAGE
    assert decision.permitted
    assert decision.execution_authority is False
    assert len(planner.calls) == 1
    assert transport.actions == [SocialAction.SEND_MESSAGE]
