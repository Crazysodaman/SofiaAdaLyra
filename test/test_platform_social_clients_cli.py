from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sofia.platform.chat_clients.accessibility import (
    accessibility_summary,
    keyboard_commands,
)
from sofia.platform.chat_clients.contracts import (
    ChatOffline,
    ChatPermissionDenied,
    ChatRoom,
    ConnectionState,
    CoreIdentity,
    MembershipStatus,
    MessagePage,
    RoomKind,
    RoomMembership,
    SendReceipt,
    SendStatus,
)
from sofia.platform.chat_clients.controller import (
    ChatClientController,
    NotificationMode,
    PendingSendStatus,
)
from sofia.platform.chat_clients.drafts import (
    ClientDraftStore,
    MemoryDraftPersistence,
)
from sofia.platform.chat_clients.render import render_chat_screen
from sofia.platform.chat_clients.stage6_simulation import SyntheticStage6World

pytestmark = pytest.mark.pkg_social


def _controller(
    world: SyntheticStage6World, *, core_index: int, client_id: str = "cli",
    drafts: ClientDraftStore | None = None,
) -> ChatClientController:
    controller = ChatClientController(
        backend=world, client_id=client_id, drafts=drafts,
    )
    controller.select_core(world.identities()[core_index])
    return controller


def _group(world: SyntheticStage6World, creator: int, member: int) -> ChatRoom:
    identities = world.identities()
    room = world.create_private_group(
        identities[creator].core_id, title="private research",
        member_core_ids=[identities[member].core_id],
    )
    world.respond_to_invite(
        identities[member].core_id, room.room_id, accept=True
    )
    return room


def test_sidebar_has_general_private_and_direct_channels_and_core_selector():
    world = SyntheticStage6World()
    identities = world.identities()
    dm = world.initiate_direct(identities[0].core_id, identities[1].core_id)
    group = _group(world, 0, 2)
    controller = _controller(world, core_index=0)

    snapshot = controller.snapshot()
    assert snapshot.selected_core == identities[0]
    assert snapshot.connection is ConnectionState.CONNECTED
    kinds = {channel.kind for channel in snapshot.channels}
    assert RoomKind.GENERAL in kinds
    assert RoomKind.PRIVATE_GROUP in kinds
    assert RoomKind.DIRECT in kinds
    assert {channel.room_id for channel in snapshot.channels} >= {
        "room.general", group.room_id, dm.room_id,
    }
    text = render_chat_screen(snapshot, width=80)
    assert "CORE: Lyra" in text
    assert "CONNECTION: CONNECTED" in text
    assert "# general" in text


def test_history_pagination_is_bounded_and_deduplicated():
    world = SyntheticStage6World()
    core_id = world.identities()[0].core_id
    for index in range(125):
        world.send_message(
            core_id, "room.general", f"message {index}",
            client_message_id=f"history.{index}",
        )
    controller = _controller(world, core_index=0)
    controller.open_room("room.general")
    first = controller.snapshot()
    assert len(first.messages) == 50
    assert first.has_older is True

    controller.load_older(limit=50)
    second = controller.snapshot()
    assert len(second.messages) == 100
    assert second.has_older is True

    controller.load_older(limit=50)
    third = controller.snapshot()
    assert len(third.messages) == 125
    assert third.has_older is False
    sequences = [message.sequence for message in third.messages]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))


def test_draft_restores_across_client_instances():
    world = SyntheticStage6World()
    persistence = MemoryDraftPersistence()
    first_store = ClientDraftStore(
        client_id="cli", persistence=persistence
    )
    first = _controller(world, core_index=0, drafts=first_store)
    first.open_room("room.general")
    saved = first.save_draft("unfinished question")
    assert saved is not None and saved.content == "unfinished question"

    second_store = ClientDraftStore(
        client_id="cli", persistence=persistence
    )
    second = _controller(world, core_index=0, drafts=second_store)
    second.open_room("room.general")
    restored = second.draft()
    assert restored is not None
    assert restored.content == "unfinished question"


