"""Canonical model provenance linked to the exact persisted assistant message.

Router execution metadata is host observed, never a model's self-report.
A missing routing observation is recorded as UNKNOWN, not "model-free".
No prompt, conversation content, or private memory is duplicated here.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from sofia.cognition.matrix.model import CognitionExecutionTrace
from sofia.social.model import PrincipalContext
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


class ReplyModelOriginStore:
    """Durable per-reply evidence, erased when the original message is removed."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS cognition_reply_model_origin (
                    assistant_message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    principal_id TEXT,
                    audience_id TEXT,
                    origin_kind TEXT NOT NULL CHECK(origin_kind IN ('model','unknown')),
                    routing_serial INTEGER,
                    actual_route TEXT,
                    steps_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS cognition_reply_origin_session_idx
                    ON cognition_reply_model_origin(session_id, recorded_at);
                CREATE TRIGGER IF NOT EXISTS cognition_reply_model_origin_delete
                AFTER DELETE ON conversation_messages
                BEGIN
                    DELETE FROM cognition_reply_model_origin
                    WHERE assistant_message_id=OLD.id;
                END;
            """)

    def _connect(self):
        db = self._guard.connect(timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(
        self, *, assistant_message_id: str,
        session_id: str, execution: CognitionExecutionTrace | None,
        principal: PrincipalContext | None, at: datetime,
    ) -> None:
        for value in (assistant_message_id, session_id):
            if not isinstance(value, str) or not value.strip() or len(value)>200:
                raise ValueError("bounded canonical reply/session ID required")
        if execution is not None and not isinstance(execution, CognitionExecutionTrace):
            raise TypeError("host-observed routing trace required")
        if principal is not None and not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated principal scope required")
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("model origin time must be timezone-aware")
        steps = () if execution is None else execution.steps
        if len(steps) > 16:
            raise ValueError("bounded model execution step history required")
        if any(
            item.model is not None and (
                not isinstance(item.model, str) or len(item.model)>200
            )
            for item in steps
        ):
            raise ValueError("invalid observed model identity")
        document = {
            "assistant_message_id": assistant_message_id,
            "session_id": session_id,
            "principal_id": principal.principal_id if principal else None,
            "audience_id": principal.audience_id if principal else None,
            "origin_kind": "model" if steps else "unknown",
            "routing_serial": None if execution is None else execution.serial,
            "actual_route": None if execution is None else execution.actual_route,
            "steps_json": json.dumps(
                [asdict(step) for step in steps], sort_keys=True,
                separators=(",", ":"),
            ),
            "recorded_at": at.astimezone(timezone.utc).isoformat(),
        }
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT session_id,principal_id,audience_id,origin_kind,"
                "routing_serial,actual_route,steps_json "
                "FROM cognition_reply_model_origin WHERE assistant_message_id=?",
                (assistant_message_id,),
            ).fetchone()
            fields = (
                document["session_id"], document["principal_id"],
                document["audience_id"], document["origin_kind"],
                document["routing_serial"], document["actual_route"],
                document["steps_json"],
            )
            if existing is not None:
                if tuple(existing) != fields:
                    raise PermissionError(
                        "previously recorded reply/model origin cannot be rewritten"
                    )
                db.commit()
                return
            source = db.execute(
                "SELECT session_id,role FROM conversation_messages WHERE id=?",
                (assistant_message_id,),
            ).fetchone()
            if source != (session_id, "assistant"):
                raise LookupError("exact persisted assistant message is missing")
            db.execute(
                "INSERT INTO cognition_reply_model_origin VALUES"
                "(?,?,?,?,?,?,?,?,?)",
                (
                    assistant_message_id, session_id, *fields[1:],
                    document["recorded_at"],
                ),
            )
            db.commit()

    def inspect(
        self, *, assistant_message_id: str, principal: PrincipalContext,
    ) -> dict | None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated principal required to read origin")
        if not isinstance(assistant_message_id, str) or not assistant_message_id.strip():
            raise ValueError("exact assistant message ID required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT o.session_id,o.principal_id,o.audience_id,"
                "o.origin_kind,o.routing_serial,o.actual_route,o.steps_json,o.recorded_at "
                "FROM cognition_reply_model_origin o "
                "JOIN conversation_messages m ON m.id=o.assistant_message_id "
                "AND m.session_id=o.session_id AND m.role='assistant' "
                "WHERE o.assistant_message_id=?",
                (assistant_message_id,),
            ).fetchone()
        if (
            row is None or row[1] != principal.principal_id
            or row[2] != principal.audience_id
        ):
            return None
        return {
            "assistant_message_id": assistant_message_id,
            "session_id": row[0],
            "kind": row[3],
            "routing_serial": row[4],
            "actual_route": row[5],
            "steps": tuple(json.loads(row[6])),
            "recorded_at": row[7],
            "note": (
                "Host-observed cognitive execution metadata, not a model claim. "
                "An unknown origin is not proof of deterministic inference."
            ),
        }
