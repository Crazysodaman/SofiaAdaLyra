"""Durable virtual-gesture evidence and independently checked session stop.

Only a trusted host may call these methods with a persisted, authenticated
user message. No model output, lab fixture, or unverified pointer is admitted.
The user-authored message grants only its own ordinary representational gesture;
no blanket consent, real contact, private-region or avatar permission is inferred.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from sofia.interaction.core import InteractionDecision, InteractionEngine

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")
_STOP = re.compile(r"^sof[ií]a,?\s+(stop|resume)\s+(?:body\s+)?interactions[.!]?$", re.I)


def control_command(text: str) -> str | None:
    """Exact addressed user command; discussion and quotes cannot revoke/enable."""
    if not isinstance(text, str):
        raise TypeError("Interaction command must be text.")
    if len(text) > 100 or '\n' in text or '`' in text or '"' in text or '*' in text:
        return None
    match = _STOP.fullmatch(text.strip())
    return match.group(1).casefold() if match else None


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} requires a bounded source identifier.")
    return value


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An aware source timestamp is required.")
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class ControlOutcome:
    status: str  # stopped, resumed, replayed
    reason: str


class InteractionLedger:
    """Per-session stop and at-most-once gesture evidence in existing state DB.

    BEGIN IMMEDIATE serializes simultaneous writes across processes. A denied
    private-region attempt stores a digest/status, not the sensitive region or
    source text. No synthesized emotion or real-world touch is stored here.
    """

    def __init__(self, state_path: str | Path) -> None:
        if not isinstance(state_path, (str, Path)) or not str(state_path).strip():
            raise ValueError("A configured state database path is required.")
        self.path = Path(state_path)
        if not self.path.parent.is_dir() or str(state_path) == ':memory:':
            raise ValueError("Use an existing persistent state directory.")
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS interaction_session_controls (
                    session_id TEXT PRIMARY KEY, stopped INTEGER NOT NULL DEFAULT 0
                        CHECK (stopped IN (0, 1))
                );
                CREATE TABLE IF NOT EXISTS interaction_control_events (
                    message_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    content_digest TEXT NOT NULL, command TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS interaction_evidence (
                    message_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    content_digest TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    status TEXT NOT NULL, region_id TEXT, gesture TEXT,
                    registry_version TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.execute('PRAGMA busy_timeout=5000')
        return db

    def stopped(self, session_id: str) -> bool:
        _id(session_id, 'session_id')
        with self._connect() as db:
            row = db.execute('SELECT stopped FROM interaction_session_controls WHERE session_id=?',
                             (session_id,)).fetchone()
            return bool(row[0]) if row else False

    def control(self, *, session_id: str, message_id: str, content: str,
                occurred_at: datetime) -> ControlOutcome:
        """Persist an explicit saved-user stop/resume before any model reply."""
        _id(session_id, 'session_id')
        _id(message_id, 'message_id')
        command = control_command(content)
        if command is None:
            raise ValueError('An exact addressed interaction control is required.')
        digest = sha256(content.encode('utf-8')).hexdigest()
        when = _utc(occurred_at)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT session_id, content_digest, command, occurred_at '
                             'FROM interaction_control_events WHERE message_id=?', (message_id,)).fetchone()
            if old is not None:
                if old != (session_id, digest, command, when):
                    raise ValueError('Control message ID reused for different evidence.')
                return ControlOutcome('replayed', 'Control message already processed; no new state change.')
            # Sharing an ID between control and contact is forbidden.
            if db.execute('SELECT 1 FROM interaction_evidence WHERE message_id=?', (message_id,)).fetchone():
                raise ValueError('Message ID is already used for a gesture.')
            db.execute('INSERT INTO interaction_session_controls (session_id, stopped) VALUES (?, ?) '
                       'ON CONFLICT(session_id) DO UPDATE SET stopped=excluded.stopped',
                       (session_id, int(command == 'stop')))
            db.execute('INSERT INTO interaction_control_events VALUES (?, ?, ?, ?, ?)',
                       (message_id, session_id, digest, command, when))
        if command == 'stop':
            return ControlOutcome('stopped', 'Representational body interactions stopped for this session.')
        return ControlOutcome('resumed', 'Ordinary user-initiated text gestures may resume; restricted regions remain denied.')

    def process_text(self, *, engine: InteractionEngine, content: str,
                     message_id: str, session_id: str,
                     occurred_at: datetime) -> tuple[InteractionDecision | None, bool]:
        """Enforce durable stop and deduplicate one persisted user message.

        Returns (decision, first_processing). Replays are acknowledged, never
        described as fresh contact or a newly completed gesture.
        """
        if not isinstance(engine, InteractionEngine):
            raise TypeError('Canonical shared InteractionEngine required.')
        _id(message_id, 'message_id')
        _id(session_id, 'session_id')
        when = _utc(occurred_at)
        digest = sha256(content.encode('utf-8')).hexdigest()
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT session_id, content_digest, occurred_at, status '
                             'FROM interaction_evidence WHERE message_id=?', (message_id,)).fetchone()
            if old is not None:
                if old[:3] != (session_id, digest, when):
                    raise ValueError('Gesture message ID reused for different evidence.')
                decision = engine.from_text(content=content, message_id=message_id,
                                            session_id=session_id, occurred_at=occurred_at,
                                            stopped=(old[3] == 'denied'))
                if decision is None:
                    raise ValueError('Recorded gesture no longer parses; registry migration needed.')
                return (InteractionDecision(decision.event, 'acknowledged',
                         'This saved gesture was already processed; no new contact or reaction.'), False)
            if db.execute('SELECT 1 FROM interaction_control_events WHERE message_id=?', (message_id,)).fetchone():
                raise ValueError('Message ID is already used for a session control.')
            row = db.execute('SELECT stopped FROM interaction_session_controls WHERE session_id=?',
                             (session_id,)).fetchone()
            decision = engine.from_text(content=content, message_id=message_id,
                                        session_id=session_id, occurred_at=occurred_at,
                                        stopped=bool(row[0]) if row else False)
            if decision is None:
                return None, False
            event = decision.event
            # Keep restricted and unresolved region identities out of this log.
            region = event.region_id if decision.status == 'accepted' else None
            gesture = event.gesture if decision.status == 'accepted' else None
            db.execute('INSERT INTO interaction_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                       (message_id, session_id, digest, when, decision.status,
                        region, gesture, event.registry_version))
            return decision, True

    def accepted(self, message_id: str) -> tuple[str, str, str] | None:
        """Read an accepted gesture's session/region/verb, never raw text."""
        _id(message_id, 'message_id')
        with self._connect() as db:
            row = db.execute('SELECT session_id, region_id, gesture FROM interaction_evidence '
                             "WHERE message_id=? AND status='accepted'", (message_id,)).fetchone()
            return tuple(row) if row is not None else None
