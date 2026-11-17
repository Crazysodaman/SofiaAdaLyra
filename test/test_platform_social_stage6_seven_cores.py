from __future__ import annotations

import pytest

from sofia.platform.chat_clients.contracts import (
    ChatPermissionDenied,
    ConnectionState,
    MembershipStatus,
    RoomKind,
)
from sofia.platform.chat_clients.controller import ChatClientController
from sofia.platform.chat_clients.stage6_simulation import (
    EvidenceCategory,
    SyntheticStage6World,
    run_stage6_deterministic_suite,
)

pytestmark = pytest.mark.pkg_social


def test_stage6_deterministic_suite_reports_all_scenarios_without_overclaiming():
    report = run_stage6_deterministic_suite()
    assert report.all_passed is True
    names = {item.name for item in report.scenarios}
    assert names == {
        "seven_cores_in_general",
        "simultaneous_inbound",
        "direct_and_group",
        "core_initiated_conversations",
        "invite_leave_decline",
        "independent_relationships",
        "owner_history_review",
        "denial_and_revocation",
        "shared_inference_queue_and_gaming",
        "restart_and_reconnect",
        "stop_and_authorization",
        "bounded_long_autonomy",
        "seven_core_scale_without_identity_leakage",
    }
    assert report.synthetic_core_count == 7
    assert report.category is EvidenceCategory.DETERMINISTIC_SIMULATION
    assert report.installed_production_core_count == 0
    assert report.real_ollama_invoked is False
    assert report.process_boundaries_exercised is False
    assert report.installed_host_acceptance is False
    assert "synthetic" in report.claim_boundary()
    assert "installed" in report.claim_boundary()


def test_seven_synthetic_cores_have_independent_identity_state_and_policy():
    world = SyntheticStage6World()
    identities = world.identities()
    assert len(identities) == 7
    assert len({item.core_id for item in identities}) == 7
    assert len({item.platform_id for item in identities}) == 7
    assert len({world.private_token(item.core_id) for item in identities}) == 7
    assert len({
        world.model_policy(item.core_id).policy_id for item in identities
    }) == 7

    world.set_impression(
        identities[0].core_id, identities[1].core_id,
        respect=90, skepticism=10, trust=80,
    )
    world.set_impression(
        identities[2].core_id, identities[1].core_id,
        respect=20, skepticism=90, trust=15,
    )
    assert world.impressions(identities[0].core_id)[identities[1].core_id] != (
        world.impressions(identities[2].core_id)[identities[1].core_id]
    )
    copy = world.impressions(identities[0].core_id)
    copy[identities[1].core_id]["trust"] = 1
    assert world.impressions(identities[0].core_id)[
        identities[1].core_id
    ]["trust"] == 80
    assert world.model_policy(identities[0].core_id) != (
        world.model_policy(identities[1].core_id)
    )


def test_all_seven_cores_receive_simultaneous_general_messages():
    world = SyntheticStage6World()
    identities = world.identities()
    for index, identity in enumerate(identities):
        world.send_message(
            identity.core_id, "room.general", f"simultaneous {index}",
            client_message_id=f"seven.simultaneous.{index}",
        )
    histories = {
        identity.core_id: world.history_page(
            identity.core_id, "room.general"
        ).messages
        for identity in identities
    }
    assert all(len(messages) == 7 for messages in histories.values())
    assert all(
        [item.sequence for item in messages] == list(range(1, 8))
        for messages in histories.values()
    )


def test_dm_group_invite_leave_and_no_identity_leakage():
    world = SyntheticStage6World()
    identities = world.identities()
    dm = world.initiate_direct(identities[0].core_id, identities[1].core_id)
    world.send_message(
        identities[0].core_id, dm.room_id, "private one",
        client_message_id="seven.dm.1",
    )
    assert world.history_page(
        identities[1].core_id, dm.room_id
    ).messages
    with pytest.raises(ChatPermissionDenied):
        world.history_page(identities[2].core_id, dm.room_id)

    group = world.create_private_group(
        identities[0].core_id, title="three core group",
        member_core_ids=[identities[1].core_id, identities[2].core_id],
    )
    with pytest.raises(ChatPermissionDenied):
        world.history_page(identities[1].core_id, group.room_id)
    accepted = world.respond_to_invite(
        identities[1].core_id, group.room_id, accept=True
    )
    declined = world.respond_to_invite(
        identities[2].core_id, group.room_id, accept=False
    )
    assert accepted.status is MembershipStatus.ACTIVE
    assert declined.status is MembershipStatus.DECLINED
    world.send_message(
        identities[0].core_id, group.room_id, "after invite",
        client_message_id="seven.group.1",
    )
    assert world.history_page(
        identities[1].core_id, group.room_id
    ).messages
    with pytest.raises(ChatPermissionDenied):
        world.history_page(identities[2].core_id, group.room_id)

    left = world.leave_room(identities[1].core_id, group.room_id)
    assert left.status is MembershipStatus.LEFT
    with pytest.raises(ChatPermissionDenied):
        world.send_message(
            identities[1].core_id, group.room_id, "after leaving",
            client_message_id="seven.group.2",
        )