def test_mentions_replies_unread_and_notification_controls():
    world = SyntheticStage6World()
    group = _group(world, 0, 1)
    sender = _controller(world, core_index=0, client_id="sender")
    receiver = _controller(world, core_index=1, client_id="receiver")
    receiver.open_room("room.general")

    sender.open_room(group.room_id)
    receipt = sender.send("hello @Roland")
    assert receipt.status is SendStatus.SENT_CONFIRMED

    channels = {item.room_id: item for item in receiver.drain_live_events()}
    assert channels[group.room_id].unread == 1
    assert channels[group.room_id].mentions == 1
    assert any(
        notice.code == "NEW_MESSAGE" for notice in receiver.notices()
    )

    receiver.set_notification(group.room_id, NotificationMode.MUTED)
    notices_before = len([
        item for item in receiver.notices() if item.code == "NEW_MESSAGE"
    ])
    sender.send("quiet update")
    channels = {item.room_id: item for item in receiver.drain_live_events()}
    assert channels[group.room_id].unread == 2
    notices_after = len([
        item for item in receiver.notices() if item.code == "NEW_MESSAGE"
    ])
    assert notices_after == notices_before

    sender.open_room("room.general")
    original = sender.send("original")
    reply = sender.send("reply body", reply_to=original.message.message_id)
    assert reply.status is SendStatus.SENT_CONFIRMED
    receiver.open_room("room.general")
    receiver.drain_live_events()
    rendered = receiver.snapshot().messages
    assert any(
        item.reply_to == original.message.message_id
        and item.body == "reply body"
        for item in rendered
    )


def test_permission_denied_and_offline_preserve_the_draft():
    world = SyntheticStage6World()
    core = world.identities()[0]
    controller = _controller(
        world, core_index=0,
        drafts=ClientDraftStore(client_id="cli"),
    )
    controller.open_room("room.general")
    controller.save_draft("keep me on failure")

    world.restrict_core(core.core_id, ["chat.receive"])
    receipt = controller.send()
    assert receipt.status is SendStatus.DENIED
    assert receipt.denial_code == "OPERATION_NOT_AUTHORIZED"
    assert any(
        notice.severity.value == "denied" for notice in controller.notices()
    )
    assert controller.draft().content == "keep me on failure"

    world.restrict_core(core.core_id, ["chat.send", "chat.receive"])
    world.set_offline(core.core_id)
    with pytest.raises(ChatOffline):
        controller.send()
    assert controller.draft().content == "keep me on failure"
    assert controller.connection is not ConnectionState.CONNECTED


def test_owner_core_system_distinction_and_keyboard_accessibility():
    world = SyntheticStage6World()
    core = world.identities()[0]
    world.owner_send("room.general", "owner note")
    world.system_send("room.general", "system notice")
    world.send_message(
        core.core_id, "room.general", "core note",
        client_message_id="distinction.core",
    )
    controller = _controller(world, core_index=0)
    controller.open_room("room.general")
    rendered = controller.snapshot().messages
    kinds = {item.speaker_kind.value for item in rendered}
    assert kinds == {"owner", "core", "system"}
    labels = {item.speaker_label for item in rendered}
    assert {"Owner", "System", "Lyra"} <= labels

    summary = accessibility_summary(controller.snapshot())
    assert summary["uses_color_for_status"] is False
    assert summary["core_label"] == "Lyra generation 1"
    assert summary["connection"] == "CONNECTED"
    assert "core_selector" in summary["focus_order"]
    assert any(item.key == "Tab" and item.enabled for item in keyboard_commands(
        controller.snapshot()
    ))
    plain = render_chat_screen(
        controller.snapshot(), width=80, no_color=True
    )
    assert "\x1b[" not in plain
    assert "[OWNER]" in plain and "[CORE]" in plain and "[SYSTEM]" in plain


def test_cross_client_sync_and_core_identity_isolation():
    world = SyntheticStage6World()
    identities = world.identities()
    alice = _controller(world, core_index=0, client_id="cli")
    bob = _controller(world, core_index=1, client_id="desktop")
    bob.open_room("room.general")
    alice.open_room("room.general")
    alice.send("cross-client message")
    bob.drain_live_events()
    assert any(
        item.body == "cross-client message"
        for item in bob.snapshot().messages
    )

    dm = world.initiate_direct(identities[0].core_id, identities[1].core_id)
    alice.open_room(dm.room_id)
    alice.send("private to Roland")
    bob.open_room(dm.room_id)
    bob.drain_live_events()
    assert any(item.body == "private to Roland" for item in bob.snapshot().messages)

    outsider = _controller(world, core_index=2, client_id="android")
    assert dm.room_id not in {
        item.room_id for item in outsider.snapshot().channels
    }
    with pytest.raises(ChatPermissionDenied):
        outsider.open_room(dm.room_id)
    assert all(
        item.body != "private to Roland" for item in outsider.snapshot().messages
    )


def test_same_core_clients_sync_without_self_unread():
    world = SyntheticStage6World()
    group = _group(world, 0, 1)
    first = _controller(world, core_index=0, client_id="cli")
    second = _controller(world, core_index=0, client_id="desktop")
    second.open_room(group.room_id)
    first.open_room(group.room_id)
    first.send("same Core, other client")
    channels = {item.room_id: item for item in second.drain_live_events()}
    assert any(
        item.body == "same Core, other client"
        for item in second.snapshot().messages
    )
    assert channels[group.room_id].unread == 0
    assert channels[group.room_id].mentions == 0


