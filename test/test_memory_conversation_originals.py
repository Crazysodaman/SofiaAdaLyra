from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.memory.conversation_originals import (
    ConversationOriginalRetriever,
    OriginalRetrievalRequest,
)


def save(store, session_id, content, *, role=ConversationRole.USER):
    message = ConversationMessage(
        id=str(uuid4()),
        session_id=session_id,
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    store.save(message)
    return message


def test_reads_exact_persisted_originals_in_requested_order(tmp_path):
    store = ConversationStore(tmp_path / "memory.db")
    session = store.create_session()
    first = save(store, session.id, "  exact first  ")
    second = save(store, session.id, "exact second")

    result = ConversationOriginalRetriever(store).retrieve(
        OriginalRetrievalRequest(session.id, (second.id, first.id), 100)
    )

    assert [item.message_id for item in result.selected] == [second.id, first.id]
    assert [item.content for item in result.selected] == ["exact second", "  exact first  "]
    store.close()


def test_never_crosses_session_boundary(tmp_path):
    store = ConversationStore(tmp_path / "memory.db")
    allowed = store.create_session()
    other = store.create_session()
    visible = save(store, allowed.id, "visible")
    secret = save(store, other.id, "secret")

    result = ConversationOriginalRetriever(store).retrieve(
        OriginalRetrievalRequest(allowed.id, (secret.id, visible.id), 100)
    )

    assert [item.message_id for item in result.selected] == [visible.id]
    assert result.missing_ids == (secret.id,)
    assert all(item.content != "secret" for item in result.selected)
    store.close()


def test_budget_omits_but_never_truncates(tmp_path):
    store = ConversationStore(tmp_path / "memory.db")
    session = store.create_session()
    long = save(store, session.id, "12345")
    short = save(store, session.id, "x")

    result = ConversationOriginalRetriever(store).retrieve(
        OriginalRetrievalRequest(session.id, (long.id, short.id), 1)
    )

    assert result.omitted_ids == (long.id,)
    assert [item.content for item in result.selected] == ["x"]
    store.close()


def test_unknown_session_fails_closed(tmp_path):
    store = ConversationStore(tmp_path / "memory.db")
    with pytest.raises(LookupError):
        ConversationOriginalRetriever(store).retrieve(
            OriginalRetrievalRequest("missing", ("id",), 10)
        )
    store.close()


@pytest.mark.parametrize("ids", [[], ["x"], "x", None])
def test_message_ids_must_be_immutable_tuple(ids):
    with pytest.raises((TypeError, ValueError)):
        OriginalRetrievalRequest("session", ids, 10)
