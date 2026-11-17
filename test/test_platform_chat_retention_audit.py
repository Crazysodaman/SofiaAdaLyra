from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest

from sofia.platform.chat import (
    ChatActor,
    ChatEngine,
    CoreIdentity,
    MembershipStatus,
)


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value = self.value + timedelta(seconds=seconds)


T0 = datetime(2026, 11, 17, 15, tzinfo=timezone.utc)


def make_engine(path, **kwargs):
    if not path.exists():
        with sqlite3.connect(path):
            pass
    return ChatEngine(path, owner_id="platform:owner", **kwargs)


def core(name, platform="platform:a"):
    return CoreIdentity(uuid4(), platform, 1, name)


def test_membership_and_permission_changes_are_audited(tmp_path):
    path = tmp_path / "sofia.db"
    engine = make_engine(path, clock=Clock(T0))
    owner = engine.owner_actor()
    ada = core("Ada")
    bea = core("Bea")
    engine.register_core(ada)
    engine.register_core(bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.create_group(ada_actor, "Audited", member_ids=[bea.core_id_text])
    invitation = engine.pending_invitations(bea_actor, room_id=room.room_id)[0]
    engine.accept_invitation(bea_actor, invitation.invite_id)
    engine.revoke_membership(ada_actor, room.room_id, bea.core_id_text)
    engine.block(ada_actor, bea.core_id_text, reason="boundary")

    events = engine.audit_events(owner, room_id=room.room_id)
    types = {event.event_type for event in events}
    assert "chat.membership.invited" in types
    assert "chat.membership.accepted" in types
    assert "chat.membership.revoked" in types
    all_events = engine.audit_events(owner)
    assert any(
        event.event_type == "chat.permission.blocked"
        and event.payload.get("target_id") == bea.core_id_text
        for event in all_events
    )
    assert engine.verify_audit() == (True, None)


def test_retention_deletes_old_messages_with_audit_evidence(tmp_path):
    clock = Clock(T0)
    path = tmp_path / "sofia.db"
    engine = make_engine(path, clock=clock)
    owner = engine.owner_actor()
    ada = core("Ada")
    bea = core("Bea")
    engine.register_core(ada)
    engine.register_core(bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.create_group(
        ada_actor,
        "Retained",
        member_ids=[bea.core_id_text],
        retention_seconds=60,
    )
    engine.join_room(bea_actor, room.room_id)
    engine.send(ada_actor, room.room_id, "expire me")
    assert len(engine.history(bea_actor, room.room_id).messages) == 1

    clock.advance(120)
    result = engine.apply_retention(owner)
    assert result.deleted_messages == 1
    assert engine.history(bea_actor, room.room_id).messages == ()
    events = engine.audit_events(owner, room_id=room.room_id)
    assert any(
        event.event_type == "chat.retention.cleanup"
        and event.payload.get("deleted_messages") == 1
        for event in events
    )


def test_pending_invitation_expiry_is_durable(tmp_path):
    clock = Clock(T0)
    path = tmp_path / "sofia.db"
    engine = make_engine(path, clock=clock)
    owner = engine.owner_actor()
    ada = core("Ada")
    bea = core("Bea")
    engine.register_core(ada)
    engine.register_core(bea)
    ada_actor = ChatActor.core(ada)
    bea_actor = ChatActor.core(bea)

    room = engine.create_group(ada_actor, "Expiring")
    invitation = engine.invite(
        ada_actor,
        room.room_id,
        bea.core_id_text,
        expires_at=T0 + timedelta(seconds=10),
    )
    clock.advance(20)
    result = engine.apply_retention(owner)
    assert result.expired_invitations == 1
    assert engine.membership(ada_actor, room.room_id, bea.core_id_text).status is MembershipStatus.EXPIRED
    with pytest.raises(ValueError):
        engine.accept_invitation(bea_actor, invitation.invite_id)


def test_operator_stop_suspends_core_chat_but_not_owner_local_chat(tmp_path):
    path = tmp_path / "sofia.db"
    engine = make_engine(path, stop_provider=lambda: True)
    owner = engine.owner_actor()
    ada = core("Ada")
    engine.register_core(ada)

    engine.send(owner, "general", "owner local message is not outreach")
    with pytest.raises(PermissionError):
        engine.send(ChatActor.core(ada), "general", "core outreach suspended")
