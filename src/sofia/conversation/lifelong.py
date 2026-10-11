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
            rows = db.execute(
                "SELECT source_message_id,source_session_id,source_audience_id,"
                "visibility,linked_at FROM lifelong_thread_event "
                "WHERE thread_id=? AND source_audience_id=? "
                "AND visibility='source_audience' "
                "ORDER BY linked_at DESC, source_message_id DESC LIMIT ?",
                (thread_id, principal.audience_id, limit),
            ).fetchall()
        return tuple(
            ThreadEvent(r["source_message_id"], r["source_session_id"],
                        r["source_audience_id"], datetime.fromisoformat(r["linked_at"]),
                        r["visibility"])
            for r in reversed(rows)
        )
