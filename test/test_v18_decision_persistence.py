"""CA-001: same-event persistence evidence, never a new source of authority."""
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.application.decision_persistence import inspect_turn_persistence
from sofia.application.decision_trace import project_companion_decision
from sofia.cognition.matrix.model import (
    HistoryPolicy, MatrixConfidence, MatrixIntent, MatrixTrace,
    ResponseStrategy, TurnEnvelope, TurnMatrix,
)
from sofia.cognition.matrix.trace import MatrixTraceStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite

pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_verify]
NOW = datetime(2026, 10, 13, 18, tzinfo=timezone.utc)


def _fixture(tmp_path, *, binding=True, session="s1", role="user"):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    envelope = TurnEnvelope(
        message_id="unique-msg-1", session_id="s1",
        content="private message bytes", created_at=NOW,
        principal_id="principal:one", channel="desktop",
    )
    matrix = MatrixTrace(
        envelope=envelope,
        turn=TurnMatrix(
            intent=MatrixIntent.GENERAL,
            confidence=MatrixConfidence.HIGH,
            history_policy=HistoryPolicy.BOUNDED_RECENT,
            response_strategy=ResponseStrategy.GENERATIVE,
            domains=(),
        ),
        created_at=NOW + timedelta(milliseconds=25),
    )
    MatrixTraceStore(path).record(matrix)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "CREATE TABLE conversation_messages("
            "id TEXT PRIMARY KEY,session_id TEXT,role TEXT,"
            "content TEXT,created_at TEXT)"
        )
        db.execute(
            "INSERT INTO conversation_messages VALUES (?,?,?,?,?)",
            (envelope.message_id, session, role, envelope.content, NOW.isoformat()),
        )
        db.execute(
            "CREATE TABLE social_session_principal("
            "session_id TEXT PRIMARY KEY,principal_id TEXT,audience_id TEXT)"
        )
        if binding:
            db.execute(
                "INSERT INTO social_session_principal VALUES (?,?,?)",
                ("s1", "principal:one", "private:one"),
            )
    # Force the probe to consume the same deserialized, content-stripped
    # Matrix source the production application reads on every projection.
    return path, MatrixTraceStore(path).get(envelope.message_id)


def test_verified_source_and_matrix_decision_share_canonical_turn(tmp_path):
    path, matrix = _fixture(tmp_path)
    proof = inspect_turn_persistence(path, matrix_trace=matrix)
    assert proof.same_turn_verified
    assert proof.user_message_persisted
    assert proof.matrix_decision_persisted
    assert proof.principal_scope_verified
    projection = project_companion_decision(
        matrix_trace=matrix, neuro_snapshot=None,
        canonical_persistence=proof,
    )
    assert projection is not None
    assert projection.canonical_persistence == proof
    assert not projection.neuro_turn_correlated
    assert not projection.objective_verified
    assert projection.act_delivery_ref is None
    assert "private message bytes" not in repr(proof)
    assert "private message bytes" not in repr(projection)


@pytest.mark.parametrize(("binding", "session", "role", "expected"), [
    (False, "s1", "user", (True, True, False)),
    (True, "another-session", "user", (False, True, True)),
    (True, "s1", "assistant", (False, True, True)),
])
def test_incomplete_source_and_scope_cannot_be_claimed_as_linked(
    tmp_path, binding, session, role, expected,
):
    path, matrix = _fixture(tmp_path, binding=binding, session=session, role=role)
    proof = inspect_turn_persistence(path, matrix_trace=matrix)
    assert (
        proof.user_message_persisted,
        proof.matrix_decision_persisted,
        proof.principal_scope_verified,
    ) == expected
    assert not proof.same_turn_verified


def test_changed_principal_binding_fails_closed(tmp_path):
    path, matrix = _fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "UPDATE social_session_principal SET principal_id=? "
            "WHERE session_id=?", ("principal:other", "s1"),
        )
    assert not inspect_turn_persistence(
        path, matrix_trace=matrix,
    ).same_turn_verified


def test_changed_matrix_row_must_not_prove_causal_correspondence(tmp_path):
    path, matrix = _fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "UPDATE cognition_matrix_trace SET channel=? WHERE message_id=?",
            ("discord", matrix.envelope.message_id),
        )
    proof = inspect_turn_persistence(path, matrix_trace=matrix)
    assert proof.user_message_persisted
    assert not proof.matrix_decision_persisted
    assert not proof.same_turn_verified


def test_projection_refuses_proof_for_another_message_or_session(tmp_path):
    path, matrix = _fixture(tmp_path)
    proof = inspect_turn_persistence(path, matrix_trace=matrix)
    with pytest.raises(ValueError, match="another turn"):
        project_companion_decision(
            matrix_trace=matrix, neuro_snapshot=None,
            canonical_persistence=replace(proof, message_id="fake"),
        )


def test_missing_canonical_database_never_gets_recreated(tmp_path):
    path, matrix = _fixture(tmp_path)
    path.unlink()
    with pytest.raises(FileNotFoundError):
        inspect_turn_persistence(path, matrix_trace=matrix)
    assert not path.exists()


def test_live_application_projection_uses_real_persisted_turn(tmp_path):
    from sofia.application import SofiaApplication
    from sofia.verify.cognition_v2_baseline import _configuration

    config = _configuration(tmp_path)
    bootstrap_canonical_sqlite(config.state_path)
    app = SofiaApplication(config)
    try:
        app.start()
        app.conversation.respond("Test a single bounded decision")
        projection = app.latest_companion_decision_trace()
        assert projection is not None
        proof = projection.canonical_persistence
        assert proof is not None
        assert proof.user_message_persisted
        assert proof.matrix_decision_persisted
        # No authenticated session principal was provided. Do not promote
        # an anonymous conversation into verified audience-bound causality.
        assert not proof.principal_scope_verified
        assert not proof.same_turn_verified
    finally:
        app.shutdown()
