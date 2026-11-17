from __future__ import annotations

import pytest

from sofia.platform.chat_clients.contracts import (
    ChatPermissionDenied,
    ConnectionState,
    MembershipStatus,
    SendStatus,
)
from sofia.platform.chat_clients.controller import (
    ChatClientController,
    NotificationMode,
)
from sofia.platform.chat_clients.stage6_simulation import (
    EvidenceCategory,
    InferenceJob,
    Stage6Report,
    SyntheticStage6World,
    run_stage6_deterministic_suite,
)

pytestmark = pytest.mark.pkg_social


def test_shared_inference_queue_defers_background_while_gaming():
    world = SyntheticStage6World()
    identities = world.identities()
    jobs = [
        world.request_inference(item.core_id, category="background", priority=10)
        for item in identities
    ]
    assert len(jobs) == 7
    world.set_gaming(True)
    assert world.run_inference_step(capacity=7) == ()
    deferred = [
        row for row in world.inference.snapshot()
        if row["deferred_by_gaming"] > 0
    ]
    assert len(deferred) == 7

    interactive = world.request_inference(
        identities[0].core_id, category="interactive", priority=100
    )
    processed = world.run_inference_step(capacity=1)
    assert len(processed) == 1
    assert isinstance(processed[0], InferenceJob)
    assert processed[0].job_id == interactive.job_id

    world.set_gaming(False)
    assert len(world.run_inference_step(capacity=7)) == 7
    assert len(world.inference) == 0


def test_live_events_are_targeted_and_shortcut_does_not_leak():
    world = SyntheticStage6World()
    identities = world.identities()
    dm = world.initiate_direct(identities[0].core_id, identities[1].core_id)
    world.send_message(
        identities[0].core_id, dm.room_id, "direct only",
        client_message_id="reliability.dm.1",
    )
    outsider_events = world.events(
        after_revision=0, core_id=identities[2].core_id
    )
    assert all(event.room_id != dm.room_id for event in outsider_events)
    participant_events = world.events(
        after_revision=0, core_id=identities[1].core_id
    )
    assert any(event.room_id == dm.room_id for event in participant_events)

    general_events = world.events(
        after_revision=0, core_id=identities[3].core_id
    )
    assert all(event.kind != "message" for event in general_events)

    world.send_message(
        identities[0].core_id, "room.general", "hello @Mira",
        client_message_id="reliability.general.1",
    )
    mira_events = [
        event for event in world.events(
            after_revision=0, core_id=identities[4].core_id
        )
        if event.kind == "message"
    ]
    assert mira_events
    assert mira_events[-1].mentioned_core_ids == (identities[4].core_id.lower(),)


def test_inactive_channel_unread_mention_and_mute_control():
    world = SyntheticStage6World()
    identities = world.identities()
    group = world.create_private_group(
        identities[0].core_id, title="reliability",
        member_core_ids=[identities[1].core_id],
    )
    world.respond_to_invite(identities[1].core_id, group.room_id, accept=True)
    sender = ChatClientController(backend=world, client_id="sender")
    sender.select_core(identities[0])
    sender.open_room(group.room_id)
    receiver = ChatClientController(backend=world, client_id="receiver")
    receiver.select_core(identities[1])
    receiver.open_room("room.general")

    sender.send("reliability mention @Roland")
    channels = {item.room_id: item for item in receiver.drain_live_events()}
    assert channels[group.room_id].unread == 1
    assert channels[group.room_id].mentions == 1

    receiver.set_notification(group.room_id, NotificationMode.MENTIONS)
    sender.send("plain update")
    channels = {item.room_id: item for item in receiver.drain_live_events()}
    assert channels[group.room_id].unread == 2
    assert channels[group.room_id].mentions == 1
    assert channels[group.room_id].notification is NotificationMode.MENTIONS


def test_revocation_is_fail_closed_and_cannot_reconnect():
    world = SyntheticStage6World()
    identities = world.identities()
    revoked = identities[6]
    world.revoke_core(revoked.core_id)
    assert world.connection_state(revoked.core_id) is ConnectionState.REVOKED
    rows = {
        row.core_id: row for row in world.memberships(
            identities[0].core_id, "room.general"
        )
    }
    assert rows[revoked.core_id].status is MembershipStatus.REVOKED
    with pytest.raises(ChatPermissionDenied, match="CORE_REVOKED"):
        world.send_message(
            revoked.core_id, "room.general", "revoked send",
            client_message_id="reliability.revoke.1",
        )
    with pytest.raises(ChatPermissionDenied, match="CORE_REVOKED"):
        world.reconnect_core(revoked.core_id)
    with pytest.raises(ChatPermissionDenied):
        world.history_page(revoked.core_id, "room.general")


def test_stop_overrides_social_trust_and_impressions():
    world = SyntheticStage6World()
    identities = world.identities()
    world.set_impression(
        identities[0].core_id, identities[1].core_id,
        respect=100, skepticism=0, trust=100,
    )
    world.stop()
    with pytest.raises(ChatPermissionDenied, match="STOP_ACTIVE"):
        world.send_message(
            identities[0].core_id, "room.general",
            "affection is not authorization",
            client_message_id="reliability.trust.1",
        )
    assert world.message_count("room.general") == 0


def test_bounded_long_autonomy_does_not_unbound_queue_or_history():
    world = SyntheticStage6World()
    identities = world.identities()
    for cycle in range(400):
        core = identities[cycle % 7]
        peer = identities[(cycle + 1) % 7]
        world.initiate_direct_message(
            core.core_id, peer.core_id, f"long cycle {cycle}",
            client_message_id=f"reliability.long.{cycle}",
        )
        if cycle % 3 == 0:
            world.request_inference(core.core_id, category="background")
        world.run_inference_step(capacity=3)
    assert len(world.inference) <= world.inference.max_jobs
    assert all(
        world.message_count(room_id) <= 4_000
        for room_id in world.list_room_ids()
    )
    assert world.message_count("room.general") == 0


def test_stage6_evidence_categories_are_explicit():
    assert {item.value for item in EvidenceCategory} == {
        "deterministic_simulation",
        "process_integration",
        "real_ollama",
        "installed_host_acceptance",
    }
    report = run_stage6_deterministic_suite()
    assert isinstance(report, Stage6Report)
    assert report.category is EvidenceCategory.DETERMINISTIC_SIMULATION
    assert report.installed_production_core_count == 0
    assert report.real_ollama_invoked is False
    assert report.process_boundaries_exercised is False
    assert report.installed_host_acceptance is False


def test_duplicate_client_message_id_is_idempotent():
    world = SyntheticStage6World()
    core = world.identities()[0]
    first = world.send_message(
        core.core_id, "room.general", "once",
        client_message_id="reliability.idempotent.1",
    )
    second = world.send_message(
        core.core_id, "room.general", "once again",
        client_message_id="reliability.idempotent.1",
    )
    assert first.status is SendStatus.SENT_CONFIRMED
    assert second == first
    assert world.message_count("room.general") == 1
