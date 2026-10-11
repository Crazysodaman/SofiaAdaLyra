"""Lifelong conversation identity over immutable, channel-bound source messages.

One MAIN per principal; optional PROJECT threads. Every linked message keeps
its original SocialSessionStore audience, source session and message ID.
A projection is not a message delivery and confers no tool/SAFE authority.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import sqlite3
from uuid import uuid4

from sofia.cognition.model import CognitiveResponse, CognitiveToolCall
from sofia.social.model import PrincipalContext
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


_NAME = re.compile(r"^[\w][\w .:/()-]{0,119}$", re.UNICODE)


@dataclass(frozen=True, slots=True)
class LifelongThread:
    thread_id: str
    owner_principal_id: str
    kind: str
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ThreadEvent:
    source_message_id: str
    source_session_id: str
    source_audience_id: str
    created_at: datetime
    visibility: str
    canonical_sequence: int | None = None
    turn_position: int | None = None


@dataclass(frozen=True, slots=True)
class HistoricalImportPreview:
    """Bounded same-audience source receipt, never a migration grant."""
    session_id: str
    owner_principal_id: str
    source_audience_id: str
    eligible_message_ids: tuple[str, ...]
    already_linked_ids: tuple[str, ...]
    original_timestamps: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HistoricalImportReceipt:
    review_ref: str
    source_session_id: str
    status: str
    added_ids: tuple[str, ...]
    pending_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LifelongMessage:
    """Original durable message with its actual source audience and link time."""

    thread_id: str
    message: ConversationMessage
    audience_id: str
    linked_at: datetime
    canonical_sequence: int | None = None
    turn_position: int | None = None


@dataclass(frozen=True, slots=True)
class CanonicalTurnAdmission:
    event_id: str
    canonical_sequence: int
    status: str
    user_message_id: str
    assistant_message_id: str
    response: CognitiveResponse | None = None


class CanonicalTurnConflict(RuntimeError):
    """A stable source event was replayed with different authenticated bytes."""


class CanonicalTurnPending(RuntimeError):
    """A matching canonical turn is still owned by an active runtime."""


class CanonicalTurnUncertain(RuntimeError):
    """A prior turn may have executed and must not be replayed automatically."""


class LifelongThreadStore:
    """Metadata/links in canonical sofia.db; never a second transcript store."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS lifelong_thread(
                    thread_id TEXT PRIMARY KEY,
                    owner_principal_id TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('main','project')),
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(owner_principal_id,kind,name)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS lifelong_one_main
                    ON lifelong_thread(owner_principal_id) WHERE kind='main';
                CREATE TABLE IF NOT EXISTS lifelong_thread_event(
                    thread_id TEXT NOT NULL,
                    source_message_id TEXT NOT NULL,
                    source_session_id TEXT NOT NULL,
                    source_audience_id TEXT NOT NULL,
                    visibility TEXT NOT NULL
                        CHECK(visibility IN ('source_audience','reviewed_owner')),
                    linked_at TEXT NOT NULL,
                    PRIMARY KEY(thread_id,source_message_id),
                    FOREIGN KEY(thread_id) REFERENCES lifelong_thread(thread_id)
                );
                CREATE INDEX IF NOT EXISTS lifelong_thread_event_order
                    ON lifelong_thread_event(thread_id,linked_at,source_message_id);
                CREATE TABLE IF NOT EXISTS canonical_conversation_turn (
                    event_id TEXT PRIMARY KEY,
                    owner_principal_id TEXT NOT NULL,
                    source_audience_id TEXT NOT NULL,
                    source_audience_kind TEXT NOT NULL,
                    source_channel TEXT NOT NULL,
                    source_session_id TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    canonical_sequence INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'processing','completed','interrupted','uncertain'
                    )),
                    runtime_id TEXT NOT NULL,
                    user_message_id TEXT NOT NULL UNIQUE,
                    assistant_message_id TEXT NOT NULL UNIQUE,
                    response_json TEXT,
                    received_at TEXT NOT NULL,
                    settled_at TEXT,
                    UNIQUE(owner_principal_id,canonical_sequence)
                );
                CREATE INDEX IF NOT EXISTS canonical_turn_scope
                    ON canonical_conversation_turn(
                        owner_principal_id,source_audience_id,
                        canonical_sequence
                    );
                CREATE TABLE IF NOT EXISTS lifelong_historical_import (
                    review_ref TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    source_session_id TEXT NOT NULL,
                    owner_principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'committed','partially_rolled_back','rolled_back','rejected'
                    )),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES lifelong_thread(thread_id)
                );
                CREATE TABLE IF NOT EXISTS lifelong_historical_import_added (
                    review_ref TEXT NOT NULL,
                    source_message_id TEXT NOT NULL,
                    removed_at TEXT,
                    PRIMARY KEY(review_ref,source_message_id),
                    FOREIGN KEY(review_ref)
                        REFERENCES lifelong_historical_import(review_ref)
                );
                """
            )
            columns = {
                row[1] for row in db.execute(
                    "PRAGMA table_info(lifelong_thread_event)"
                )
            }
            if "canonical_sequence" not in columns:
                db.execute(
                    "ALTER TABLE lifelong_thread_event "
                    "ADD COLUMN canonical_sequence INTEGER"
                )
            if "turn_position" not in columns:
                db.execute(
                    "ALTER TABLE lifelong_thread_event "
                    "ADD COLUMN turn_position INTEGER"
                )
            db.execute(
                """CREATE INDEX IF NOT EXISTS lifelong_thread_canonical_order
                ON lifelong_thread_event(
                    thread_id,canonical_sequence,turn_position,source_message_id
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        # A lost Main database must never be resurrected by a later page
        # request or independent device after canonical state relocation.
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _turn_response(document: str | None) -> CognitiveResponse | None:
        if document is None:
            return None
        value = json.loads(document)
        return CognitiveResponse(
            content=value["content"],
            tool_calls=tuple(CognitiveToolCall(
                item["name"], item["arguments"], item.get("call_id"),
            ) for item in value.get("tool_calls", ())),
            evidence_refs=tuple(value.get("evidence_refs", ())),
        )

    @classmethod
    def _turn_admission(cls, row: sqlite3.Row) -> CanonicalTurnAdmission:
        return CanonicalTurnAdmission(
            row["event_id"], int(row["canonical_sequence"]), row["status"],
            row["user_message_id"], row["assistant_message_id"],
            cls._turn_response(row["response_json"]),
        )

    def recover_interrupted_turns(self, *, runtime_id: str, now: datetime) -> int:
        """Fence unfinished claims from earlier application lifetimes."""
        if not isinstance(runtime_id, str) or not runtime_id.strip():
            raise ValueError("runtime_id required")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("recovery time must be timezone-aware")
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """UPDATE canonical_conversation_turn
                SET status='interrupted',settled_at=?
                WHERE status='processing' AND runtime_id<>?""",
                (now.astimezone(timezone.utc).isoformat(), runtime_id),
            )
        return changed.rowcount

    def admit_turn(
        self, *, event_id: str, principal: PrincipalContext,
        session_id: str, channel: str, content: str,
        runtime_id: str, now: datetime,
    ) -> CanonicalTurnAdmission:
        """Durably order and deduplicate one authenticated source submission."""
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        values = (event_id, session_id, channel, runtime_id)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("turn identity fields must be nonempty strings")
        if len(event_id) > 256 or len(session_id) > 256 or len(channel) > 64:
            raise ValueError("turn identity fields exceed bounds")
        if not isinstance(content, str) or not content.strip() or len(content) > 12000:
            raise ValueError("turn content must be bounded nonempty text")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("turn receipt time must be timezone-aware")
        digest = sha256(json.dumps((
            principal.principal_id, principal.audience_id,
            principal.audience_kind.value, session_id, channel, content,
        ), ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            binding = db.execute(
                """SELECT principal_id,audience_id,audience_kind
                FROM social_session_principal WHERE session_id=?""",
                (session_id,),
            ).fetchone()
            if binding is None or tuple(binding) != (
                principal.principal_id, principal.audience_id,
                principal.audience_kind.value,
            ):
                raise PermissionError("turn session is not bound to authenticated source")
            existing = db.execute(
                "SELECT * FROM canonical_conversation_turn WHERE event_id=?",
                (event_id,),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != digest:
                    raise CanonicalTurnConflict(
                        "source event ID was reused across content or authority scope"
                    )
                admission = self._turn_admission(existing)
                if admission.status == "processing":
                    raise CanonicalTurnPending("canonical turn is already processing")
                if admission.status in {"interrupted", "uncertain"}:
                    raise CanonicalTurnUncertain(
                        "prior canonical turn outcome is uncertain; replay denied"
                    )
                return admission
            sequence = int(db.execute(
                """SELECT COALESCE(MAX(canonical_sequence),0)+1
                FROM canonical_conversation_turn WHERE owner_principal_id=?""",
                (principal.principal_id,),
            ).fetchone()[0])
            user_id = f"message:user:{uuid4().hex}"
            assistant_id = f"message:assistant:{uuid4().hex}"
            stamp = now.astimezone(timezone.utc).isoformat()
            db.execute(
                """INSERT INTO canonical_conversation_turn(
                event_id,owner_principal_id,source_audience_id,
                source_audience_kind,source_channel,source_session_id,
                request_digest,canonical_sequence,status,runtime_id,
                user_message_id,assistant_message_id,response_json,
                received_at,settled_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                (
                    event_id, principal.principal_id, principal.audience_id,
                    principal.audience_kind.value, channel, session_id,
                    digest, sequence, "processing", runtime_id,
                    user_id, assistant_id, None, stamp,
                ),
            )
            row = db.execute(
                "SELECT * FROM canonical_conversation_turn WHERE event_id=?",
                (event_id,),
            ).fetchone()
            return self._turn_admission(row)

    def settle_turn(
        self, *, admission: CanonicalTurnAdmission,
        principal: PrincipalContext, response: CognitiveResponse,
        now: datetime,
    ) -> None:
        """Commit a response only when both exact canonical messages exist."""
        document = json.dumps({
            "content": response.content,
            "tool_calls": [
                {"name": item.name, "arguments": item.arguments,
                 "call_id": item.call_id}
                for item in response.tool_calls
            ],
            "evidence_refs": response.evidence_refs,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(document.encode("utf-8")) > 256 * 1024:
            raise ValueError("canonical turn response exceeds durable bound")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            turn = db.execute(
                "SELECT * FROM canonical_conversation_turn WHERE event_id=?",
                (admission.event_id,),
            ).fetchone()
            if turn is None or (
                turn["status"] != "processing"
                or int(turn["canonical_sequence"]) != admission.canonical_sequence
                or turn["user_message_id"] != admission.user_message_id
                or turn["assistant_message_id"] != admission.assistant_message_id
            ):
                raise CanonicalTurnUncertain(
                    "canonical turn admission no longer matches its durable claim"
                )
            source_session = turn["source_session_id"]
            messages = db.execute(
                """SELECT id,role,content FROM conversation_messages
                WHERE session_id=? AND id IN (?,?)""",
                (source_session, admission.user_message_id,
                 admission.assistant_message_id),
            ).fetchall()
            by_id = {row["id"]: row for row in messages}
            if (
                by_id.get(admission.user_message_id) is None
                or by_id[admission.user_message_id]["role"] != "user"
                or by_id.get(admission.assistant_message_id) is None
                or by_id[admission.assistant_message_id]["role"] != "assistant"
                or by_id[admission.assistant_message_id]["content"] != response.content
            ):
                raise CanonicalTurnUncertain(
                    "canonical source/response messages are missing or inconsistent"
                )
            binding = db.execute(
                """SELECT principal_id,audience_id,audience_kind
                FROM social_session_principal WHERE session_id=?""",
                (source_session,),
            ).fetchone()
            if binding is None or tuple(binding) != (
                principal.principal_id, principal.audience_id,
                principal.audience_kind.value,
            ):
                raise CanonicalTurnUncertain(
                    "source audience changed before canonical settlement"
                )
            thread = db.execute(
                """SELECT thread_id FROM lifelong_thread
                WHERE owner_principal_id=? AND kind='main'""",
                (principal.principal_id,),
            ).fetchone()
            if thread is None:
                thread_id = f"thread:{uuid4().hex}"
                db.execute(
                    "INSERT INTO lifelong_thread VALUES(?,?,?,?,?)",
                    (
                        thread_id, principal.principal_id, "main", "Main",
                        now.astimezone(timezone.utc).isoformat(),
                    ),
                )
            else:
                thread_id = thread["thread_id"]
            for message_id, position in (
                (admission.user_message_id, 0),
                (admission.assistant_message_id, 1),
            ):
                existing_link = db.execute(
                    """SELECT source_session_id,source_audience_id,visibility,
                    canonical_sequence,turn_position
                    FROM lifelong_thread_event
                    WHERE thread_id=? AND source_message_id=?""",
                    (thread_id, message_id),
                ).fetchone()
                expected_link = (
                    source_session, principal.audience_id, "source_audience",
                    admission.canonical_sequence, position,
                )
                if existing_link is None:
                    db.execute(
                        """INSERT INTO lifelong_thread_event(
                        thread_id,source_message_id,source_session_id,
                        source_audience_id,visibility,linked_at,
                        canonical_sequence,turn_position
                        ) VALUES(?,?,?,?,?,?,?,?)""",
                        (
                            thread_id, message_id, source_session,
                            principal.audience_id, "source_audience",
                            now.astimezone(timezone.utc).isoformat(),
                            admission.canonical_sequence, position,
                        ),
                    )
                elif tuple(existing_link) != expected_link:
                    raise CanonicalTurnUncertain(
                        "Main source link conflicts with canonical turn order"
                    )
            changed = db.execute(
                """UPDATE canonical_conversation_turn
                SET status='completed',response_json=?,settled_at=?
                WHERE event_id=? AND owner_principal_id=?
                AND source_audience_id=? AND source_audience_kind=?
                AND status='processing'
                AND user_message_id=? AND assistant_message_id=?""",
                (
                    document, now.astimezone(timezone.utc).isoformat(),
                    admission.event_id, principal.principal_id,
                    principal.audience_id, principal.audience_kind.value,
                    admission.user_message_id, admission.assistant_message_id,
                ),
            )
            if changed.rowcount != 1:
                raise CanonicalTurnUncertain("canonical turn changed before settlement")

    def mark_turn_uncertain(
        self, *, admission: CanonicalTurnAdmission,
        interrupted: bool, now: datetime,
    ) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """UPDATE canonical_conversation_turn SET status=?,settled_at=?
                WHERE event_id=? AND status='processing'""",
                (
                    "interrupted" if interrupted else "uncertain",
                    now.astimezone(timezone.utc).isoformat(), admission.event_id,
                ),
            )

    @staticmethod
    def _decode(row: sqlite3.Row) -> LifelongThread:
        return LifelongThread(
            thread_id=row["thread_id"],
            owner_principal_id=row["owner_principal_id"],
            kind=row["kind"], name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def get_or_create(
        self, *, owner: PrincipalContext,
        kind: str = "main", name: str = "Main",
    ) -> LifelongThread:
        if not isinstance(owner, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if kind not in {"main", "project"}:
            raise ValueError("unsupported thread kind")
        if kind == "main":
            name = "Main"
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError("bounded thread name required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if kind == "main":
                row = db.execute(
                    "SELECT * FROM lifelong_thread WHERE owner_principal_id=? AND kind='main'",
                    (owner.principal_id,),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT * FROM lifelong_thread WHERE owner_principal_id=? "
                    "AND kind='project' AND name=?",
                    (owner.principal_id, name),
                ).fetchone()
            if row is not None:
                return self._decode(row)
            identifier = f"thread:{uuid4().hex}"
            when = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT INTO lifelong_thread VALUES(?,?,?,?,?)",
                (identifier, owner.principal_id, kind, name, when),
            )
            return LifelongThread(identifier, owner.principal_id, kind, name,
                                  datetime.fromisoformat(when))

    def thread_for(
        self, *, owner: PrincipalContext, thread_id: str,
    ) -> LifelongThread | None:
        """Resolve one canonical thread header for its authenticated owner.

        This is an ownership lookup only, NOT permission to render private
        project titles to a different audience. Callers must also check
        original source-event visibility before exposing its name/content.
        """
        if not isinstance(owner, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if not isinstance(thread_id, str) or not 8 <= len(thread_id) <= 128:
            raise ValueError("bounded thread ID required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM lifelong_thread "
                "WHERE thread_id=? AND owner_principal_id=?",
                (thread_id, owner.principal_id),
            ).fetchone()
        return None if row is None else self._decode(row)

    def list_threads(
        self, *, owner: PrincipalContext, limit: int = 30,
    ) -> tuple[LifelongThread, ...]:
        """Enumerate only canonical thread headers owned by authenticated user."""
        if not isinstance(owner, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded thread listing required")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM lifelong_thread WHERE owner_principal_id=? "
                "ORDER BY CASE kind WHEN 'main' THEN 0 ELSE 1 END,"
                "created_at DESC,thread_id LIMIT ?",
                (owner.principal_id, limit),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def list_visible_threads(
        self, *, owner: PrincipalContext, limit: int = 30,
    ) -> tuple[LifelongThread, ...]:
        """Page headers only AFTER original-audience visibility admission.

        Source-free private project names must never consume the result
        limit or surface to another transport. The SQL EXISTS guard checks
        the original message and its CURRENT authenticated session binding,
        not merely the shared owner ID or an old thread index.
        """
        if not isinstance(owner, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded visible thread listing required")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT t.* FROM lifelong_thread AS t "
                "WHERE t.owner_principal_id=? AND ("
                "t.kind='main' OR (t.kind='project' AND EXISTS ("
                "SELECT 1 FROM lifelong_thread_event AS e "
                "JOIN conversation_messages AS m "
                "ON m.id=e.source_message_id "
                "AND m.session_id=e.source_session_id "
                "JOIN social_session_principal AS s "
                "ON s.session_id=m.session_id "
                "WHERE e.thread_id=t.thread_id "
                "AND e.visibility='source_audience' "
                "AND e.source_audience_id=? "
                "AND s.principal_id=? AND s.audience_id=? "
                "AND s.audience_kind=?"
                "))) "
                "ORDER BY CASE t.kind WHEN 'main' THEN 0 ELSE 1 END,"
                "t.created_at DESC,t.thread_id LIMIT ?",
                (
                    owner.principal_id, owner.audience_id,
                    owner.principal_id, owner.audience_id,
                    owner.audience_kind.value, limit,
                ),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def link_message(
        self, *, thread_id: str, source_message_id: str,
        principal: PrincipalContext,
        visibility: str = "source_audience",
    ) -> None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated principal required")
        if visibility != "source_audience":
            # Cross-channel visibility requires independent reviewed opt-in
            # with retention/outbound disclosure; never infer it from owner ID.
            raise PermissionError("cross-channel message projection is not yet authorized")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            thread = db.execute(
                "SELECT owner_principal_id FROM lifelong_thread WHERE thread_id=?",
                (thread_id,),
            ).fetchone()
            if thread is None or thread["owner_principal_id"] != principal.principal_id:
                raise PermissionError("thread does not belong to authenticated principal")
            row = db.execute(
                "SELECT m.session_id,s.principal_id,s.audience_id,s.audience_kind "
                "FROM conversation_messages m JOIN social_session_principal s "
                "ON s.session_id=m.session_id WHERE m.id=?",
                (source_message_id,),
            ).fetchone()
            if row is None:
                raise LookupError("original message or verified audience binding missing")
            if (
                row["principal_id"] != principal.principal_id
                or row["audience_id"] != principal.audience_id
                or row["audience_kind"] != principal.audience_kind.value
            ):
                raise PermissionError("cross-principal/audience message linking denied")
            existing = db.execute(
                "SELECT source_session_id,source_audience_id,visibility "
                "FROM lifelong_thread_event WHERE thread_id=? AND source_message_id=?",
                (thread_id, source_message_id),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != (
                    row["session_id"], row["audience_id"], visibility
                ):
                    raise PermissionError("conflicting thread event replay")
                return
            ordered = db.execute(
                """SELECT canonical_sequence,user_message_id,assistant_message_id
                FROM canonical_conversation_turn
                WHERE user_message_id=? OR assistant_message_id=?""",
                (source_message_id, source_message_id),
            ).fetchone()
            canonical_sequence = None if ordered is None else int(
                ordered["canonical_sequence"]
            )
            turn_position = (
                None if ordered is None else
                0 if ordered["user_message_id"] == source_message_id else 1
            )
            db.execute(
                """INSERT INTO lifelong_thread_event(
                thread_id,source_message_id,source_session_id,
                source_audience_id,visibility,linked_at,
                canonical_sequence,turn_position
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (thread_id, source_message_id, row["session_id"],
                 row["audience_id"], visibility,
                 datetime.now(timezone.utc).isoformat(),
                 canonical_sequence, turn_position),
            )

    def preview_historical_import(
        self, *, principal: PrincipalContext, session_id: str,
        limit: int = 128,
    ) -> HistoricalImportPreview:
        """Preview at most one bounded source batch without changing history.

        Selection is restricted to the CURRENT original session binding.
        A principal ID match alone cannot import another transport audience.
        An operator can review a longer session in additional explicit
        batches rather than silently importing years of private content.
        """
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated owner principal required")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("exact source session ID required")
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError("bounded source import preview limit required")
        with closing(self._connect()) as db:
            source = db.execute(
                "SELECT principal_id,audience_id,audience_kind "
                "FROM social_session_principal WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if source is None or tuple(source) != (
                principal.principal_id, principal.audience_id,
                principal.audience_kind.value,
            ):
                raise PermissionError("source session audience is not authenticated")
            rows = db.execute(
                "SELECT m.id,m.created_at, "
                "EXISTS(SELECT 1 FROM lifelong_thread_event AS e "
                "JOIN lifelong_thread AS t ON t.thread_id=e.thread_id "
                "WHERE e.source_message_id=m.id "
                "AND t.kind='main' AND t.owner_principal_id=? "
                "AND e.source_session_id=m.session_id "
                "AND e.source_audience_id=? "
                "AND e.visibility='source_audience') AS already "
                "FROM conversation_messages AS m "
                "WHERE m.session_id=? ORDER BY m.created_at,m.id LIMIT ?",
                (principal.principal_id, principal.audience_id,
                 session_id, limit),
            ).fetchall()
        return HistoricalImportPreview(
            session_id=session_id,
            owner_principal_id=principal.principal_id,
            source_audience_id=principal.audience_id,
            eligible_message_ids=tuple(row["id"] for row in rows),
            already_linked_ids=tuple(row["id"] for row in rows if row["already"]),
            original_timestamps=tuple(row["created_at"] for row in rows),
        )

    def apply_historical_import(
        self, *, principal: PrincipalContext, session_id: str,
        message_ids: tuple[str, ...], review_ref: str, reject: bool,
        independently_verify_operator_review,
    ) -> HistoricalImportReceipt:
        """Operator-reviewed reversible Main links, never source rebindings.

        A trusted host controller verifies the exact review digest and
        operator approval independently of model text. Original rows keep
        their session, privacy and chronological provenance unchanged.
        """
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated owner principal required")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("source session required")
        if (
            not isinstance(message_ids, tuple) or not 1 <= len(message_ids) <= 128
            or len(set(message_ids)) != len(message_ids)
            or any(
                not isinstance(x, str) or not x.strip() or len(x) > 256
                for x in message_ids
            )
        ):
            raise ValueError("1..128 distinct bounded source message IDs required")
        if not isinstance(review_ref, str) or not 8 <= len(review_ref) <= 256:
            raise ValueError("bounded operator review reference required")
        if type(reject) is not bool:
            raise TypeError("reject decision must be explicit")
        digest = sha256(json.dumps(
            (principal.principal_id, principal.audience_id,
             principal.audience_kind.value, session_id, message_ids, reject),
            separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        if not callable(independently_verify_operator_review) or (
            independently_verify_operator_review(review_ref, digest) is not True
        ):
            raise PermissionError("independent operator review denied import")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            original = db.execute(
                "SELECT principal_id,audience_id,audience_kind "
                "FROM social_session_principal WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if original is None or tuple(original) != (
                principal.principal_id, principal.audience_id,
                principal.audience_kind.value,
            ):
                raise PermissionError("original source audience changed since review")
            existing = db.execute(
                "SELECT request_digest,status,source_session_id "
                "FROM lifelong_historical_import WHERE review_ref=?",
                (review_ref,),
            ).fetchone()
            if existing is not None:
                if existing["request_digest"] != digest or (
                    existing["source_session_id"] != session_id
                ):
                    raise PermissionError("review reference reused for different sources")
                return self._historical_receipt(db, review_ref)
            marker = ",".join("?" for _ in message_ids)
            rows = db.execute(
                "SELECT id FROM conversation_messages "
                "WHERE session_id=? AND id IN (" + marker + ")",
                (session_id, *message_ids),
            ).fetchall()
            if len(rows) != len(message_ids):
                raise LookupError("requested message not in exact reviewed source")
            thread = db.execute(
                "SELECT thread_id FROM lifelong_thread "
                "WHERE owner_principal_id=? AND kind='main'",
                (principal.principal_id,),
            ).fetchone()
            if thread is None:
                thread_id = f"thread:{uuid4().hex}"
                db.execute(
                    "INSERT INTO lifelong_thread VALUES(?,?,?,?,?)",
                    (thread_id, principal.principal_id, "main", "Main",
                     datetime.now(timezone.utc).isoformat()),
                )
            else:
                thread_id = thread["thread_id"]
            stamp = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT INTO lifelong_historical_import VALUES(?,?,?,?,?,?,?,?)",
                (review_ref, thread_id, session_id, principal.principal_id,
                 principal.audience_id, digest,
                 "rejected" if reject else "committed", stamp),
            )
            if not reject:
                for identifier in message_ids:
                    already = db.execute(
                        "SELECT source_session_id,source_audience_id,visibility "
                        "FROM lifelong_thread_event "
                        "WHERE thread_id=? AND source_message_id=?",
                        (thread_id, identifier),
                    ).fetchone()
                    if already is not None:
                        if tuple(already) != (
                            session_id, principal.audience_id, "source_audience"
                        ):
                            raise PermissionError("existing source link conflicts with review")
                        continue
                    db.execute(
                        """INSERT INTO lifelong_thread_event(
                        thread_id,source_message_id,source_session_id,
                        source_audience_id,visibility,linked_at,
                        canonical_sequence,turn_position
                        ) VALUES(?,?,?,?,?,?,NULL,NULL)""",
                        (thread_id, identifier, session_id,
                         principal.audience_id, "source_audience", stamp),
                    )
                    db.execute(
                        "INSERT INTO lifelong_historical_import_added VALUES(?,?,NULL)",
                        (review_ref, identifier),
                    )
            return self._historical_receipt(db, review_ref)

    @staticmethod
    def _historical_receipt(db: sqlite3.Connection, review_ref: str) -> HistoricalImportReceipt:
        row = db.execute(
            "SELECT source_session_id,status "
            "FROM lifelong_historical_import WHERE review_ref=?",
            (review_ref,),
        ).fetchone()
        if row is None:
            raise LookupError("historical import decision absent")
        added = db.execute(
            "SELECT source_message_id,removed_at "
            "FROM lifelong_historical_import_added WHERE review_ref=? "
            "ORDER BY source_message_id", (review_ref,),
        ).fetchall()
        return HistoricalImportReceipt(
            review_ref=review_ref, source_session_id=row["source_session_id"],
            status=row["status"],
            added_ids=tuple(r["source_message_id"] for r in added),
            pending_ids=tuple(
                r["source_message_id"] for r in added
                if r["removed_at"] is None
            ),
        )

    def rollback_historical_import(
        self, *, principal: PrincipalContext, review_ref: str,
        message_ids: tuple[str, ...], independently_verify_operator_review,
    ) -> HistoricalImportReceipt:
        """Undo only links introduced by one authenticated historical import."""
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated owner required")
        if not isinstance(review_ref, str) or not 8 <= len(review_ref) <= 256:
            raise ValueError("operator review reference required")
        if (
            not isinstance(message_ids, tuple) or not 1 <= len(message_ids) <= 128
            or len(set(message_ids)) != len(message_ids)
            or any(not isinstance(v, str) or not v.strip() for v in message_ids)
        ):
            raise ValueError("bounded explicit rollback item IDs required")
        digest = sha256(json.dumps(
            ("rollback", principal.principal_id, principal.audience_id,
             review_ref, message_ids), separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        if not callable(independently_verify_operator_review) or (
            independently_verify_operator_review(review_ref, digest) is not True
        ):
            raise PermissionError("independent operator rollback review denied")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            owner = db.execute(
                "SELECT thread_id,owner_principal_id,audience_id,"
                "source_session_id,status "
                "FROM lifelong_historical_import WHERE review_ref=?",
                (review_ref,),
            ).fetchone()
            if owner is None:
                raise LookupError("review reference does not exist")
            if (owner["owner_principal_id"],owner["audience_id"]) != (
                principal.principal_id, principal.audience_id,
            ):
                raise PermissionError("rollback is not owned by this exact audience")
            if owner["status"] == "rejected":
                raise PermissionError("rejected import created no links")
            for identifier in message_ids:
                record = db.execute(
                    "SELECT removed_at FROM lifelong_historical_import_added "
                    "WHERE review_ref=? AND source_message_id=?",
                    (review_ref, identifier),
                ).fetchone()
                if record is None:
                    raise PermissionError("cannot remove preexisting or foreign Main links")
                if record["removed_at"] is not None:
                    continue
                db.execute(
                    "DELETE FROM lifelong_thread_event "
                    "WHERE thread_id=? AND source_message_id=? "
                    "AND source_session_id=? AND source_audience_id=? "
                    "AND visibility='source_audience'",
                    (owner["thread_id"], identifier,
                     owner["source_session_id"], principal.audience_id),
                )
                db.execute(
                    "UPDATE lifelong_historical_import_added SET removed_at=? "
                    "WHERE review_ref=? AND source_message_id=? AND removed_at IS NULL",
                    (datetime.now(timezone.utc).isoformat(), review_ref, identifier),
                )
            remaining = db.execute(
                "SELECT 1 FROM lifelong_historical_import_added "
                "WHERE review_ref=? AND removed_at IS NULL LIMIT 1",
                (review_ref,),
            ).fetchone()
            db.execute(
                "UPDATE lifelong_historical_import SET status=? "
                "WHERE review_ref=?",
                ("partially_rolled_back" if remaining else "rolled_back",
                 review_ref),
            )
            return self._historical_receipt(db, review_ref)

    def visible_events(
        self, *, thread_id: str, principal: PrincipalContext,
        limit: int = 100,
    ) -> tuple[ThreadEvent, ...]:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated principal required")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("bounded event limit required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT owner_principal_id FROM lifelong_thread WHERE thread_id=?",
                (thread_id,),
            ).fetchone()
            if row is None or row["owner_principal_id"] != principal.principal_id:
                raise PermissionError("thread not accessible to caller")
            # Re-validate the current source session binding on every read.
            # An index entry is not a grant: a deleted source, changed binding,
            # different audience kind or another principal must not surface.
            rows = db.execute(
                "SELECT e.source_message_id,e.source_session_id,"
                "e.source_audience_id,e.visibility,e.linked_at,"
                "e.canonical_sequence,e.turn_position "
                "FROM lifelong_thread_event AS e "
                "JOIN conversation_messages AS m "
                "ON m.id=e.source_message_id AND m.session_id=e.source_session_id "
                "JOIN social_session_principal AS s ON s.session_id=m.session_id "
                "WHERE e.thread_id=? AND e.source_audience_id=? "
                "AND e.visibility='source_audience' "
                "AND s.principal_id=? AND s.audience_id=? "
                "AND s.audience_kind=? "
                "ORDER BY CASE WHEN e.canonical_sequence IS NULL THEN 0 ELSE 1 END DESC,"
                "e.canonical_sequence DESC,e.turn_position DESC,"
                "e.linked_at DESC,e.source_message_id DESC LIMIT ?",
                (thread_id, principal.audience_id, principal.principal_id,
                 principal.audience_id, principal.audience_kind.value, limit),
            ).fetchall()
        return tuple(
            ThreadEvent(r["source_message_id"], r["source_session_id"],
                        r["source_audience_id"], datetime.fromisoformat(r["linked_at"]),
                        r["visibility"], r["canonical_sequence"], r["turn_position"])
            for r in reversed(rows)
        )

    def visible_messages(
        self, *, thread_id: str, principal: PrincipalContext,
        limit: int = 100,
    ) -> tuple[ConversationMessage, ...]:
        """Resolve original source bytes, never a duplicated Main transcript.

        Restricts principal, audience, audience KIND, original session
        binding, source-message presence and thread ownership at read time.
        This is an authenticated read API, not outbound permission to relay
        messages across Discord/desktop/mobile audiences.
        """
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated principal required")
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise ValueError("thread_id required")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("bounded source message limit required")
        with closing(self._connect()) as db:
            thread = db.execute(
                "SELECT owner_principal_id FROM lifelong_thread WHERE thread_id=?",
                (thread_id,),
            ).fetchone()
            if thread is None or thread["owner_principal_id"] != principal.principal_id:
                raise PermissionError("thread not accessible to authenticated principal")
            rows = db.execute(
                "SELECT m.id,m.session_id,m.role,m.content,m.created_at "
                "FROM lifelong_thread_event AS e "
                "JOIN conversation_messages AS m ON m.id=e.source_message_id "
                "AND m.session_id=e.source_session_id "
                "JOIN social_session_principal AS s ON s.session_id=m.session_id "
                "WHERE e.thread_id=? AND e.visibility='source_audience' "
                "AND e.source_audience_id=? AND s.principal_id=? "
                "AND s.audience_id=? AND s.audience_kind=? "
                "ORDER BY CASE WHEN e.canonical_sequence IS NULL THEN 0 ELSE 1 END DESC,"
                "e.canonical_sequence DESC,e.turn_position DESC,"
                "m.created_at DESC,m.id DESC LIMIT ?",
                (thread_id, principal.audience_id, principal.principal_id,
                 principal.audience_id, principal.audience_kind.value, limit),
            ).fetchall()
        return tuple(
            ConversationMessage(
                id=row["id"], session_id=row["session_id"],
                role=ConversationRole(row["role"]), content=row["content"],
                created_at=datetime.fromisoformat(row["created_at"]),
            ) for row in reversed(rows)
        )

    def visible_message_page(
        self, *, thread_id: str, principal: PrincipalContext,
        before: tuple[datetime, str] | tuple[int, int, str] | None = None,
        limit: int = 50,
    ) -> tuple[LifelongMessage, ...]:
        """Page original messages in a single principal AND audience scope.

        Newest-first SQL with a keyset seek avoids OFFSET scans; the returned
        page is chronological for display. Every row still joins its original
        conversation session and CURRENT SocialSessionStore binding, so no
        other audience becomes visible simply by sharing the same Main thread.
        Caller must authenticate PrincipalContext externally. This returns no
        LLM context and does not grant a tool or cross-channel disclosure.
        """
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise ValueError("thread ID required")
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("page limit must be between 1 and 200")
        legacy_cursor = (
            isinstance(before, tuple) and len(before) == 2
            and isinstance(before[0], datetime)
            and before[0].tzinfo is not None
            and before[0].utcoffset() is not None
            and isinstance(before[1], str) and bool(before[1].strip())
        )
        canonical_cursor = (
            isinstance(before, tuple) and len(before) == 3
            and type(before[0]) is int and before[0] > 0
            and type(before[1]) is int and before[1] in {0, 1}
            and isinstance(before[2], str) and bool(before[2].strip())
        )
        if before is not None and not (legacy_cursor or canonical_cursor):
            raise ValueError("before cursor requires canonical order or legacy timestamp")
        filters = (
            "e.thread_id=? AND e.source_audience_id=? "
            "AND e.visibility='source_audience' "
            "AND s.principal_id=? AND s.audience_id=? "
            "AND s.audience_kind=?"
        )
        args: list[object] = [
            thread_id, principal.audience_id, principal.principal_id,
            principal.audience_id, principal.audience_kind.value,
        ]
        if canonical_cursor:
            filters += (
                " AND (e.canonical_sequence IS NULL "
                "OR e.canonical_sequence < ? "
                "OR (e.canonical_sequence = ? AND e.turn_position < ?) "
                "OR (e.canonical_sequence = ? AND e.turn_position = ? "
                "AND e.source_message_id < ?))"
            )
            args.extend((before[0], before[0], before[1],
                         before[0], before[1], before[2]))
        elif legacy_cursor:
            cursor = before[0].astimezone(timezone.utc).isoformat()
            filters += (
                " AND e.canonical_sequence IS NULL "
                "AND (e.linked_at < ? OR "
                "(e.linked_at = ? AND e.source_message_id < ?))"
            )
            args.extend((cursor, cursor, before[1]))
        args.append(limit)
        with closing(self._connect()) as db:
            owner = db.execute(
                "SELECT owner_principal_id FROM lifelong_thread "
                "WHERE thread_id=?", (thread_id,),
            ).fetchone()
            if owner is None or owner["owner_principal_id"] != principal.principal_id:
                raise PermissionError("lifelong thread is not owned by this principal")
            rows = db.execute(
                "SELECT e.source_message_id,e.source_audience_id,e.linked_at,"
                "e.canonical_sequence,e.turn_position,"
                "m.session_id,m.role,m.content,m.created_at "
                "FROM lifelong_thread_event e "
                "JOIN conversation_messages m "
                "ON m.id=e.source_message_id AND m.session_id=e.source_session_id "
                "JOIN social_session_principal s ON s.session_id=m.session_id "
                "WHERE " + filters + " ORDER BY "
                "CASE WHEN e.canonical_sequence IS NULL THEN 0 ELSE 1 END DESC,"
                "e.canonical_sequence DESC,e.turn_position DESC,"
                "e.linked_at DESC,e.source_message_id DESC LIMIT ?",
                tuple(args),
            ).fetchall()
        # A page bound by row count alone can still exhaust a small
        # desktop/mobile client's RAM if one source message is enormous.
        # Reject oversized pages; never silently truncate canonical history.
        total_text_bytes = sum(
            len(row["content"].encode("utf-8")) for row in rows
        )
        if total_text_bytes > 256 * 1024:
            raise ValueError(
                "lifelong page exceeds the 256-KiB display budget; "
                "retry with a smaller limit"
            )
        return tuple(
            LifelongMessage(
                thread_id=thread_id,
                message=ConversationMessage(
                    id=row["source_message_id"],
                    session_id=row["session_id"],
                    role=ConversationRole(row["role"]),
                    content=row["content"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                ),
                audience_id=row["source_audience_id"],
                linked_at=datetime.fromisoformat(row["linked_at"]),
                canonical_sequence=row["canonical_sequence"],
                turn_position=row["turn_position"],
            )
            for row in reversed(rows)
        )
