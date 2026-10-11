from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.memory.originals import (
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


def test_exact_originals_do_not_materialize_complete_session(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path / "memory.db")
    session = store.create_session()
    original = [save(store, session.id, f"historical original {number}")
                for number in range(160)]
    # A hot-path regression must fail if code falls back to loading 160
    # messages into Python rather than just the selected two.
    def prohibited_full_materialization(*args, **kwargs):
        raise AssertionError("full-session materialization is forbidden")

    monkeypatch.setattr(store, "list_messages", prohibited_full_materialization)
    result = ConversationOriginalRetriever(store).retrieve(
        OriginalRetrievalRequest(
            session.id, (original[125].id, original[9].id, original[125].id),
            200,
        )
    )
    assert [item.message_id for item in result.selected] == [
        original[125].id, original[9].id,
    ]
    assert [item.position for item in result.selected] == [125, 9]
    assert result.missing_ids == ()
    store.close()


def test_exact_retrieval_timestamp_ties_have_stable_original_positions(tmp_path):
    store = ConversationStore(tmp_path / "memory.db")
    session = store.create_session()
    tied = datetime(2026, 10, 11, 8, tzinfo=timezone.utc)
    for identifier in ("b", "c", "a"):
        store.save(ConversationMessage(
            id=identifier, session_id=session.id,
            role=ConversationRole.USER, content=identifier,
            created_at=tied,
        ))
    result = ConversationOriginalRetriever(store).retrieve(
        OriginalRetrievalRequest(session.id, ("c", "a", "b"), 100)
    )
    assert [item.position for item in result.selected] == [2, 0, 1]
    store.close()


def test_exact_source_query_rejects_unbounded_id_batches(tmp_path):
    store = ConversationStore(tmp_path / "memory.db")
    session = store.create_session()
    with pytest.raises(ValueError, match="128"):
        ConversationOriginalRetriever(store).retrieve(
            OriginalRetrievalRequest(
                session.id, tuple(f"source-{number}" for number in range(129)),
                100,
            )
        )
    assert store.exact_originals(session.id, message_ids=()) == ()
    store.close()
