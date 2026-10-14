"""CA-001: stable source event -> actual durable assistant response receipt."""
from contextlib import closing
import json
import sqlite3

import pytest

from sofia.application.decision_persistence import inspect_turn_persistence
from test.test_v18_decision_persistence import _fixture, NOW

pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_verify]


def _settled(tmp_path):
    state, matrix = _fixture(tmp_path)
    with closing(sqlite3.connect(state)) as db, db:
        db.execute(
            "INSERT INTO conversation_messages VALUES (?,?,?,?,?)",
            ("assistant-response-1", "s1", "assistant",
             "private assistant reply", NOW.isoformat()),
        )
        db.execute(
            "CREATE TABLE canonical_conversation_turn("
            "event_id TEXT PRIMARY KEY,user_message_id TEXT,"
            "assistant_message_id TEXT,owner_principal_id TEXT,"
            "source_audience_id TEXT,source_channel TEXT,"
            "source_session_id TEXT,status TEXT,response_json TEXT,"
            "settled_at TEXT)"
        )
        db.execute(
            "INSERT INTO canonical_conversation_turn VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("event:1", matrix.envelope.message_id,
             "assistant-response-1", "principal:one",
             "private:one", "desktop", "s1", "completed",
             json.dumps({"content": "private assistant reply", "tool_calls": []}),
             NOW.isoformat()),
        )
    return state, matrix


def test_actual_settled_reply_is_tied_to_original_event_without_content(tmp_path):
    state, matrix = _settled(tmp_path)
    result = inspect_turn_persistence(state, matrix_trace=matrix)
    assert result.same_turn_verified
    assert result.assistant_reply_persisted
    assert result.canonical_turn_settled
    assert result.canonical_event_id == "event:1"
    assert result.assistant_message_id == "assistant-response-1"
    assert "private assistant reply" not in repr(result)
    assert "tool_calls" not in repr(result)
    assert "execution" in result.limitation


@pytest.mark.parametrize(("field", "value"), [
    ("status", "uncertain"),
    ("source_session_id", "foreign-session"),
    ("source_audience_id", "private:other"),
    ("owner_principal_id", "principal:other"),
    ("source_channel", "discord"),
    ("response_json", '{"content":"invented reply"}'),
    ("assistant_message_id", "missing-assistant"),
    ("settled_at", "invalid-timestamp"),
])
def test_unsettled_or_rebound_claim_cannot_prove_assistant_reply(
    tmp_path, field, value,
):
    state, matrix = _settled(tmp_path)
    assert field in {
        "status", "source_session_id", "source_audience_id",
        "owner_principal_id", "source_channel", "response_json",
        "assistant_message_id", "settled_at",
    }
    with closing(sqlite3.connect(state)) as db, db:
        db.execute(
            f"UPDATE canonical_conversation_turn SET {field}=? WHERE event_id=?",
            (value, "event:1"),
        )
    result = inspect_turn_persistence(state, matrix_trace=matrix)
    assert result.same_turn_verified
    assert not result.canonical_turn_settled
    assert not result.assistant_reply_persisted
    assert result.canonical_event_id is None
    assert result.assistant_message_id is None


def test_reply_without_independent_social_binding_is_not_accepted(tmp_path):
    state, matrix = _settled(tmp_path)
    with closing(sqlite3.connect(state)) as db, db:
        db.execute("DELETE FROM social_session_principal WHERE session_id=?", ("s1",))
    result = inspect_turn_persistence(state, matrix_trace=matrix)
    assert result.user_message_persisted
    assert result.matrix_decision_persisted
    assert not result.principal_scope_verified
    assert not result.canonical_turn_settled


def test_assistant_role_and_content_must_match_immutable_settlement(tmp_path):
    state, matrix = _settled(tmp_path)
    with closing(sqlite3.connect(state)) as db, db:
        db.execute(
            "UPDATE conversation_messages SET role=? WHERE id=?",
            ("system", "assistant-response-1"),
        )
    assert not inspect_turn_persistence(
        state, matrix_trace=matrix,
    ).assistant_reply_persisted


def test_legacy_schema_with_no_settlement_owner_reports_unverified(tmp_path):
    state, matrix = _fixture(tmp_path)
    result = inspect_turn_persistence(state, matrix_trace=matrix)
    assert result.same_turn_verified
    assert not result.assistant_reply_persisted
    assert not result.canonical_turn_settled
    assert result.canonical_event_id is None
