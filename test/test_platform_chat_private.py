import sqlite3
from uuid import uuid4

import pytest

from sofia.platform.chat import (
    ChatActor,
    ChatEngine,
    CoreIdentity,
    InvitationStatus,
    MembershipStatus,
    RoomHistoryPolicy,
    RoomKind,
)


@pytest.fixture
def engine(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    return ChatEngine(path, owner_id="platform:owner")


def core(name):
    return CoreIdentity(uuid4(), f"platform:{name.lower()}", 1, name)


def register(engine, *cores):
    for value in cores:
        engine.register_core(value)


def test_owner_and_core_private_direct_is_owner_initiated_and_isolated(engine):
    owner = engine.owner_actor()
    ada = core("Ada")
    bea = core("Bea")
    register(engine, ada, bea)

    room = engine.open_direct(owner, ada.core_id_text)
    assert room.kind is RoomKind.DIRECT
    engine.send(owner, room.room_id, "private owner note")
    engine.send(ChatActor.core(ada), room.room_id, "private reply")
    assert [m.body for m in engine.history(owner, room.room_id).messages] == [
        "private owner note",
        "private reply",
    ]

    outsider = ChatActor.core(bea)
    with pytest.raises(PermissionError):
        engine.history(outsider, room.room_id)
    with pytest.raises(PermissionError):
        engine.send(outsider, room.room_id, "intrusion")


def test_core_to_core_direct_requires_explicit_acceptance(engine):
    ada = core("Ada")
    bea = core("Bea")
    register(engine, ada, bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.open_direct(ada_actor, bea.core_id_text)
    with pytest.raises(PermissionError):
        engine.history(bea_actor, room.room_id)
    with pytest.raises(PermissionError):
        engine.send(ada_actor, room.room_id, "too early")

    membership = engine.join_room(bea_actor, room.room_id)
    assert membership.status is MembershipStatus.ACTIVE
    message = engine.send(ada_actor, room.room_id, "accepted")
    assert [m.message_id for m in engine.history(bea_actor, room.room_id).messages] == [
        message.message_id
    ]


def test_late_join_does_not_leak_pre_join_messages(engine):
    ada = core("Ada")
    bea = core("Bea")
    register(engine, ada, bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.create_group(ada_actor, "Engineering", member_ids=[bea.core_id_text])
    before = engine.send(ada_actor, room.room_id, "secret before join")
    engine.join_room(bea_actor, room.room_id)

    assert engine.history(bea_actor, room.room_id).messages == ()
    after = engine.send(ada_actor, room.room_id, "after join")
    history = engine.history(bea_actor, room.room_id)
    assert [m.message_id for m in history.messages] == [after.message_id]
    assert before.sequence < history.history_from_sequence


def test_explicit_history_grant_is_bounded_to_an_epoch(engine):
    ada = core("Ada")
    bea = core("Bea")
    register(engine, ada, bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.create_group(
        ada_actor,
        "Review",
        history_policy=RoomHistoryPolicy.EXPLICIT_GRANT,
    )
    for index in range(3):
        engine.send(ada_actor, room.room_id, f"history {index}")
    invitation = engine.invite(
        ada_actor,
        room.room_id,
        bea.core_id_text,
        history_from_sequence=2,
    )
    membership = engine.accept_invitation(bea_actor, invitation.invite_id)
    assert membership.history_from_sequence == 2
    history = engine.history(bea_actor, room.room_id)
    assert [m.sequence for m in history.messages] == [2, 3]
    assert history.history_from_sequence == 2

    with pytest.raises(PermissionError):
        no_grant_room = engine.create_group(ada_actor, "No grant")
        engine.invite(
            ada_actor,
            no_grant_room.room_id,
            bea.core_id_text,
            history_from_sequence=1,
        )


def test_decline_and_revoked_invitation_end_lifecycle(engine):
    ada = core("Ada")
    bea = core("Bea")
    register(engine, ada, bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.create_group(ada_actor, "Decline", member_ids=[bea.core_id_text])
    invitation = engine.pending_invitations(bea_actor, room_id=room.room_id)[0]
    declined = engine.decline_invitation(bea_actor, invitation.invite_id)
    assert declined.status is InvitationStatus.DECLINED
    assert engine.membership(ada_actor, room.room_id, bea.core_id_text).status is MembershipStatus.DECLINED
    with pytest.raises(ValueError):
        engine.accept_invitation(bea_actor, invitation.invite_id)

    second = engine.invite(ada_actor, room.room_id, bea.core_id_text)
    engine.revoke_invitation(ada_actor, second.invite_id)
    assert engine.membership(ada_actor, room.room_id, bea.core_id_text).status is MembershipStatus.REVOKED
    with pytest.raises(ValueError):
        engine.accept_invitation(bea_actor, second.invite_id)


def test_revocation_removes_private_room_access_immediately(engine):
    owner = engine.owner_actor()
    ada = core("Ada")
    bea = core("Bea")
    register(engine, ada, bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.create_group(ada_actor, "Revocation", member_ids=[bea.core_id_text])
    engine.join_room(bea_actor, room.room_id)
    engine.send(bea_actor, room.room_id, "member text")
    engine.revoke_membership(ada_actor, room.room_id, bea.core_id_text, reason="test")

    with pytest.raises(PermissionError):
        engine.history(bea_actor, room.room_id)
    with pytest.raises(PermissionError):
        engine.send(bea_actor, room.room_id, "after revoke")
    assert engine.membership(ada_actor, room.room_id, bea.core_id_text).status is MembershipStatus.REVOKED
    events = engine.audit_events(owner, room_id=room.room_id)
    assert any(event.event_type == "chat.membership.revoked" for event in events)


def test_leave_block_and_owner_cannot_read_core_private_group(engine):
    owner = engine.owner_actor()
    ada = core("Ada")
    bea = core("Bea")
    register(engine, ada, bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.create_group(ada_actor, "Private", member_ids=[bea.core_id_text])
    engine.join_room(bea_actor, room.room_id)
    first = engine.send(ada_actor, room.room_id, "Ada says hi")
    with pytest.raises(PermissionError):
        engine.history(owner, room.room_id)

    engine.block(bea_actor, ada.core_id_text, reason="boundary")
    assert ada.core_id_text in engine.blocked(bea_actor)
    assert engine.history(bea_actor, room.room_id).messages == ()

    engine.leave_room(bea_actor, room.room_id)
    with pytest.raises(PermissionError):
        engine.history(bea_actor, room.room_id)
    assert engine.message(ada_actor, first.message_id).body == "Ada says hi"


def test_room_owner_block_removes_target_from_controlled_room(engine):
    ada = core("Ada")
    bea = core("Bea")
    register(engine, ada, bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.create_group(ada_actor, "Blocked", member_ids=[bea.core_id_text])
    engine.join_room(bea_actor, room.room_id)
    engine.send(bea_actor, room.room_id, "before block")
    engine.block(ada_actor, bea.core_id_text, reason="owner block")

    assert engine.membership(ada_actor, room.room_id, bea.core_id_text).status is MembershipStatus.BLOCKED
    with pytest.raises(PermissionError):
        engine.history(bea_actor, room.room_id)
    with pytest.raises(PermissionError):
        engine.send(bea_actor, room.room_id, "after block")


def test_metadata_update_and_membership_epoch_advance(engine):
    ada = core("Ada")
    bea = core("Bea")
    register(engine, ada, bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.create_group(ada_actor, "Topic room", topic="initial")
    original_epoch = room.membership_epoch
    assert room.owner_core_id == ada.core_id_text
    updated = engine.update_room(ada_actor, room.room_id, name="Renamed", topic="new")
    assert updated.name == "Renamed"
    assert updated.topic == "new"
    with pytest.raises(PermissionError):
        engine.update_room(bea_actor, room.room_id, name="hijack")

    invitation = engine.invite(ada_actor, room.room_id, bea.core_id_text)
    accepted = engine.accept_invitation(bea_actor, invitation.invite_id)
    assert accepted.epoch > original_epoch
    current = engine.room(ada_actor, room.room_id)
    assert current.membership_epoch >= accepted.epoch
