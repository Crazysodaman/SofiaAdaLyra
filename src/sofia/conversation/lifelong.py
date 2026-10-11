"""Lifelong conversation identity over immutable, channel-bound source messages.

One MAIN per principal; optional PROJECT threads. Every linked message keeps
its original SocialSessionStore audience, source session and message ID.
A projection is not a message delivery and confers no tool/SAFE authority.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from sofia.social.model import PrincipalContext
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.model import ConversationMessage, ConversationRole


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


@dataclass(frozen=True, slots=True)
class LifelongMessage:
    """Original durable message with its actual source audience and link time."""

    thread_id: str
    message: ConversationMessage
    audience_id: str
    linked_at: datetime


class LifelongThreadStore:
    """Metadata/links in canonical sofia.db; never a second transcript store."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("canonical sofia.db must already exist")
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
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

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
            db.execute(
                "INSERT INTO lifelong_thread_event VALUES(?,?,?,?,?,?)",
                (thread_id, source_message_id, row["session_id"],
                 row["audience_id"], visibility,
                 datetime.now(timezone.utc).isoformat()),
            )

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
                "e.source_audience_id,e.visibility,e.linked_at "
                "FROM lifelong_thread_event AS e "
                "JOIN conversation_messages AS m "
                "ON m.id=e.source_message_id AND m.session_id=e.source_session_id "
                "JOIN social_session_principal AS s ON s.session_id=m.session_id "
                "WHERE e.thread_id=? AND e.source_audience_id=? "
                "AND e.visibility='source_audience' "
                "AND s.principal_id=? AND s.audience_id=? "
                "AND s.audience_kind=? "
                "ORDER BY e.linked_at DESC,e.source_message_id DESC LIMIT ?",
                (thread_id, principal.audience_id, principal.principal_id,
                 principal.audience_id, principal.audience_kind.value, limit),
            ).fetchall()
        return tuple(
            ThreadEvent(r["source_message_id"], r["source_session_id"],
                        r["source_audience_id"], datetime.fromisoformat(r["linked_at"]),
                        r["visibility"])
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
                "ORDER BY m.created_at DESC,m.id DESC LIMIT ?",
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
        before: tuple[datetime, str] | None = None,
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
        if before is not None and (
            not isinstance(before, tuple) or len(before) != 2
            or not isinstance(before[0], datetime)
            or before[0].tzinfo is None
            or before[0].utcoffset() is None
            or not isinstance(before[1], str)
            or not before[1].strip()
        ):
            raise ValueError("before cursor requires aware timestamp and message ID")
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
        if before is not None:
            cursor = before[0].isoformat()
            filters += (
                " AND (e.linked_at < ? OR "
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
                "m.session_id,m.role,m.content,m.created_at "
                "FROM lifelong_thread_event e "
                "JOIN conversation_messages m "
                "ON m.id=e.source_message_id AND m.session_id=e.source_session_id "
                "JOIN social_session_principal s ON s.session_id=m.session_id "
                "WHERE " + filters + " ORDER BY e.linked_at DESC,"
                "e.source_message_id DESC LIMIT ?",
                tuple(args),
            ).fetchall()
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
            )
            for row in reversed(rows)
        )
