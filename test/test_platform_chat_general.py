from concurrent.futures import ThreadPoolExecutor
import sqlite3
from uuid import uuid4

import pytest

from sofia.platform.chat import (
    ChatActor,
    ChatEngine,
    CoreIdentity,
    MembershipStatus,
    MessageOrigin,
)


def make_engine(tmp_path, **kwargs):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    return ChatEngine(path, owner_id="platform:owner", **kwargs)


def make_core(name="Ada", platform="platform:a"):
    return CoreIdentity(uuid4(), platform, 1, name)


@pytest.fixture
def engine(tmp_path):
    return make_engine(tmp_path)


def test_general_is_visible_to_owner_and_authorized_cores_with_history(engine):
    owner = engine.owner_actor()
    ada = make_core("Ada")
    bea = make_core("Bea")
    engine.register_core(ada)
    engine.register_core(bea)

    first = engine.send(owner, "general", "owner message")
    second = engine.send(ChatActor.core(ada), "general", "Ada while owner away")
    third = engine.send(ChatActor.core(bea), "general", "Bea while owner away")

    assert [first.sequence, second.sequence, third.sequence] == [1, 2, 3]
    owner_history = engine.history(owner, "general", limit=10)
    assert [message.body for message in owner_history.messages] == [
        "owner message",
        "Ada while owner away",
        "Bea while owner away",
    ]
    assert owner_history.history_from_sequence == 1
    assert engine.membership(owner, "general", ada.core_id_text).status is MembershipStatus.ACTIVE
    assert engine.membership(owner, "general", bea.core_id_text).status is MembershipStatus.ACTIVE


def test_ordering_and_pagination_use_stable_per_room_sequence(engine):
    owner = engine.owner_actor()
    ada = make_core()
    actor = ChatActor.core(ada)
    engine.register_core(ada)
    for index in range(5):
        engine.send(actor if index % 2 else owner, "general", f"message {index}")

    first = engine.history(owner, "general", limit=2)
    assert [message.sequence for message in first.messages] == [1, 2]
    assert first.has_more is True
    assert first.next_cursor == 2

    second = engine.history(owner, "general", after_sequence=first.next_cursor, limit=2)
    assert [message.sequence for message in second.messages] == [3, 4]
    assert second.has_more is True
    assert second.next_cursor == 4

    third = engine.history(owner, "general", after_sequence=second.next_cursor, limit=2)
    assert [message.sequence for message in third.messages] == [5]
    assert third.has_more is False
    assert third.next_cursor is None


def test_idempotency_and_message_id_deduplicate_one_logical_message(engine):
    owner = engine.owner_actor()
    first = engine.send(
        owner,
        "general",
        "once",
        idempotency_key="idem-1",
        message_id="stable-message-id",
    )
    duplicate = engine.send(
        owner,
        "general",
        "once",
        idempotency_key="idem-1",
        message_id="stable-message-id",
    )
    assert duplicate.message_id == first.message_id
    assert len(engine.history(owner, "general").messages) == 1
    with pytest.raises(ValueError):
        engine.send(owner, "general", "different", idempotency_key="idem-1")
    with pytest.raises(ValueError):
        engine.send(owner, "general", "different body", message_id="stable-message-id")


def test_reply_edit_tombstone_cursor_and_private_draft(engine):
    owner = engine.owner_actor()
    ada = make_core()
    actor = ChatActor.core(ada)
    engine.register_core(ada)

    original = engine.send(owner, "general", "original")
    reply = engine.send(actor, "general", "reply", reply_to=original.message_id)
    assert reply.reply_to == original.message_id
    assert reply.origin is MessageOrigin.LOCAL_CORE

    edited = engine.edit_message(owner, original.message_id, "edited")
    assert edited.body == "edited"
    assert edited.revision == 1
    with pytest.raises(PermissionError):
        engine.edit_message(actor, original.message_id, "hijack")

    tombstone = engine.delete_message(actor, reply.message_id, reason="cleanup")
    assert tombstone.is_tombstone
    assert tombstone.body == ""
    with pytest.raises(PermissionError):
        engine.edit_message(actor, reply.message_id, "resurrect")

    assert engine.set_cursor(actor, "general", edited.sequence) == edited.sequence
    assert engine.cursor(actor, "general") == edited.sequence

    draft = engine.save_draft(actor, "general", "unsent text", reply_to=original.message_id)
    assert draft is not None and draft.body == "unsent text"
    assert engine.draft(actor, "general").body == "unsent text"
    assert engine.draft(owner, "general") is None
    engine.clear_draft(actor, "general")
    assert engine.draft(actor, "general") is None


def test_concurrent_senders_serialize_sequence_without_loss(engine):
    owner = engine.owner_actor()
    cores = [make_core(f"Core{index}", f"platform:{index}") for index in range(4)]
    for core in cores:
        engine.register_core(core)
    actors = [ChatActor.core(core) for core in cores]

    def send(index):
        actor = actors[index % len(actors)]
        return engine.send(
            actor,
            "general",
            f"concurrent {index}",
            idempotency_key=f"concurrent-{index}",
        ).sequence

    with ThreadPoolExecutor(max_workers=8) as pool:
        sequences = list(pool.map(send, range(40)))

    assert sorted(sequences) == list(range(1, 41))
    page = engine.history(owner, "general", limit=200)
    assert [message.sequence for message in page.messages] == list(range(1, 41))
    message_ids = [message.message_id for message in page.messages]
    assert len(set(message_ids)) == 40
