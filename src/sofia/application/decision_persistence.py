"""Read-only canonical input/decision correlation for companion traces (CA-001).

This projection reads existing canonical owners. It never promotes a source,
claims a completed effect, creates a table, or grants principal access.
A Matrix row on its own is not proof of the originating user event.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3

from sofia.cognition.matrix.model import MatrixTrace
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


@dataclass(frozen=True, slots=True)
class CompanionTurnPersistence:
    schema_version: int
    message_id: str
    session_id: str
    user_message_persisted: bool
    matrix_decision_persisted: bool
    principal_scope_verified: bool
    same_turn_verified: bool
    limitation: str = (
        "Source/decision persistence is not model quality, consent, "
        "NEURO causal linkage, goal outcome, execution or delivery proof."
    )


def inspect_turn_persistence(
    state_path: Path | str, *, matrix_trace: MatrixTrace,
) -> CompanionTurnPersistence:
    """Compare source and decision keys in a single read-only SQLite snapshot.

    Verify role, session, time order, Matrix planning metadata and session
    principal/audience binding. No original content or private results are
    included in the projection. Missing/mismatched legacy data fails closed.
    """
    if not isinstance(matrix_trace, MatrixTrace):
        raise TypeError("matrix_trace must be MatrixTrace")
    envelope = matrix_trace.envelope
    message_ok = decision_ok = scope_ok = False
    guard = CanonicalSQLiteGuard(state_path)
    with closing(guard.connect(timeout=5, read_only=True)) as db:
        db.execute("BEGIN")
        try:
            required_tables = {
                "conversation_messages", "cognition_matrix_trace",
            }
            present = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name IN ('conversation_messages','cognition_matrix_trace',"
                    "'social_session_principal')"
                )
            }
            if required_tables <= present:
                columns = {
                    name: {row[1] for row in db.execute(
                        f'PRAGMA table_info("{name}")'
                    )}
                    for name in required_tables
                }
                if (
                    {"id", "session_id", "role", "created_at"} <=
                    columns["conversation_messages"]
                    and {"message_id", "session_id", "principal_id",
                         "channel", "intent", "history_policy",
                         "response_strategy", "created_at", "shadow"}
                    <= columns["cognition_matrix_trace"]
                ):
                    message = db.execute(
                        "SELECT session_id,role,created_at "
                        "FROM conversation_messages WHERE id=?",
                        (envelope.message_id,),
                    ).fetchone()
                    row = db.execute(
                        "SELECT session_id,principal_id,channel,intent,"
                        "history_policy,response_strategy,created_at,shadow "
                        "FROM cognition_matrix_trace WHERE message_id=?",
                        (envelope.message_id,),
                    ).fetchone()
                    if message is not None:
                        try:
                            created = datetime.fromisoformat(message[2])
                            message_ok = (
                                message[0] == envelope.session_id
                                and message[1] == "user"
                                and created.tzinfo is not None
                                and created.utcoffset() is not None
                                and created <= matrix_trace.created_at
                            )
                        except (TypeError, ValueError):
                            message_ok = False
                    if row is not None:
                        decision_ok = (
                            row[0] == envelope.session_id
                            and row[1] == (envelope.principal_id or "")
                            and row[2] == envelope.channel
                            and row[3] == matrix_trace.turn.intent.value
                            and row[4] == matrix_trace.turn.history_policy.value
                            and row[5] == matrix_trace.turn.response_strategy.value
                            and row[6] == matrix_trace.created_at.isoformat()
                            and row[7] == 0
                        )
            if (
                envelope.principal_id
                and "social_session_principal" in present
            ):
                required_columns = {"session_id", "principal_id", "audience_id"}
                actual_columns = {
                    r[1] for r in db.execute(
                        'PRAGMA table_info("social_session_principal")'
                    )
                }
                if required_columns <= actual_columns:
                    binding = db.execute(
                        "SELECT principal_id,audience_id "
                        "FROM social_session_principal WHERE session_id=?",
                        (envelope.session_id,),
                    ).fetchone()
                    scope_ok = (
                        binding is not None
                        and binding[0] == envelope.principal_id
                        and (
                            matrix_trace.privacy is None
                            or matrix_trace.privacy.audience_id == binding[1]
                        )
                    )
        finally:
            db.rollback()
    # A session principal is not proven by the claim in the Matrix row.
    # Only the separate SOCIAL canonical owner can authorize that binding.
    return CompanionTurnPersistence(
        schema_version=1,
        message_id=envelope.message_id,
        session_id=envelope.session_id,
        user_message_persisted=message_ok,
        matrix_decision_persisted=decision_ok,
        principal_scope_verified=scope_ok,
        same_turn_verified=message_ok and decision_ok and scope_ok,
    )