def test_private_group_invite_membership_display_and_leave():
    world = SyntheticStage6World()
    identities = world.identities()
    creator = _controller(world, core_index=0, client_id="cli")
    room = creator.create_private_group(
        "invite test", [identities[1].core_id]
    )
    members = {item.core_id: item for item in creator.members(room.room_id)}
    invited = members[identities[1].core_id]
    assert invited.status is MembershipStatus.INVITED
    assert invited.display_name == "Roland"

    invitee = _controller(world, core_index=1, client_id="desktop")
    assert room.room_id in {
        item.room_id for item in invitee.snapshot().channels
    }
    invitee.respond_to_invite(room.room_id, accept=True)
    members = {item.core_id: item for item in invitee.members(room.room_id)}
    assert members[identities[1].core_id].status is MembershipStatus.ACTIVE
    assert members[identities[1].core_id].is_selected_core is True

    invitee.leave_room(room.room_id)
    assert room.room_id not in {
        item.room_id for item in invitee.snapshot().channels
    }
    members = {item.core_id: item for item in creator.members(room.room_id)}
    assert members[identities[1].core_id].status is MembershipStatus.LEFT


def test_stale_generation_and_unknown_core_are_denied():
    world = SyntheticStage6World()
    old = {item.core_id: item for item in world.identities()}
    controller = _controller(world, core_index=0)
    world.restart()
    with pytest.raises(ChatPermissionDenied, match="STALE_GENERATION"):
        controller.select_core(old[controller.selected_core.core_id])
    with pytest.raises(ChatPermissionDenied, match="CORE_NOT_ENROLLED"):
        controller.select_core("00000000-0000-0000-0000-000000000000")
    fresh = {item.core_id: item for item in world.identities()}
    controller.select_core(fresh[controller.selected_core.core_id])
    assert controller.snapshot().selected_core.generation == 2


class _ReceiptBackend:
    def __init__(self, statuses: list[SendStatus]) -> None:
        self._core = CoreIdentity(
            core_id="11111111-1111-4111-8111-111111111111",
            platform_id="platform.test",
            generation=1,
            display_name="Test",
        )
        self._statuses = list(statuses)
        self._room = ChatRoom(
            room_id="room.general", kind=RoomKind.GENERAL,
            title="general", created_by_core_id=None,
            created_at=datetime.now(timezone.utc),
        )
        self._membership = RoomMembership(
            room_id="room.general", core_id=self._core.core_id, epoch=1,
            status=MembershipStatus.ACTIVE,
            joined_at=datetime.now(timezone.utc),
            history_from_sequence=0,
        )

    def list_cores(self):
        return (self._core,)

    def connection_state(self, core_id):
        return ConnectionState.CONNECTED

    def list_rooms(self, core_id):
        return (self._room,)

    def memberships(self, core_id, room_id):
        return (self._membership,)

    def history_page(self, core_id, room_id, *, before_sequence=None, limit=50):
        return MessagePage(
            messages=(), before_sequence=before_sequence, has_more=False,
            oldest_sequence=None, newest_sequence=None,
        )

    def send_message(self, core_id, room_id, body, *, client_message_id,
                     reply_to=None, audience=None):
        status = self._statuses.pop(0)
        return SendReceipt(
            client_message_id=client_message_id, room_id=room_id,
            status=status,
        )

    def events(self, *, after_revision, core_id=None):
        return ()


def test_pending_and_uncertain_sends_remain_visible_without_false_success():
    backend = _ReceiptBackend([
        SendStatus.PENDING,
        SendStatus.OUTCOME_UNKNOWN,
        SendStatus.SENT_UNCONFIRMED,
    ])
    controller = ChatClientController(backend=backend, client_id="cli")
    controller.select_core(backend.list_cores()[0])
    controller.open_room("room.general")

    pending = controller.send("first")
    assert pending.status is SendStatus.PENDING
    assert controller.pending_sends()[0].status is PendingSendStatus.PENDING

    uncertain = controller.send("second")
    assert uncertain.status is SendStatus.OUTCOME_UNKNOWN
    unconfirmed = controller.send("third")
    assert unconfirmed.status is SendStatus.SENT_UNCONFIRMED
    statuses = {item.status for item in controller.pending_sends()}
    assert PendingSendStatus.PENDING in statuses
    assert PendingSendStatus.UNCERTAIN in statuses
    assert len(controller.pending_sends()) == 3
    rendered = render_chat_screen(controller.snapshot(), no_color=True)
    assert "[PENDING]" in rendered
    assert "[UNCERTAIN]" in rendered
