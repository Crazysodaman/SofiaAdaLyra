"""STOP, authorization and cross-Core isolation for social autonomy."""
from datetime import datetime, timedelta, timezone

from sofia.platform.social.autonomy.contracts import (
    AutonomyLimits,
    SocialAction,
    SocialEvent,
    SocialEventKind,
)
from sofia.platform.social.autonomy.engine import AutonomousSocialEngine
from sofia.platform.social.autonomy.evidence import EvidenceCategory
from sofia.platform.social.autonomy.models import BoundaryKind, PeerFacet
from sofia.platform.social.autonomy.store import SocialAutonomyStore
from test.social_autonomy_support import (
    AllowAuthorization,
    FakeStop,
    MutableClock,
    RecordingTransport,
    StaticPlanner,
    identity,
    message,
    proposal,
    state_path,
)


NOW = datetime(2026, 4, 5, 11, 0, tzinfo=timezone.utc)


def _engine(tmp_path, *, stop=None, authorization=None, transport=None):
    store = SocialAutonomyStore(state_path(tmp_path))
    core = identity("Ada")
    engine = AutonomousSocialEngine(
        core,
        store,
        clock=MutableClock(NOW),
        stop=stop or FakeStop(),
        authorization=authorization or AllowAuthorization(),
        transport=transport or RecordingTransport(),
        limits=AutonomyLimits(contact_cooldown=timedelta(0)),
    )
    return store, core, engine


def _event(core, peer, index=1):
    return SocialEvent(
        event_id=f"event-{index}",
        core_id=core.core_id,
        kind=SocialEventKind.MESSAGE_RECEIVED,
        occurred_at=NOW,
        room_id="general-1",
        chain_id="safety-chain",
        message=message(
            peer,
            message_id=f"msg-{index}",
            body="A message that would otherwise be answered.",
            now=NOW,
            sequence=index,
        ),
    )


def test_operator_stop_refuses_all_social_choices(tmp_path):
    transport = RecordingTransport()
    store, core, engine = _engine(
        tmp_path, stop=FakeStop(True), transport=transport
    )
    peer = identity("Lyda")
    planner = StaticPlanner(proposal(SocialAction.REPLY, body="Should not send."))

    decision = engine.receive(_event(core, peer), planner=planner)
    assert decision.action is SocialAction.REFUSED
    assert decision.permitted is False
    assert planner.calls == []
    assert transport.decisions == []
    assert engine.block_peer(peer.core_id, reason="x").action is SocialAction.REFUSED
    assert engine.leave_room("general-1", reason="x").action is SocialAction.REFUSED
    assert engine.propose_disclosure(
        peer.core_id, item_ref="memory-1", classification="private"
    ).action is SocialAction.REFUSED
    assert store.boundaries(core.core_id) == ()


def test_authorization_denial_wins_over_strong_interpersonal_trust(tmp_path):
    transport = RecordingTransport()
    authorization = AllowAuthorization(allow_all=False)
    store, core, engine = _engine(
        tmp_path, authorization=authorization, transport=transport
    )
    peer = identity("Lyda")
    engine.set_facet(
        peer.core_id,
        PeerFacet.AFFINITY,
        level=1.0,
        reason="Extremely warm but not a permission.",
        evidence_refs=("interaction-1",),
    )
    planner = StaticPlanner(proposal(SocialAction.REPLY, body="Should not send."))

    decision = engine.receive(_event(core, peer), planner=planner)
    assert decision.action is SocialAction.REFUSED
    assert "authorization" in decision.reason
    assert decision.execution_authority is False
    assert transport.decisions == []

    disclosure = engine.propose_disclosure(
        peer.core_id, item_ref="memory-1", classification="private"
    )
    assert disclosure.action is SocialAction.REFUSED
    assert disclosure.permitted is False

    authorization.allowed.add((core.core_id, SocialAction.SHARE))
    allowed = engine.propose_disclosure(
        peer.core_id, item_ref="memory-1", classification="private"
    )
    assert allowed.action is SocialAction.SHARE
    assert allowed.permitted is True
    assert allowed.payload_ref == "memory-1"
    assert allowed.execution_authority is False


