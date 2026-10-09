"""Durable, audience-scoped structured conversation focus."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .contracts import (
    ConversationFocus,
    FocusReference,
    FocusTopic,
    PendingAction,
    UnresolvedRequest,
)


class ConversationFocusConflict(RuntimeError):
    pass


def _scope_key(audience_id: str | None) -> str:
    return "unbound" if audience_id is None else f"audience:{audience_id}"


class SQLiteConversationFocusStore:
    """CAS persistence in canonical `sofia.db`, partitioned by session/audience."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS cognition_v2_conversation_focus (
                    session_id TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    audience_id TEXT,
                    revision INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, scope_key)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _empty(session_id: str, audience_id: str | None) -> ConversationFocus:
        return ConversationFocus(
            session_id=session_id,
            audience_id=audience_id,
            revision=0,
        )

    def load(
        self,
        *,
        session_id: str,
        audience_id: str | None,
    ) -> ConversationFocus:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT revision, payload_json
                FROM cognition_v2_conversation_focus
                WHERE session_id = ? AND scope_key = ?
                """,
                (session_id, _scope_key(audience_id)),
            ).fetchone()
        if row is None:
            return self._empty(session_id, audience_id)
        payload = json.loads(row["payload_json"])
        references = tuple(
            FocusReference(
                **{
                    **item,
                    "aliases": tuple(item["aliases"]),
                    "evidence_refs": tuple(item["evidence_refs"]),
                }
            )
            for item in payload["references"]
        )
        by_id = {item.reference_id: item for item in references}
        primary_id = payload.get("primary_reference_id")
        return ConversationFocus(
            session_id=session_id,
            audience_id=audience_id,
            revision=int(row["revision"]),
            primary_reference=(None if primary_id is None else by_id[primary_id]),
            references=references,
            topics=tuple(
                FocusTopic(
                    **{**item, "subject_ids": tuple(item["subject_ids"])}
                )
                for item in payload["topics"]
            ),
            unresolved_requests=tuple(
                UnresolvedRequest(
                    **{
                        **item,
                        "created_at": datetime.fromisoformat(item["created_at"]),
                        "predicate": item.get("predicate"),
                        "scope_id": item.get("scope_id"),
                    }
                )
                for item in payload["unresolved_requests"]
            ),
            pending_actions=tuple(
                PendingAction(
                    **{
                        **item,
                        "created_at": datetime.fromisoformat(item["created_at"]),
                    }
                )
                for item in payload["pending_actions"]
            ),
        )

    @staticmethod
    def _payload(focus: ConversationFocus) -> str:
        return json.dumps(
            {
                "primary_reference_id": (
                    None
                    if focus.primary_reference is None
                    else focus.primary_reference.reference_id
                ),
                "references": [
                    {
                        "reference_id": item.reference_id,
                        "subject_id": item.subject_id,
                        "kind": item.kind,
                        "source_turn_id": item.source_turn_id,
                        "confidence": item.confidence,
                        "aliases": list(item.aliases),
                        "evidence_refs": list(item.evidence_refs),
                    }
                    for item in focus.references
                ],
                "topics": [
                    {
                        "topic_id": item.topic_id,
                        "subject_ids": list(item.subject_ids),
                        "last_turn_id": item.last_turn_id,
                        "salience": item.salience,
                    }
                    for item in focus.topics
                ],
                "unresolved_requests": [
                    {
                        "request_id": item.request_id,
                        "source_turn_id": item.source_turn_id,
                        "subject_id": item.subject_id,
                        "request_kind": item.request_kind,
                        "created_at": item.created_at.isoformat(),
                        "predicate": item.predicate,
                        "scope_id": item.scope_id,
                    }
                    for item in focus.unresolved_requests
                ],
                "pending_actions": [
                    {
                        "action_id": item.action_id,
                        "source_turn_id": item.source_turn_id,
                        "subject_id": item.subject_id,
                        "action_kind": item.action_kind,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in focus.pending_actions
                ],
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    def commit(
        self,
        focus: ConversationFocus,
        *,
        expected_revision: int,
    ) -> ConversationFocus:
        if focus.revision != expected_revision + 1:
            raise ValueError("focus revision must increment exactly once")
        scope = _scope_key(focus.audience_id)
        payload = self._payload(focus)
        with closing(self._connect()) as db, db:
            if expected_revision == 0:
                try:
                    db.execute(
                        """
                        INSERT INTO cognition_v2_conversation_focus (
                            session_id, scope_key, audience_id, revision,
                            payload_json, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            focus.session_id,
                            scope,
                            focus.audience_id,
                            focus.revision,
                            payload,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ConversationFocusConflict(
                        "conversation focus was concurrently created"
                    ) from exc
            else:
                result = db.execute(
                    """
                    UPDATE cognition_v2_conversation_focus
                    SET revision = ?, payload_json = ?, updated_at = ?
                    WHERE session_id = ? AND scope_key = ? AND revision = ?
                    """,
                    (
                        focus.revision,
                        payload,
                        datetime.now(timezone.utc).isoformat(),
                        focus.session_id,
                        scope,
                        expected_revision,
                    ),
                )
                if result.rowcount != 1:
                    raise ConversationFocusConflict(
                        "conversation focus revision changed concurrently"
                    )
        return focus
