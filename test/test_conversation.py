from datetime import datetime, timedelta

from sofia.conversation.model import (
    ConversationMessage,
    ConversationRole,
    ConversationSession,
)
from sofia.conversation.store import ConversationStore


def test_conversation_store_persists_messages(
    tmp_path,
):
    database_path = tmp_path / "sofia.db"

    store = ConversationStore(database_path)

    session = store.create_session()

    message = ConversationMessage(
        id="message-1",
        session_id=session.id,
        role=ConversationRole.USER,
        content="Hello, Sofía.",
        created_at=datetime.fromisoformat(
            "2026-09-13T19:00:00+00:00"
        ),
    )

    store.save(message)

    loaded = store.list_messages(session.id)

    assert loaded == (message,)


def test_conversation_store_isolates_sessions(
    tmp_path,
):
    database_path = tmp_path / "sofia.db"

    store = ConversationStore(database_path)

    session_one = store.create_session()
    session_two = store.create_session()

    message_one = ConversationMessage(
        id="message-1",
        session_id=session_one.id,
        role=ConversationRole.USER,
        content="Session one.",
        created_at=datetime.fromisoformat(
            "2026-09-13T19:00:00+00:00"
        ),
    )

    message_two = ConversationMessage(
        id="message-2",
        session_id=session_two.id,
        role=ConversationRole.USER,
        content="Session two.",
        created_at=datetime.fromisoformat(
            "2026-09-13T19:01:00+00:00"
        ),
    )

    store.save(message_one)
    store.save(message_two)

    assert store.list_messages(session_one.id) == (
        message_one,
    )

    assert store.list_messages(session_two.id) == (
        message_two,
    )


def test_conversation_store_returns_messages_in_creation_order(
    tmp_path,
):
    database_path = tmp_path / "sofia.db"

    store = ConversationStore(database_path)

    session = store.create_session()

    first_message = ConversationMessage(
        id="message-1",
        session_id=session.id,
        role=ConversationRole.USER,
        content="First.",
        created_at=datetime.fromisoformat(
            "2026-09-13T19:00:00+00:00"
        ),
    )

    second_message = ConversationMessage(
        id="message-2",
        session_id=session.id,
        role=ConversationRole.ASSISTANT,
        content="Second.",
        created_at=datetime.fromisoformat(
            "2026-09-13T19:01:00+00:00"
        ),
    )

    store.save(second_message)
    store.save(first_message)

    assert store.list_messages(session.id) == (
        first_message,
        second_message,
    )


def test_conversation_store_creates_and_persists_session(
    tmp_path,
):
    database_path = tmp_path / "sofia.db"

    store = ConversationStore(database_path)

    session = store.create_session()

    loaded = store.get_session(session.id)

    assert loaded == session


def test_saving_message_updates_session_timestamp(
    tmp_path,
):
    database_path = tmp_path / "sofia.db"

    store = ConversationStore(database_path)

    session = store.create_session()

    message_time = session.created_at + timedelta(
        seconds=1
    )

    message = ConversationMessage(
        id="message-1",
        session_id=session.id,
        role=ConversationRole.USER,
        content="Activity should update the session.",
        created_at=message_time,
    )

    store.save(message)

    updated_session = store.get_session(
        session.id
    )

    assert updated_session is not None
    assert updated_session.id == session.id
    assert updated_session.created_at == session.created_at
    assert updated_session.updated_at == message_time

def test_saving_older_message_does_not_rewind_session_timestamp(
    tmp_path,
):
    database_path = tmp_path / "sofia.db"

    store = ConversationStore(database_path)

    session = store.create_session()

    newer_message_time = session.created_at + timedelta(
        seconds=2
    )

    newer_message = ConversationMessage(
        id="message-1",
        session_id=session.id,
        role=ConversationRole.USER,
        content="Newer activity.",
        created_at=newer_message_time,
    )

    store.save(newer_message)

    older_message_time = session.created_at + timedelta(
        seconds=1
    )

    older_message = ConversationMessage(
        id="message-2",
        session_id=session.id,
        role=ConversationRole.ASSISTANT,
        content="Older activity.",
        created_at=older_message_time,
    )

    store.save(older_message)

    updated_session = store.get_session(
        session.id
    )

    assert updated_session is not None
    assert updated_session.updated_at == newer_message_time