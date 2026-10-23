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

from sofia.core.cognition.model import CognitiveResponse, CognitiveToolCall
from sofia.core.social.model import PrincipalContext
from sofia.core.conversation.model import ConversationMessage, ConversationRole
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


_NAME = re.compile(r"^[\w][\w .:/()-]{0,119}$", re.UNICODE)


@dataclass(frozen=True, slots=True)
class LifelongThread:
    thread_id: str
    owner_principal_id: str
    kind: str
    name: str
    created_at: datetime
    archived_at: datetime | None = None


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
    next_cursor: tuple[str, str] | None = None


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
class MainProjectionItem:
    """One Main position; content exists only for the source audience."""

    canonical_sequence: int
    turn_position: int
    linked_at: datetime
    message: ConversationMessage | None
    redacted_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalTurnAdmission:
    event_id: str
    canonical_sequence: int
    status: str
    user_message_id: str
    assistant_message_id: str
    response: CognitiveResponse | None = None
    source_channel: str = "unknown"
    source_device_id: str | None = None
    received_at: datetime = datetime.min.replace(tzinfo=timezone.utc)
    client_created_at: datetime | None = None
    reply_to_event_id: str | None = None
    correction_of_event_id: str | None = None


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
            thread_columns = {
                row[1] for row in db.execute("PRAGMA table_info(lifelong_thread)")
            }
            if "archived_at" not in thread_columns:
                db.execute("ALTER TABLE lifelong_thread ADD COLUMN archived_at TEXT")
            # Legacy projects cannot be assigned an audience from a shared
            # owner ID alone. Their source links must be checked at use time.
            for name in ("project_audience_id", "project_audience_kind"):
                if name not in thread_columns:
                    db.execute("ALTER TABLE lifelong_thread ADD COLUMN " + name + " TEXT")
            if "has_linked_source" not in thread_columns:
                # A legacy source-free project has no creator-audience
                # evidence; fail closed rather than resurrect titles whose
                # links were removed earlier.
                db.execute(
                    "ALTER TABLE lifelong_thread ADD COLUMN "
                    "has_linked_source INTEGER NOT NULL DEFAULT 1"
                )
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
            turn_columns = {
                row[1] for row in db.execute(
                    "PRAGMA table_info(canonical_conversation_turn)"
                )
            }
            for name, definition in (
                ("source_device_id", "TEXT"),
                ("client_created_at", "TEXT"),
                ("reply_to_event_id", "TEXT"),
                ("correction_of_event_id", "TEXT"),
            ):
                if name not in turn_columns:
                    db.execute(
                        "ALTER TABLE canonical_conversation_turn ADD COLUMN "
                        + name + " " + definition
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
            row["source_channel"], row["source_device_id"],
            datetime.fromisoformat(row["received_at"]),
            (
                None if row["client_created_at"] is None
                else datetime.fromisoformat(row["client_created_at"])
            ),
            row["reply_to_event_id"], row["correction_of_event_id"],
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
        source_device_id: str | None = None,
        client_created_at: datetime | None = None,
        reply_to_event_id: str | None = None,
        correction_of_event_id: str | None = None,
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
        for label, value in (
            ("source_device_id", source_device_id),
            ("reply_to_event_id", reply_to_event_id),
            ("correction_of_event_id", correction_of_event_id),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 256
            ):
                raise ValueError(f"{label} must be a bounded nonempty string")
        if client_created_at is not None and (
            not isinstance(client_created_at, datetime)
            or client_created_at.tzinfo is None
            or client_created_at.utcoffset() is None
        ):
            raise ValueError("client_created_at must be timezone-aware")
        if reply_to_event_id == event_id or correction_of_event_id == event_id:
            raise ValueError("an event cannot reference or correct itself")
        digest = sha256(json.dumps((
            principal.principal_id, principal.audience_id,
            principal.audience_kind.value, session_id, channel, content,
            source_device_id,
            None if client_created_at is None else client_created_at.isoformat(),
            reply_to_event_id, correction_of_event_id,
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
                try:
                    admission = self._turn_admission(existing)
                except (ValueError, TypeError, KeyError) as exc:
                    raise CanonicalTurnUncertain(
                        "stored canonical response is no longer independently readable"
                    ) from exc
                if admission.status == "processing":
                    raise CanonicalTurnPending("canonical turn is already processing")
                if admission.status in {"interrupted", "uncertain"}:
                    raise CanonicalTurnUncertain(
                        "prior canonical turn outcome is uncertain; replay denied"
                    )
                if admission.status == "completed":
                    # The receipt alone is not permanent permission to
                    # resurrect deleted or withdrawn source conversation.
                    # Verify BOTH original messages and their current Main
                    # source-audience links inside this same SQLite snapshot
                    # before returning previously generated model/tool text.
                    original_rows = db.execute(
                        """SELECT m.id,m.role,m.content,e.turn_position
                        FROM conversation_messages AS m
                        JOIN lifelong_thread_event AS e
                          ON e.source_message_id=m.id
                          AND e.source_session_id=m.session_id
                        JOIN lifelong_thread AS t
                          ON t.thread_id=e.thread_id
                        WHERE m.session_id=?
                          AND m.id IN (?,?)
                          AND e.canonical_sequence=?
                          AND e.source_audience_id=?
                          AND e.visibility='source_audience'
                          AND t.kind='main'
                          AND t.owner_principal_id=?""",
                        (
                            session_id, admission.user_message_id,
                            admission.assistant_message_id,
                            admission.canonical_sequence,
                            principal.audience_id, principal.principal_id,
                        ),
                    ).fetchall()
                    original_by_id = {row["id"]: row for row in original_rows}
                    user = original_by_id.get(admission.user_message_id)
                    assistant = original_by_id.get(admission.assistant_message_id)
                    if (
                        admission.response is None
                        or len(original_rows) != 2
                        or user is None or assistant is None
                        or user["role"] != "user" or user["turn_position"] != 0
                        or assistant["role"] != "assistant"
                        or assistant["turn_position"] != 1
                        or assistant["content"] != admission.response.content
                    ):
                        raise CanonicalTurnUncertain(
                            "completed response no longer has current original "
                            "conversation and Main audience evidence"
                        )
                return admission
            for reference, purpose in (
                (reply_to_event_id, "reply"),
                (correction_of_event_id, "correction"),
            ):
                if reference is None:
                    continue
                target = db.execute(
                    "SELECT owner_principal_id,source_audience_id,status "
                    "FROM canonical_conversation_turn WHERE event_id=?",
                    (reference,),
                ).fetchone()
                if target is None:
                    raise LookupError(f"{purpose} target does not exist")
                if tuple(target[:2]) != (
                    principal.principal_id, principal.audience_id,
                ):
                    raise PermissionError(
                        f"{purpose} target belongs to another audience"
                    )
                if target["status"] != "completed":
                    raise CanonicalTurnUncertain(
                        f"{purpose} target is not durably completed"
                    )
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
                received_at,settled_at,source_device_id,client_created_at,
                reply_to_event_id,correction_of_event_id
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,?,?,?)""",
                (
                    event_id, principal.principal_id, principal.audience_id,
                    principal.audience_kind.value, channel, session_id,
                    digest, sequence, "processing", runtime_id,
                    user_id, assistant_id, None, stamp,
                    source_device_id,
                    (None if client_created_at is None else
                     client_created_at.astimezone(timezone.utc).isoformat()),
                    reply_to_event_id, correction_of_event_id,
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
                    "INSERT INTO lifelong_thread("
                    "thread_id,owner_principal_id,kind,name,created_at) "
                    "VALUES(?,?,?,?,?)",
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
        if not isinstance(admission, CanonicalTurnAdmission):
            raise TypeError("typed original canonical admission required")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("uncertainty timestamp must be timezone-aware")
        # A stale runtime must never mutate the receipt associated with an
        # unrelated claim, even if another path accidentally reused its event
        # ID. Match the entire immutable original admission identity.
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                """UPDATE canonical_conversation_turn SET status=?,settled_at=?
                WHERE event_id=? AND canonical_sequence=?
                AND user_message_id=? AND assistant_message_id=?
                AND status='processing'""",
                (
                    "interrupted" if interrupted else "uncertain",
                    now.astimezone(timezone.utc).isoformat(),
                    admission.event_id, admission.canonical_sequence,
                    admission.user_message_id, admission.assistant_message_id,
                ),
            )
            if changed.rowcount != 1:
                row = db.execute(
                    "SELECT status,canonical_sequence,user_message_id,"
                    "assistant_message_id FROM canonical_conversation_turn "
                    "WHERE event_id=?", (admission.event_id,),
                ).fetchone()
                if row is None or (
                    row["canonical_sequence"] != admission.canonical_sequence
                    or row["user_message_id"] != admission.user_message_id
                    or row["assistant_message_id"] != admission.assistant_message_id
                ):
                    raise CanonicalTurnUncertain(
                        "canonical turn admission identity changed before uncertainty"
                    )
                # A completed or already-uncertain receipt is authoritative:
                # never regress it to a different status on stale failure.
                if row["status"] not in {"completed", "interrupted", "uncertain"}:
                    raise CanonicalTurnUncertain(
                        "canonical turn could not settle uncertainty"
                    )

    @staticmethod
    def _decode(row: sqlite3.Row) -> LifelongThread:
        return LifelongThread(
            thread_id=row["thread_id"],
            owner_principal_id=row["owner_principal_id"],
            kind=row["kind"], name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            archived_at=(datetime.fromisoformat(row["archived_at"])
                         if row["archived_at"] is not None else None),
        )

    @staticmethod
    def _project_scope_allowed(
        db: sqlite3.Connection, *, row: sqlite3.Row,
        principal: PrincipalContext,
    ) -> bool:
        """Verify an existing project uses only this actual source audience.

        New projects have an immutable creation-audience tag. Old projects
        lacking that tag are eligible only when *all* existing source links
        and current session bindings agree on the same authenticated scope.
        Mixed/unlinked legacy projects need independent owner review.
        """
        if row["kind"] != "project":
            return False
        if row["project_audience_id"] is not None and (
            row["project_audience_id"] != principal.audience_id
            or row["project_audience_kind"] != principal.audience_kind.value
        ):
            return False
        counts = db.execute(
            "SELECT COUNT(*),SUM(CASE WHEN "
            "e.visibility='source_audience' AND e.source_audience_id=? "
            "AND m.id IS NOT NULL AND s.principal_id=? "
            "AND s.audience_id=? AND s.audience_kind=? "
            "THEN 1 ELSE 0 END) "
            "FROM lifelong_thread_event AS e "
            "LEFT JOIN conversation_messages AS m "
            "ON m.id=e.source_message_id AND m.session_id=e.source_session_id "
            "LEFT JOIN social_session_principal AS s ON s.session_id=m.session_id "
            "WHERE e.thread_id=?",
            (principal.audience_id, principal.principal_id,
             principal.audience_id, principal.audience_kind.value,
             row["thread_id"]),
        ).fetchone()
        if counts[0] == 0:
            # Only a never-linked project with an authenticated creation
            # scope can be claimed. Legacy source-free rows stay ambiguous.
            return (
                row["project_audience_id"] is not None
                and row["has_linked_source"] == 0
            )
        # An origin tag is not permission to ignore later foreign, deleted
        # or rebound source evidence. All links must still be original-bound.
        return counts[1] == counts[0]

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
                if kind == "project" and not self._project_scope_allowed(
                    db, row=row, principal=owner,
                ):
                    raise PermissionError(
                        "project name is unavailable in this source audience"
                    )
                return self._decode(row)
            identifier = f"thread:{uuid4().hex}"
            when = datetime.now(timezone.utc).isoformat()
            if kind == "project":
                db.execute(
                    "INSERT INTO lifelong_thread("
                    "thread_id,owner_principal_id,kind,name,created_at,"
                    "project_audience_id,project_audience_kind,has_linked_source) "
                    "VALUES(?,?,?,?,?,?,?,0)",
                    (identifier, owner.principal_id, kind, name, when,
                     owner.audience_id, owner.audience_kind.value),
                )
            else:
                db.execute(
                    "INSERT INTO lifelong_thread("
                    "thread_id,owner_principal_id,kind,name,created_at) "
                    "VALUES(?,?,?,?,?)",
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
        include_archived: bool = False,
    ) -> tuple[LifelongThread, ...]:
        """Enumerate only canonical thread headers owned by authenticated user."""
        if not isinstance(owner, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded thread listing required")
        if type(include_archived) is not bool:
            raise TypeError("include_archived must be bool")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM lifelong_thread WHERE owner_principal_id=? "
                + ("" if include_archived else "AND archived_at IS NULL ")
                + "ORDER BY CASE kind WHEN 'main' THEN 0 ELSE 1 END,"
                "created_at DESC,thread_id LIMIT ?",
                (owner.principal_id, limit),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def list_visible_threads(
        self, *, owner: PrincipalContext, limit: int = 30,
        include_archived: bool = False,
    ) -> tuple[LifelongThread, ...]:
        """Page headers only AFTER original-audience visibility admission.

        Empty projects are visible only to their original authenticated
        creation audience. As soon as an original is linked, source-audience
        visibility is revalidated from the actual current binding in SQL
        before applying the result limit.
        """
        if not isinstance(owner, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded visible thread listing required")
        if type(include_archived) is not bool:
            raise TypeError("include_archived must be bool")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT t.* FROM lifelong_thread AS t "
                "WHERE t.owner_principal_id=? "
                + ("" if include_archived else "AND t.archived_at IS NULL ")
                + "AND (t.kind='main' OR t.project_audience_id IS NULL "
                "OR (t.project_audience_id=? AND t.project_audience_kind=?)) "
                "AND (t.kind='main' OR NOT EXISTS ("
                "SELECT 1 FROM lifelong_thread_event AS x "
                "LEFT JOIN conversation_messages AS xm "
                "ON xm.id=x.source_message_id AND xm.session_id=x.source_session_id "
                "LEFT JOIN social_session_principal AS xs "
                "ON xs.session_id=xm.session_id "
                "WHERE x.thread_id=t.thread_id AND ("
                "x.visibility!='source_audience' OR x.source_audience_id!=? "
                "OR xm.id IS NULL OR xs.principal_id IS NULL "
                "OR xs.principal_id!=? OR xs.audience_id!=? "
                "OR xs.audience_kind!=?))) "
                "AND ("
                "t.kind='main' OR (t.kind='project' AND ("
                "(t.project_audience_id=? AND t.project_audience_kind=? "
                "AND t.has_linked_source=0 "
                "AND NOT EXISTS (SELECT 1 FROM lifelong_thread_event AS e0 "
                "WHERE e0.thread_id=t.thread_id)) OR EXISTS ("
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
                ")))) "
                "ORDER BY CASE t.kind WHEN 'main' THEN 0 ELSE 1 END,"
                "t.created_at DESC,t.thread_id LIMIT ?",
                (
                    owner.principal_id,
                    owner.audience_id, owner.audience_kind.value,
                    owner.audience_id, owner.principal_id, owner.audience_id,
                    owner.audience_kind.value,
                    owner.audience_id, owner.audience_kind.value,
                    owner.audience_id, owner.principal_id, owner.audience_id,
                    owner.audience_kind.value, limit,
                ),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def source_free_project_visible(
        self, *, principal: PrincipalContext, thread_id: str,
    ) -> bool:
        """Allow an empty read-only view only for a never-linked project.

        The creation stamp is not sufficient for a formerly populated
        project: once an original was linked, future source withdrawal
        must not re-expose old titles or suggest the content never existed.
        """
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if not isinstance(thread_id, str) or not 8 <= len(thread_id) <= 128:
            raise ValueError("bounded project thread ID required")
        with closing(self._connect()) as db:
            return db.execute(
                "SELECT 1 FROM lifelong_thread AS t WHERE t.thread_id=? "
                "AND t.owner_principal_id=? AND t.kind='project' "
                "AND t.project_audience_id=? AND t.project_audience_kind=? "
                "AND t.has_linked_source=0 "
                "AND NOT EXISTS(SELECT 1 FROM lifelong_thread_event AS e "
                "WHERE e.thread_id=t.thread_id)",
                (thread_id, principal.principal_id, principal.audience_id,
                 principal.audience_kind.value),
            ).fetchone() is not None

    @staticmethod
    def _authorize_project_edit(
        db: sqlite3.Connection, *, principal: PrincipalContext, thread_id: str,
    ) -> sqlite3.Row:
        """Require current exact-source audience admission before title edits.

        A shared principal alone cannot rename/archive another device's
        protected project. A newly created, source-free project can be
        edited by its attested creation audience. Unbound legacy metadata
        cannot be claimed merely because an owner ID matches.
        """
        row = db.execute(
            "SELECT * FROM lifelong_thread WHERE thread_id=? "
            "AND owner_principal_id=? AND kind='project' "
            "AND (EXISTS (SELECT 1 FROM lifelong_thread_event AS e "
            "JOIN conversation_messages AS m ON m.id=e.source_message_id "
            "AND m.session_id=e.source_session_id "
            "JOIN social_session_principal AS s ON s.session_id=m.session_id "
            "WHERE e.thread_id=lifelong_thread.thread_id "
            "AND e.visibility='source_audience' "
            "AND e.source_audience_id=? "
            "AND s.principal_id=? AND s.audience_id=? "
            "AND s.audience_kind=?) OR "
            "(project_audience_id=? AND project_audience_kind=? "
            "AND has_linked_source=0 "
            "AND NOT EXISTS (SELECT 1 FROM lifelong_thread_event AS e0 "
            "WHERE e0.thread_id=lifelong_thread.thread_id)))",
            (thread_id, principal.principal_id, principal.audience_id,
             principal.principal_id, principal.audience_id,
             principal.audience_kind.value, principal.audience_id,
             principal.audience_kind.value),
        ).fetchone()
        if row is None or not LifelongThreadStore._project_scope_allowed(
            db, row=row, principal=principal,
        ):
            raise PermissionError(
                "project edit requires current original-source audience access"
            )
        return row

    def rename_project(
        self, *, principal: PrincipalContext, thread_id: str, new_name: str,
    ) -> LifelongThread:
        """Rename a source-visible project without editing source messages."""
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated project principal required")
        if not isinstance(thread_id, str) or not 8 <= len(thread_id) <= 128:
            raise ValueError("bounded project thread ID required")
        if not isinstance(new_name, str) or _NAME.fullmatch(new_name) is None:
            raise ValueError("bounded project name required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = self._authorize_project_edit(
                db, principal=principal, thread_id=thread_id,
            )
            if current["name"] == new_name:
                return self._decode(current)
            duplicate = db.execute(
                "SELECT 1 FROM lifelong_thread WHERE owner_principal_id=? "
                "AND kind='project' AND name=? AND thread_id<>?",
                (principal.principal_id, new_name, thread_id),
            ).fetchone()
            if duplicate is not None:
                raise ValueError("project name already exists")
            db.execute(
                "UPDATE lifelong_thread SET name=? WHERE thread_id=? "
                "AND owner_principal_id=? AND kind='project'",
                (new_name, thread_id, principal.principal_id),
            )
            row = db.execute(
                "SELECT * FROM lifelong_thread WHERE thread_id=?", (thread_id,),
            ).fetchone()
            return self._decode(row)

    def set_project_archived(
        self, *, principal: PrincipalContext, thread_id: str, archived: bool,
    ) -> LifelongThread:
        """Archive or restore one project without deleting original evidence."""
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated project principal required")
        if not isinstance(thread_id, str) or not 8 <= len(thread_id) <= 128:
            raise ValueError("bounded project thread ID required")
        if type(archived) is not bool:
            raise TypeError("archived must be a bool")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = self._authorize_project_edit(
                db, principal=principal, thread_id=thread_id,
            )
            if (current["archived_at"] is not None) == archived:
                return self._decode(current)
            stamp = datetime.now(timezone.utc).isoformat() if archived else None
            db.execute(
                "UPDATE lifelong_thread SET archived_at=? WHERE thread_id=? "
                "AND owner_principal_id=? AND kind='project'",
                (stamp, thread_id, principal.principal_id),
            )
            updated = db.execute(
                "SELECT * FROM lifelong_thread WHERE thread_id=?", (thread_id,),
            ).fetchone()
            return self._decode(updated)

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
                "SELECT * FROM lifelong_thread WHERE thread_id=?",
                (thread_id,),
            ).fetchone()
            if thread is None or thread["owner_principal_id"] != principal.principal_id:
                raise PermissionError("thread does not belong to authenticated principal")
            if thread["kind"] == "project" and not self._project_scope_allowed(
                db, row=thread, principal=principal,
            ):
                raise PermissionError(
                    "project link cannot cross original source audiences"
                )
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
            if thread["kind"] == "project":
                # Durable even if all event links are subsequently removed.
                # A formerly populated thread must not be reinterpreted as
                # a never-used project and leak its old title on a new device.
                db.execute(
                    "UPDATE lifelong_thread SET has_linked_source=1 "
                    "WHERE thread_id=? AND kind='project'",
                    (thread_id,),
                )

    def preview_historical_import(
        self, *, principal: PrincipalContext, session_id: str,
        limit: int = 128,
        after: tuple[str, str] | None = None,
    ) -> HistoricalImportPreview:
        """Page reviewed source candidates without automatic import.

        The cursor is the original (stored timestamp, message ID) returned
        in the preceding preview. This is an ordering cursor, not authority:
        each page independently checks the exact CURRENT source audience.
        """
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated owner principal required")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("exact source session ID required")
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError("bounded source import preview limit required")
        if after is not None and (
            not isinstance(after, tuple) or len(after) != 2
            or any(not isinstance(value, str) or not 1 <= len(value) <= 256
                   for value in after)
        ):
            raise ValueError("bounded historical source cursor required")
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
            cursor_clause = (
                "" if after is None else
                " AND (m.created_at>? OR "
                "(m.created_at=? AND m.id>?))"
            )
            arguments: tuple[object, ...] = (
                principal.principal_id, principal.audience_id, session_id,
            )
            if after is not None:
                arguments += (after[0], after[0], after[1])
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
                "WHERE m.session_id=?" + cursor_clause +
                " ORDER BY m.created_at,m.id LIMIT ?",
                (*arguments, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        batch = rows[:limit]
        return HistoricalImportPreview(
            session_id=session_id,
            owner_principal_id=principal.principal_id,
            source_audience_id=principal.audience_id,
            eligible_message_ids=tuple(row["id"] for row in batch),
            already_linked_ids=tuple(row["id"] for row in batch if row["already"]),
            original_timestamps=tuple(row["created_at"] for row in batch),
            next_cursor=(
                (batch[-1]["created_at"], batch[-1]["id"])
                if has_more else None
            ),
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
            # External approval can be revoked during source enumeration.
            # Verify it again inside the canonical writer boundary before
            # creating ANY Main import receipt or source links.
            if independently_verify_operator_review(review_ref, digest) is not True:
                raise PermissionError(
                    "independent operator import approval expired before publication"
                )
            thread = db.execute(
                "SELECT thread_id FROM lifelong_thread "
                "WHERE owner_principal_id=? AND kind='main'",
                (principal.principal_id,),
            ).fetchone()
            if thread is None:
                thread_id = f"thread:{uuid4().hex}"
                db.execute(
                    "INSERT INTO lifelong_thread("
                    "thread_id,owner_principal_id,kind,name,created_at) "
                    "VALUES(?,?,?,?,?)",
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
            if independently_verify_operator_review(review_ref, digest) is not True:
                raise PermissionError(
                    "independent operator rollback approval expired before publication"
                )
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
                # An import-created source link may later acquire
                # independent canonical-turn ordering. The old import review
                # does not own that later Main admission, so never erase it
                # just because its original source ID appeared in this batch.
                current_link = db.execute(
                    "SELECT canonical_sequence,turn_position "
                    "FROM lifelong_thread_event WHERE thread_id=? "
                    "AND source_message_id=? AND source_session_id=? "
                    "AND source_audience_id=? AND visibility='source_audience'",
                    (owner["thread_id"], identifier,
                     owner["source_session_id"], principal.audience_id),
                ).fetchone()
                if current_link is not None and (
                    current_link["canonical_sequence"] is not None
                    or current_link["turn_position"] is not None
                ):
                    raise PermissionError(
                        "historical rollback cannot remove an adopted canonical turn"
                    )
                db.execute(
                    "DELETE FROM lifelong_thread_event "
                    "WHERE thread_id=? AND source_message_id=? "
                    "AND source_session_id=? AND source_audience_id=? "
                    "AND visibility='source_audience' "
                    "AND canonical_sequence IS NULL AND turn_position IS NULL",
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
                "SELECT * FROM lifelong_thread WHERE thread_id=?",
                (thread_id,),
            ).fetchone()
            if row is None or row["owner_principal_id"] != principal.principal_id:
                raise PermissionError("thread not accessible to caller")
            if row["kind"] == "project" and not self._project_scope_allowed(
                db, row=row, principal=principal,
            ):
                return ()
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
                "SELECT * FROM lifelong_thread WHERE thread_id=?",
                (thread_id,),
            ).fetchone()
            if thread is None or thread["owner_principal_id"] != principal.principal_id:
                raise PermissionError("thread not accessible to authenticated principal")
            if thread["kind"] == "project" and not self._project_scope_allowed(
                db, row=thread, principal=principal,
            ):
                return ()
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
                "SELECT * FROM lifelong_thread WHERE thread_id=?",
                (thread_id,),
            ).fetchone()
            if owner is None or owner["owner_principal_id"] != principal.principal_id:
                raise PermissionError("lifelong thread is not owned by this principal")
            if owner["kind"] == "project" and not self._project_scope_allowed(
                db, row=owner, principal=principal,
            ):
                raise PermissionError("project original audience is unavailable")
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

    def main_projection_page(
        self, *, principal: PrincipalContext,
        before: tuple[int, int] | None = None, limit: int = 50,
    ) -> tuple[MainProjectionItem, ...]:
        """Return canonical Main order with safe unavailable placeholders.

        Content is admitted only when the original message still exists and
        its current session binding exactly matches the requesting audience.
        A different owner audience receives only canonical position and a
        generic reason--never content, source IDs, channel, tool output, or
        credential-bearing metadata. This projection cannot execute/replay.
        """
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if before is not None and (
            not isinstance(before, tuple) or len(before) != 2
            or type(before[0]) is not int or before[0] < 1
            or type(before[1]) is not int or before[1] not in {0, 1}
        ):
            raise ValueError("projection cursor requires sequence and position")
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("projection page limit must be 1..200")
        filters = (
            "t.owner_principal_id=? AND t.kind='main' "
            "AND e.canonical_sequence IS NOT NULL"
        )
        arguments: list[object] = [principal.principal_id]
        if before is not None:
            filters += (
                " AND (e.canonical_sequence<? OR "
                "(e.canonical_sequence=? AND e.turn_position<?))"
            )
            arguments.extend((before[0], before[0], before[1]))
        arguments.append(limit)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT e.canonical_sequence,e.turn_position,e.linked_at,"
                "m.id,m.session_id,m.role,m.content,m.created_at,"
                "s.principal_id,s.audience_id,s.audience_kind,"
                "e.source_audience_id,e.visibility "
                "FROM lifelong_thread_event AS e "
                "JOIN lifelong_thread AS t ON t.thread_id=e.thread_id "
                "LEFT JOIN conversation_messages AS m "
                "ON m.id=e.source_message_id AND m.session_id=e.source_session_id "
                "LEFT JOIN social_session_principal AS s "
                "ON s.session_id=e.source_session_id "
                "WHERE " + filters + " "
                "ORDER BY e.canonical_sequence DESC,e.turn_position DESC LIMIT ?",
                tuple(arguments),
            ).fetchall()
        page: list[MainProjectionItem] = []
        for row in reversed(rows):
            allowed = (
                row["id"] is not None
                and row["visibility"] == "source_audience"
                and row["source_audience_id"] == principal.audience_id
                and row["principal_id"] == principal.principal_id
                and row["audience_id"] == principal.audience_id
                and row["audience_kind"] == principal.audience_kind.value
            )
            message = None
            reason = "unavailable_on_this_device"
            if allowed:
                message = ConversationMessage(
                    id=row["id"], session_id=row["session_id"],
                    role=ConversationRole(row["role"]), content=row["content"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                reason = None
            page.append(MainProjectionItem(
                canonical_sequence=int(row["canonical_sequence"]),
                turn_position=int(row["turn_position"]),
                linked_at=datetime.fromisoformat(row["linked_at"]),
                message=message, redacted_reason=reason,
            ))
        return tuple(page)