def test_chat_autonomy_never_executes_without_authorization(tmp_path):
    transport = RecordingTransport()
    authorization = AllowAuthorization(allow_all=False)
    store, core, engine = _engine(
        tmp_path, authorization=authorization, transport=transport
    )
    peer = identity("Lyda")
    planner = StaticPlanner(
        proposal(
            SocialAction.SEND_MESSAGE,
            body="A meaningful message.",
            target_core_id=peer.core_id,
        )
    )
    denied = engine.receive(_event(core, peer), planner=planner)
    assert denied.action is SocialAction.REFUSED
    assert denied.execution_authority is False
    assert transport.decisions == []

    authorization.allowed.add((core.core_id, SocialAction.SEND_MESSAGE))
    allowed = engine.receive(
        SocialEvent(
            event_id="event-2",
            core_id=core.core_id,
            kind=SocialEventKind.MESSAGE_RECEIVED,
            occurred_at=NOW,
            room_id="general-1",
            chain_id="safety-chain-2",
            message=message(
                peer,
                message_id="msg-2",
                body="A second message.",
                now=NOW,
                sequence=2,
            ),
        ),
        planner=planner,
    )
    assert allowed.action is SocialAction.SEND_MESSAGE
    assert allowed.permitted is True
    assert allowed.execution_authority is False
    assert len(transport.decisions) == 1


def test_no_cross_core_state_leakage_in_one_state_file(tmp_path):
    store = SocialAutonomyStore(state_path(tmp_path))
    clock = MutableClock(NOW)
    ada = identity("Ada")
    lyda = identity("Lyda")
    ada_engine = AutonomousSocialEngine(
        ada,
        store,
        clock=clock,
        stop=FakeStop(),
        authorization=AllowAuthorization(),
    )
    lyda_engine = AutonomousSocialEngine(
        lyda,
        store,
        clock=clock,
        stop=FakeStop(),
        authorization=AllowAuthorization(),
    )

    ada_engine.set_facet(
        lyda.core_id,
        PeerFacet.AFFINITY,
        level=0.9,
        reason="Ada's private stance.",
        evidence_refs=("interaction-1",),
    )
    ada_engine.record_evidence(
        category=EvidenceCategory.PEER_CLAIM,
        claim="Ada heard a private claim.",
        evidence_ref="peer-claim-private",
        peer_core_id=lyda.core_id,
    )
    ada_engine.set_interest("robotics", 0.9)
    ada_engine.set_goal("private-goal", "Ada's private goal.", 0.7)
    ada_engine.record_opinion(
        topic="design",
        statement="Ada's private opinion.",
        stance=0.4,
        confidence=0.6,
        evidence_refs=("interaction-1",),
        peer_core_id=lyda.core_id,
    )
    ada_engine.set_topic(
        "private-topic",
        summary="Ada's private unresolved issue.",
        peer_core_id=lyda.core_id,
        room_id="dm-private",
        next_revisit_at=NOW + timedelta(days=1),
    )
    ada_engine.set_boundary(lyda.core_id, BoundaryKind.NO_CONTACT, None)

    assert lyda_engine.relationship(ada.core_id).known is False
    assert lyda_engine.active_evidence() == ()
    assert lyda_engine.appraisals() == ()
    assert lyda_engine.topics() == ()
    assert lyda_engine.opinions() == ()
    assert store.interests(lyda.core_id) == ()
    assert store.goals(lyda.core_id) == ()
    assert store.boundaries(lyda.core_id) == ()
    assert store.contact_allowed(
        core_id=lyda.core_id, peer_core_id=ada.core_id, room_id="general-1"
    ) is True

    try:
        lyda_engine.receive(_event(ada, lyda), planner=None)
    except ValueError as exc:
        assert "different Core identity" in str(exc)
    else:
        raise AssertionError("cross-Core event must be rejected")

def test_seven_independent_cores_keep_their_own_social_state(tmp_path):
    store = SocialAutonomyStore(state_path(tmp_path))
    clock = MutableClock(NOW)
    peer = identity("SharedPeer")
    cores = [identity(f"Core{index}") for index in range(7)]
    engines = [
        AutonomousSocialEngine(
            core,
            store,
            clock=clock,
            stop=FakeStop(),
            authorization=AllowAuthorization(),
        )
        for core in cores
    ]
    for index, (core, engine) in enumerate(zip(cores, engines), start=1):
        engine.set_interest(f"topic{index}", index / 10)
        engine.set_facet(
            peer.core_id,
            PeerFacet.AFFINITY,
            level=index / 10,
            reason=f"Core{index} has its own stance.",
            evidence_refs=(f"interaction-{index}",),
        )
        engine.record_evidence(
            category=EvidenceCategory.OBSERVED,
            claim=f"Core{index} observed a distinct interaction.",
            evidence_ref=f"observed-{index}",
            peer_core_id=peer.core_id,
        )

    for index, (core, engine) in enumerate(zip(cores, engines), start=1):
        assert engine.relationship(peer.core_id).effective(
            PeerFacet.AFFINITY
        ) == index / 10
        assert len(engine.active_evidence(peer_core_id=peer.core_id)) == 1
        assert store.interests(core.core_id)[0].name == f"topic{index}"
