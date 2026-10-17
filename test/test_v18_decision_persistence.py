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



def test_matrix_reloads_original_source_timestamp_not_decision_time(tmp_path):
    path, matrix = _fixture(tmp_path)
    assert matrix.envelope.created_at == NOW
    assert matrix.created_at == NOW + timedelta(milliseconds=25)
    with closing(sqlite3.connect(path)) as db:
        source, decision = db.execute(
            "SELECT source_created_at,created_at FROM cognition_matrix_trace "
            "WHERE message_id=?", (matrix.envelope.message_id,),
        ).fetchone()
    assert datetime.fromisoformat(source) == NOW
    assert datetime.fromisoformat(decision) == matrix.created_at
    assert inspect_turn_persistence(path, matrix_trace=matrix).same_turn_verified


def test_legacy_matrix_timestamp_cannot_be_backfilled_from_decision(tmp_path):
    path, matrix = _fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "UPDATE cognition_matrix_trace SET source_created_at=NULL "
            "WHERE message_id=?", (matrix.envelope.message_id,),
        )
    old_record = MatrixTraceStore(path).get(matrix.envelope.message_id)
    # A legacy record may still be displayed. Its substituted timestamp
    # must never be accepted as independent source-event evidence.
    assert old_record.envelope.created_at == old_record.created_at
    proof = inspect_turn_persistence(path, matrix_trace=old_record)
    assert not proof.user_message_persisted
    assert not proof.matrix_decision_persisted
    assert not proof.same_turn_verified


@pytest.mark.parametrize("source_time", [
    "2000-01-01T00:00:00+00:00",
    "2026-10-13T18:00:00",
    "not-an-iso-time",
    None,
])
def test_untrusted_matrix_source_timestamp_cannot_prove_user_event(
    tmp_path, source_time,
):
    path, matrix = _fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "UPDATE cognition_matrix_trace SET source_created_at=? "
            "WHERE message_id=?", (source_time, matrix.envelope.message_id),
        )
    proof = inspect_turn_persistence(path, matrix_trace=matrix)
    assert proof.user_message_persisted
    assert not proof.matrix_decision_persisted
    assert not proof.same_turn_verified


def test_matrix_source_timestamp_substitution_rejects_matching_id(tmp_path):
    path, matrix = _fixture(tmp_path)
    forged = (NOW + timedelta(milliseconds=10)).isoformat()
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "UPDATE cognition_matrix_trace SET source_created_at=? "
            "WHERE message_id=?", (forged, matrix.envelope.message_id),
        )
    reread = MatrixTraceStore(path).get(matrix.envelope.message_id)
    assert reread.envelope.created_at != NOW
    proof = inspect_turn_persistence(path, matrix_trace=reread)
    assert not proof.user_message_persisted
    assert not proof.same_turn_verified



def test_matrix_upsert_never_promotes_legacy_timestamp_to_proof(tmp_path):
    path, matrix = _fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "UPDATE cognition_matrix_trace SET source_created_at=NULL "
            "WHERE message_id=?", (matrix.envelope.message_id,),
        )
    legacy = MatrixTraceStore(path).get(matrix.envelope.message_id)
    # An ordinary extension/update pass must not silently mint evidence.
    MatrixTraceStore(path).record(legacy)
    with closing(sqlite3.connect(path)) as db:
        row = db.execute(
            "SELECT source_created_at FROM cognition_matrix_trace WHERE message_id=?",
            (matrix.envelope.message_id,),
        ).fetchone()
    assert row == (None,)
    proof = inspect_turn_persistence(path, matrix_trace=legacy)
    assert not proof.matrix_decision_persisted
    assert not proof.same_turn_verified


def test_matrix_upsert_cannot_replace_original_event_time(tmp_path):
    path, matrix = _fixture(tmp_path)
    forged = replace(
        matrix,
        envelope=replace(
            matrix.envelope,
            created_at=NOW + timedelta(milliseconds=10),
        ),
    )
    MatrixTraceStore(path).record(forged)
    with closing(sqlite3.connect(path)) as db:
        source, decision = db.execute(
            "SELECT source_created_at, created_at FROM cognition_matrix_trace "
            "WHERE message_id=?", (matrix.envelope.message_id,),
        ).fetchone()
    assert datetime.fromisoformat(source) == NOW
    assert datetime.fromisoformat(decision) == matrix.created_at
    assert not inspect_turn_persistence(
        path, matrix_trace=forged,
    ).matrix_decision_persisted
    restored = MatrixTraceStore(path).get(matrix.envelope.message_id)
    assert restored.envelope.created_at == NOW
    assert inspect_turn_persistence(
        path, matrix_trace=restored,
    ).same_turn_verified


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