def test_core_initiated_conversations_and_owner_review_requires_authorization():
    world = SyntheticStage6World()
    identities = world.identities()
    for index, identity in enumerate(identities):
        peer = identities[(index + 1) % len(identities)]
        receipt = world.initiate_direct_message(
            identity.core_id, peer.core_id, f"conversation {index}",
            client_message_id=f"seven.initiate.{index}",
        )
        assert receipt.message is not None
        assert receipt.message.origin.value == "core"

    room_id = world.initiate_direct(
        identities[0].core_id, identities[1].core_id
    ).room_id
    with pytest.raises(ChatPermissionDenied, match="OWNER_REVIEW_NOT_AUTHORIZED"):
        world.owner_review(identities[0].core_id, room_id)
    world.grant_owner_review()
    page = world.owner_review(identities[0].core_id, room_id)
    assert page.messages
    assert len(world.owner_reviews()) == 1
    assert world.owner_reviews()[0].room_id == room_id


def test_restart_reconnect_preserves_history_and_rejects_stale_generation():
    world = SyntheticStage6World()
    old_identities = {item.core_id: item for item in world.identities()}
    core = old_identities[next(iter(old_identities))]
    world.send_message(
        core.core_id, "room.general", "before restart",
        client_message_id="seven.restart.1",
    )
    controller = ChatClientController(backend=world, client_id="cli")
    controller.select_core(core)
    controller.open_room("room.general")
    assert any(
        message.body == "before restart"
        for message in controller.snapshot().messages
    )

    world.restart()
    with pytest.raises(ChatPermissionDenied, match="STALE_GENERATION"):
        controller.select_core(core)
    new_core = next(
        item for item in world.identities()
        if item.core_id == core.core_id
    )
    assert new_core.generation == core.generation + 1
    world.reconnect_core(new_core.core_id)
    controller.select_core(new_core)
    controller.open_room("room.general")
    assert any(
        message.body == "before restart"
        for message in controller.snapshot().messages
    )
    assert controller.connection is ConnectionState.CONNECTED


def test_stop_and_authorization_deny_consequential_social_operations():
    world = SyntheticStage6World()
    identities = world.identities()
    world.stop()
    with pytest.raises(ChatPermissionDenied, match="STOP_ACTIVE"):
        world.send_message(
            identities[0].core_id, "room.general", "stopped",
            client_message_id="seven.stop.1",
        )
    with pytest.raises(ChatPermissionDenied, match="STOP_ACTIVE"):
        world.request_inference(identities[0].core_id)
    assert world.message_count("room.general") == 0

    world.resume()
    world.restrict_core(identities[1].core_id, ["chat.receive"])
    with pytest.raises(ChatPermissionDenied, match="OPERATION_NOT_AUTHORIZED"):
        world.send_message(
            identities[1].core_id, "room.general", "not authorized",
            client_message_id="seven.stop.2",
        )
    assert world.message_count("room.general") == 0


def test_group_kinds_and_membership_epochs_are_stable():
    world = SyntheticStage6World()
    identities = world.identities()
    dm = world.initiate_direct(identities[0].core_id, identities[1].core_id)
    group = world.create_private_group(
        identities[0].core_id, title="stable group",
        member_core_ids=[identities[2].core_id],
    )
    general = next(
        room for room in world.list_rooms(identities[0].core_id)
        if room.kind is RoomKind.GENERAL
    )
    assert general.room_id == "room.general"
    assert dm.kind is RoomKind.DIRECT
    assert group.kind is RoomKind.PRIVATE_GROUP
    rows = {
        row.core_id: row
        for row in world.memberships(identities[0].core_id, group.room_id)
    }
    assert rows[identities[0].core_id].epoch == 1
    assert rows[identities[0].core_id].status is MembershipStatus.ACTIVE
    assert rows[identities[2].core_id].status is MembershipStatus.INVITED
