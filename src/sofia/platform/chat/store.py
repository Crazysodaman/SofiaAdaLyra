"""Canonical SQLite persistence for the Platform multi-Core chat engine.

There is exactly one writer for one canonical Platform state. This store does
not create a sidecar database, does not write another Core's protected state
and never opens a second concurrent writer path. Per-Core views are projections
over the same canonical rows, filtered by explicit membership and epoch.

Audit evidence reuses SAFE's append-only ``safe_audit_event`` hash chain so
membership and permission changes share the existing canonical trust anchor.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3

from sofia.platform.safe.audit import AuditChain
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_room (
    room_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    topic TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    owner_core_id TEXT,
    membership_epoch INTEGER NOT NULL CHECK(membership_epoch >= 1),
    history_policy TEXT NOT NULL,
    retention_seconds INTEGER,
    sequence INTEGER NOT NULL DEFAULT 0 CHECK(sequence >= 0)
);

CREATE TABLE IF NOT EXISTS chat_core (
    core_id TEXT PRIMARY KEY,
    platform_id TEXT NOT NULL,
    generation INTEGER NOT NULL CHECK(generation >= 1),
    display_name TEXT NOT NULL,
    authorized INTEGER NOT NULL CHECK(authorized IN (0, 1)),
    registered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_membership (
    room_id TEXT NOT NULL,
    core_id TEXT NOT NULL,
    member_kind TEXT NOT NULL,
    epoch INTEGER NOT NULL CHECK(epoch >= 1),
    status TEXT NOT NULL,
    joined_at TEXT,
    history_from_sequence INTEGER,
    invited_by TEXT,
    invite_expires_at TEXT,
    removed_by TEXT,
    left_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (room_id, core_id),
    FOREIGN KEY (room_id) REFERENCES chat_room(room_id)
);

CREATE TABLE IF NOT EXISTS chat_invitation (
    invite_id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    invitee_id TEXT NOT NULL,
    invited_by TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    history_from_sequence INTEGER,
    epoch INTEGER NOT NULL CHECK(epoch >= 1),
    resolved_at TEXT,
    FOREIGN KEY (room_id) REFERENCES chat_room(room_id)
);

CREATE TABLE IF NOT EXISTS chat_message (
    message_id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    sender_kind TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    stored_at TEXT NOT NULL,
    reply_to TEXT,
    origin TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK(sequence >= 1),
    audience_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    idempotency_key TEXT,
    origin_platform_id TEXT NOT NULL,
    source_generation INTEGER,
    edited_at TEXT,
    deleted_at TEXT,
    deleted_by TEXT,
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
    UNIQUE(room_id, sequence),
    FOREIGN KEY (room_id) REFERENCES chat_room(room_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS chat_message_idempotency
    ON chat_message(room_id, sender_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS chat_message_room_sequence
    ON chat_message(room_id, sequence);

CREATE TABLE IF NOT EXISTS chat_delivery (
    message_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    status TEXT NOT NULL,
    queued_at TEXT NOT NULL,
    delivered_at TEXT,
    acked_at TEXT,
    PRIMARY KEY (message_id, recipient_id),
    FOREIGN KEY (message_id) REFERENCES chat_message(message_id)
);

CREATE INDEX IF NOT EXISTS chat_delivery_recipient_status
    ON chat_delivery(recipient_id, status);

CREATE TABLE IF NOT EXISTS chat_outbox (
    outbox_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    room_id TEXT NOT NULL,
    destination_core_id TEXT NOT NULL,
    destination_platform_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    FOREIGN KEY (message_id) REFERENCES chat_message(message_id)
);

CREATE INDEX IF NOT EXISTS chat_outbox_destination
    ON chat_outbox(destination_core_id, status);

CREATE TABLE IF NOT EXISTS chat_cursor (
    actor_id TEXT NOT NULL,
    room_id TEXT NOT NULL,
    last_read_sequence INTEGER NOT NULL CHECK(last_read_sequence >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (actor_id, room_id)
);

CREATE TABLE IF NOT EXISTS chat_draft (
    actor_id TEXT NOT NULL,
    room_id TEXT NOT NULL,
    body TEXT NOT NULL,
    reply_to TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (actor_id, room_id)
);

CREATE TABLE IF NOT EXISTS chat_block (
    blocker_id TEXT NOT NULL,
    blocked_id TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (blocker_id, blocked_id)
);
"""


class ChatStore:
    """Pin one canonical SQLite file and own the chat schema."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self.audit = AuditChain(self.path)
        self._initialize()

    def _initialize(self) -> None:
        with self.transaction() as db:
            db.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=30.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def reader(self):
        db = self._connect()
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        """A short immediate transaction; the only SQLite write path."""
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()


__all__ = ["ChatStore"]