def test_turn_neuro_provenance_is_exact_and_ephemeral(tmp_path):
    from sofia.application.conversation_service import ConversationService
    from sofia.neuro.model import NeuroStateSnapshot

    path, matrix = _fixture(tmp_path)
    snapshot = NeuroStateSnapshot(generated_at=NOW, focus=None)
    service = object.__new__(ConversationService)
    service._current_neuro_snapshot = snapshot
    service._current_neuro_message_id = matrix.envelope.message_id
    service._current_matrix_message_id = matrix.envelope.message_id
    assert service.neuro_observation_for_turn(
        message_id=matrix.envelope.message_id,
    ) is snapshot
    assert service.neuro_observation_for_turn(message_id="unrelated-turn") is None
    with pytest.raises(ValueError, match="message_id"):
        service.neuro_observation_for_turn(message_id="")

    evidence = project_companion_decision(
        matrix_trace=matrix, neuro_snapshot=snapshot,
        neuro_turn_snapshot=snapshot,
        canonical_persistence=inspect_turn_persistence(path, matrix_trace=matrix),
    )
    assert evidence.neuro_turn_correlated
    assert evidence.neuro_observed_for_turn_at == NOW
    assert not evidence.objective_verified

    # A new message, a missing observation or reset state cannot inherit
    # an earlier snapshot merely because NEURO last_snapshot is non-null.
    service._current_matrix_message_id = "newer-message"
    assert service.neuro_observation_for_turn(
        message_id=matrix.envelope.message_id,
    ) is None
    uncorrelated = project_companion_decision(
        matrix_trace=matrix, neuro_snapshot=snapshot,
        neuro_turn_snapshot=None,
    )
    assert not uncorrelated.neuro_turn_correlated
    assert uncorrelated.neuro_observed_for_turn_at is None
    assert uncorrelated.neuro_latest_at == NOW


def test_neuro_snapshot_cannot_be_claimed_before_it_was_observed(tmp_path):
    from sofia.neuro.model import NeuroStateSnapshot

    _path, matrix = _fixture(tmp_path)
    future = NeuroStateSnapshot(
        generated_at=matrix.created_at + timedelta(seconds=1),
        focus=None,
    )
    with pytest.raises(ValueError, match="cannot follow"):
        project_companion_decision(
            matrix_trace=matrix, neuro_snapshot=future,
            neuro_turn_snapshot=future,
        )



@pytest.mark.parametrize("invalid_audience", [None, "", "  "])
def test_incomplete_social_audience_never_proves_owner_scope(tmp_path, invalid_audience):
    path, matrix = _fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "UPDATE social_session_principal SET audience_id=? WHERE session_id=?",
            (invalid_audience, matrix.envelope.session_id),
        )
    proof = inspect_turn_persistence(path, matrix_trace=matrix)
    assert proof.user_message_persisted
    assert proof.matrix_decision_persisted
    assert not proof.principal_scope_verified
    assert not proof.same_turn_verified
    assert proof.verified_audience_id is None
    projection = project_companion_decision(
        matrix_trace=matrix, neuro_snapshot=None,
        canonical_persistence=proof,
    )
    assert projection is not None
    assert projection.source_event is not None
    assert projection.source_event.principal_id is None
    assert projection.source_event.audience_id is None
    assert not projection.source_event.can_authorize


@pytest.mark.parametrize("offset_ms", [-1, 1, 20])
def test_matrix_source_requires_exact_original_message_time(tmp_path, offset_ms):
    """Matching ID, role and earlier-than-Matrix time is insufficient."""
    path, matrix = _fixture(tmp_path)
    changed = NOW + timedelta(milliseconds=offset_ms)
    assert changed < matrix.created_at
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "UPDATE conversation_messages SET created_at=? WHERE id=?",
            (changed.isoformat(), matrix.envelope.message_id),
        )
    proof = inspect_turn_persistence(path, matrix_trace=matrix)
    assert not proof.user_message_persisted
    assert proof.matrix_decision_persisted
    assert proof.principal_scope_verified
    assert not proof.same_turn_verified
    assert not proof.canonical_turn_settled


def test_equivalent_timezone_offset_does_not_invalidate_source_timestamp(tmp_path):
    """Match instants, not the display form of an ISO 8601 timestamp."""
    path, matrix = _fixture(tmp_path)
    equivalent = NOW.astimezone(timezone(timedelta(hours=-5))).isoformat()
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "UPDATE conversation_messages SET created_at=? WHERE id=?",
            (equivalent, matrix.envelope.message_id),
        )
    proof = inspect_turn_persistence(path, matrix_trace=matrix)
    assert proof.user_message_persisted
    assert proof.same_turn_verified


