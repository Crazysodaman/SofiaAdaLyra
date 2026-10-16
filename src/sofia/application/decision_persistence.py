"""Read-only canonical input/decision correlation for companion traces (CA-001).

This projection reads existing canonical owners. It never promotes a source,
claims a completed effect, creates a table, or grants principal access.
A Matrix row on its own is not proof of the originating user event.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import json
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
    assistant_reply_persisted: bool = False
    canonical_turn_settled: bool = False
    canonical_event_id: str | None = None
    assistant_message_id: str | None = None
    verified_audience_id: str | None = None
    response_evidence_refs: tuple[str, ...] = ()
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
    reply_ok = settled = False
    event_id = assistant_id = bound_audience = None
    user_created_at = None
    response_refs: tuple[str, ...] = ()
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
                    "'social_session_principal','canonical_conversation_turn')"
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
                            if message_ok:
                                user_created_at = created
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
                    if scope_ok:
                        bound_audience = binding[1]
            # Stable authenticated source events have a separate canonical
            # settlement owner. A generated response, Matrix record or model
            # assertion cannot stand in for that completed and source-bound
            # durable admission. Normal anonymous/local turns have no row.
            if (
                message_ok and decision_ok and scope_ok
                and "canonical_conversation_turn" in present
            ):
                turn_columns = {
                    item[1] for item in db.execute(
                        'PRAGMA table_info("canonical_conversation_turn")'
                    )
                }
                required = {
                    "event_id", "user_message_id", "assistant_message_id",
                    "owner_principal_id", "source_audience_id",
                    "source_channel", "source_session_id", "status",
                    "response_json", "settled_at",
                }
                if required <= turn_columns:
                    entry = db.execute(
                        "SELECT event_id,assistant_message_id,"
                        "owner_principal_id,source_audience_id,"
                        "source_channel,source_session_id,status,"
                        "response_json,settled_at "
                        "FROM canonical_conversation_turn WHERE user_message_id=?",
                        (envelope.message_id,),
                    ).fetchone()
                    if entry is not None and (
                        isinstance(entry[0], str) and bool(entry[0])
                        and isinstance(entry[1], str) and bool(entry[1])
                        and entry[2] == envelope.principal_id
                        and entry[3] == bound_audience
                        and entry[4] == envelope.channel
                        and entry[5] == envelope.session_id
                        and entry[6] == "completed"
                    ):
                        try:
                            when = datetime.fromisoformat(entry[8])
                            payload = json.loads(entry[7])
                        except (TypeError, ValueError):
                            pass
                        else:
                            if (
                                when.tzinfo is not None
                                and when.utcoffset() is not None
                                and isinstance(payload, dict)
                                and isinstance(payload.get("content"), str)
                            ):
                                raw_refs = payload.get("evidence_refs", [])
                                refs_valid = (
                                    isinstance(raw_refs, list)
                                    and len(raw_refs) <= 64
                                    and all(
                                        isinstance(item, str)
                                        and bool(item.strip())
                                        and len(item) <= 240
                                        for item in raw_refs
                                    )
                                    and len(set(raw_refs)) == len(raw_refs)
                                )
                                assistant = db.execute(
                                    "SELECT session_id,role,content,created_at "
                                    "FROM conversation_messages WHERE id=?",
                                    (entry[1],),
                                ).fetchone()
                                assistant_time_ok = False
                                if assistant is not None:
                                    try:
                                        assistant_created = datetime.fromisoformat(
                                            assistant[3],
                                        )
                                        assistant_time_ok = (
                                            user_created_at is not None
                                            and assistant_created.tzinfo is not None
                                            and assistant_created.utcoffset() is not None
                                            and user_created_at <= assistant_created
                                            and matrix_trace.created_at <= assistant_created
                                            and assistant_created <= when
                                        )
                                    except (ValueError, TypeError):
                                        pass
                                reply_ok = (
                                    assistant is not None
                                    and assistant[0] == envelope.session_id
                                    and assistant[1] == "assistant"
                                    and assistant[2] == payload["content"]
                                    and refs_valid
                                    and assistant_time_ok
                                )
                                if reply_ok:
                                    settled = True
                                    event_id, assistant_id = entry[0], entry[1]
                                    response_refs = tuple(raw_refs)
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
        assistant_reply_persisted=reply_ok,
        canonical_turn_settled=settled,
        canonical_event_id=event_id,
        assistant_message_id=assistant_id,
        verified_audience_id=(bound_audience if scope_ok else None),
        response_evidence_refs=response_refs,
    )
