from datetime import datetime

from sofia.conversation.model import (
    ConversationMessage,
    ConversationRole,
)
from sofia.conversation.store import ConversationStore


def test_conversation_store_persists_messages(
    tmp_path,
):
    database_path = tmp_path / "sofia.db"

    store = ConversationStore(database_path)

    first_message = ConversationMessage(
        id="message-1",
        session_id="session-1",
        role=ConversationRole.USER,
        content="Hello, Sofía.",
        created_at=datetime.now(),
    )

    second_message = ConversationMessage(
        id="message-2",
        session_id="session-1",
        role=ConversationRole.ASSISTANT,
        content="Hello, Sparks.",
        created_at=datetime.now(),
    )

    store.save(first_message)
    store.save(second_message)

    reloaded_store = ConversationStore(database_path)

    messages = reloaded_store.list_messages(
        "session-1"
    )

    assert messages == (
        first_message,
        second_message,
    )

def test_conversation_store_isolates_sessions(
    tmp_path,
):
    database_path = tmp_path / "sofia.db"

    store = ConversationStore(database_path)

    session_one_message = ConversationMessage(
        id="message-1",
        session_id="session-1",
        role=ConversationRole.USER,
        content="Message from session one.",
        created_at=datetime.now(),
    )

    session_two_message = ConversationMessage(
        id="message-2",
        session_id="session-2",
        role=ConversationRole.USER,
        content="Message from session two.",
        created_at=datetime.now(),
    )

    store.save(session_one_message)
    store.save(session_two_message)

    session_one_messages = store.list_messages(
        "session-1"
    )

    session_two_messages = store.list_messages(
        "session-2"
    )

    assert session_one_messages == (
        session_one_message,
    )

    assert session_two_messages == (
        session_two_message,
    )

def test_conversation_store_returns_messages_in_creation_order(
    tmp_path,
):
    database_path = tmp_path / "sofia.db"

    store = ConversationStore(database_path)

    first = ConversationMessage(
        id="message-1",
        session_id="session-1",
        role=ConversationRole.USER,
        content="First.",
        created_at=datetime.fromisoformat(
            "2026-09-13T13:00:00"
        ),
    )

    second = ConversationMessage(
        id="message-2",
        session_id="session-1",
        role=ConversationRole.ASSISTANT,
        content="Second.",
        created_at=datetime.fromisoformat(
            "2026-09-13T13:00:01"
        ),
    )

    third = ConversationMessage(
        id="message-3",
        session_id="session-1",
        role=ConversationRole.USER,
        content="Third.",
        created_at=datetime.fromisoformat(
            "2026-09-13T13:00:02"
        ),
    )

    store.save(third)
    store.save(first)
    store.save(second)

    messages = store.list_messages(
        "session-1"
    )

    assert messages == (
        first,
        second,
        third,
    )