@pytest.mark.parametrize("changed", [
    {"session_id": "s2"},
    {"principal_id": "principal:attacker"},
    {"channel": "discord"},
])
def test_matrix_upsert_cannot_rebind_message_identity(tmp_path, changed):
    """Same message ID never changes its session, principal or channel."""
    path, matrix = _fixture(tmp_path)
    original = MatrixTraceStore(path).get(matrix.envelope.message_id)
    forged = replace(matrix, envelope=replace(matrix.envelope, **changed))
    with pytest.raises(ValueError, match="identity mismatch or stale decision replay"):
        MatrixTraceStore(path).record(forged)
    restored = MatrixTraceStore(path).get(matrix.envelope.message_id)
    assert restored.envelope.session_id == original.envelope.session_id
    assert restored.envelope.principal_id == original.envelope.principal_id
    assert restored.envelope.channel == original.envelope.channel
    assert restored.created_at == original.created_at


def test_latest_matrix_trace_ties_have_stable_message_id_order(tmp_path):
    """Identically timestamped turns must have deterministic diagnostic ordering."""
    path, first = _fixture(tmp_path)
    store = MatrixTraceStore(path)
    second = replace(first, envelope=replace(first.envelope, message_id="unique-msg-2"))
    store.record(second)
    assert store.latest().envelope.message_id == "unique-msg-2"
    assert store.latest(session_id="s1").envelope.message_id == "unique-msg-2"
    # Replaying an existing trace must not randomly change latest().
    store.record(first)
    assert store.latest(session_id="s1").envelope.message_id == "unique-msg-2"


@pytest.mark.parametrize(("session", "principal", "channel", "allowed"), [
    ("s1", "principal:one", "desktop", True),
    ("s2", "principal:one", "desktop", False),
    ("s1", "principal:other", "desktop", False),
    ("s1", "principal:one", "discord", False),
])
def test_matrix_scoped_read_never_crosses_audience_binding(
    tmp_path, session, principal, channel, allowed,
):
    path, trace = _fixture(tmp_path)
    store = MatrixTraceStore(path)
    item = store.get_scoped(
        trace.envelope.message_id, session_id=session,
        principal_id=principal, channel=channel,
    )
    assert (item is not None) is allowed
    if item is not None:
        assert item.envelope.principal_id == principal
        assert item.envelope.session_id == session
        assert item.envelope.channel == channel


@pytest.mark.parametrize(("name", "value"), [
    ("message_id", ""), ("session_id", "  "),
    ("principal_id", ""), ("channel", ""),
])
def test_matrix_scoped_read_rejects_missing_identity(tmp_path, name, value):
    path, trace = _fixture(tmp_path)
    args = dict(message_id=trace.envelope.message_id, session_id="s1",
                principal_id="principal:one", channel="desktop")
    args[name] = value
    with pytest.raises(ValueError, match=name):
        MatrixTraceStore(path).get_scoped(
            args.pop("message_id"), **args,
        )


def test_matrix_prior_turn_read_is_isolated_by_principal_and_channel(tmp_path):
    path, trace = _fixture(tmp_path)
    store = MatrixTraceStore(path)
    assert store.latest_scoped(
        session_id="s1", principal_id="principal:one", channel="desktop"
    ).envelope.message_id == trace.envelope.message_id
    assert store.latest_scoped(
        session_id="s1", principal_id="principal:other", channel="desktop"
    ) is None
    assert store.latest_scoped(
        session_id="s1", principal_id="principal:one", channel="discord"
    ) is None
    assert store.latest_scoped(
        session_id="other", principal_id="principal:one", channel="desktop"
    ) is None
    # Anonymous traces must not inherit authenticated turns.
    assert store.latest_scoped(
        session_id="s1", principal_id="", channel="desktop"
    ) is None


def test_matrix_scoped_latest_uses_canonical_audience_index(tmp_path):
    """The live planner's common lookup must remain indexed as history grows."""
    path, trace = _fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        names = {
            row[1] for row in db.execute(
                "PRAGMA index_list(cognition_matrix_trace)"
            ).fetchall()
        }
        assert "idx_cognition_matrix_trace_audience" in names
        plan = db.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM cognition_matrix_trace "
            "WHERE session_id=? AND principal_id=? AND channel=? "
            "ORDER BY created_at DESC, message_id DESC LIMIT 1",
            ("s1", "principal:one", "desktop"),
        ).fetchall()
    assert any(
        "idx_cognition_matrix_trace_audience" in row[3]
        for row in plan
    ), plan
    assert MatrixTraceStore(path).latest_scoped(
        session_id="s1", principal_id="principal:one", channel="desktop"
    ).envelope.message_id == trace.envelope.message_id


def test_matrix_execution_diagnostics_use_partial_index(tmp_path):
    """Growing ordinary chat history must not cause full scans for execution."""
    path, _ = _fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        indexes = {
            row[1] for row in db.execute(
                "PRAGMA index_list(cognition_matrix_trace)"
            )
        }
        assert "idx_cognition_matrix_trace_execution" in indexes
        plan = db.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM cognition_matrix_trace "
            "WHERE session_id=? AND extensions_json IS NOT NULL "
            "ORDER BY created_at DESC, message_id DESC LIMIT ?",
            ("s1", 100),
        ).fetchall()
    assert any(
        "idx_cognition_matrix_trace_execution" in row[3]
        for row in plan
    ), plan


def test_matrix_stale_replay_does_not_rollback_completed_decision(tmp_path):
    path, original = _fixture(tmp_path)
    store = MatrixTraceStore(path)
    newer = replace(original, created_at=original.created_at + timedelta(seconds=5))
    store.record(newer)
    with pytest.raises(ValueError, match="stale decision replay"):
        store.record(original)
    recovered = MatrixTraceStore(path).get(original.envelope.message_id)
    assert recovered.created_at == newer.created_at


def test_matrix_same_revision_replay_is_idempotent(tmp_path):
    path, original = _fixture(tmp_path)
    store = MatrixTraceStore(path)
    store.record(original)
    assert store.count() == 1
    assert store.get(original.envelope.message_id).created_at == original.created_at


def test_matrix_legacy_schema_migrates_before_execution_index(tmp_path):
    """Older canonical databases may lack extensions_json at startup."""
    path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "CREATE TABLE cognition_matrix_trace ("
            "message_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,"
            "principal_id TEXT NOT NULL,channel TEXT NOT NULL,"
            "schema_version INTEGER NOT NULL,intent TEXT NOT NULL,"
            "confidence TEXT NOT NULL,history_policy TEXT NOT NULL,"
            "response_strategy TEXT NOT NULL,domains_json TEXT NOT NULL,"
            "ambiguous INTEGER NOT NULL,shadow INTEGER NOT NULL,"
            "created_at TEXT NOT NULL)"
        )
    store = MatrixTraceStore(path)
    assert store.count() == 0
    with closing(sqlite3.connect(path)) as db:
        cols = {
            item[1] for item in db.execute(
                "PRAGMA table_info(cognition_matrix_trace)"
            )
        }
        names = {
            item[1] for item in db.execute(
                "PRAGMA index_list(cognition_matrix_trace)"
            )
        }
    assert {"extensions_json", "context_json", "source_created_at"}.issubset(cols)
    assert "idx_cognition_matrix_trace_execution" in names


@pytest.mark.parametrize("limit", [0, -1, True, 1001, 1.5])
def test_matrix_execution_history_rejects_unbounded_limits(tmp_path, limit):
    path, _ = _fixture(tmp_path)
    store = MatrixTraceStore(path)
    with pytest.raises(ValueError, match="limit"):
        store.latest_with_execution(limit=limit)
    with pytest.raises(ValueError, match="limit"):
        store.latest_execution_scoped(
            session_id="s1", principal_id="principal:one",
            channel="desktop", limit=limit,
        )


def test_matrix_scoped_execution_history_filters_all_identity_axes(tmp_path):
    from sofia.cognition.matrix.model import CognitionExecutionTrace
    path, trace = _fixture(tmp_path)
    store = MatrixTraceStore(path)
    with_execution = replace(
        trace,
        cognition_execution=CognitionExecutionTrace(
            serial=1, actual_route="local", steps=(),
            fallback_count=0, verification_passes=0,
        ),
    )
    store.record(with_execution)
    assert store.latest_execution_scoped(
        session_id="s1", principal_id="principal:one", channel="desktop"
    ).envelope.message_id == trace.envelope.message_id
    for identity in (
        dict(session_id="other", principal_id="principal:one", channel="desktop"),
        dict(session_id="s1", principal_id="another", channel="desktop"),
        dict(session_id="s1", principal_id="principal:one", channel="discord"),
    ):
        assert store.latest_execution_scoped(**identity) is None
    assert store.latest_execution_scoped(
        session_id="s1", principal_id="principal:one", channel="desktop",
        limit=1,
    ) is not None
