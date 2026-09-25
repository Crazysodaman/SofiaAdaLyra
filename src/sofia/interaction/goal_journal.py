"""Explicit, inspectable Sofía goals and queue-only outreach while running.

No daemon, LLM calls, tool permissions, notifications or delivery adapter.
A trusted foreground/idle caller supplies actual presence, chosen text and
source evidence. Silent is a valid result. Nothing is inferred while offline.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class Goal:
    id: str
    source_id: str
    title: str
    kind: str
    priority: int
    status: str
    created_at: str


@dataclass(frozen=True)
class PendingMessage:
    id: str
    goal_id: str
    evidence_id: str
    content: str
    created_at: str
    status: str


class GoalJournal:
    """Source-backed goal selection, opt-in QUEUE ONLY; no external rights."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError('An existing application state DB is required.')
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                          "AND name='conversation_messages'").fetchone() is None:
                raise ValueError('Saved conversation evidence is required.')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS interact_goals (
                    id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
                    title TEXT NOT NULL, kind TEXT NOT NULL,
                    priority INTEGER NOT NULL CHECK (priority BETWEEN 0 AND 5),
                    status TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS interact_goal_transitions (
                    transition_id TEXT PRIMARY KEY, goal_id TEXT NOT NULL,
                    source_id TEXT NOT NULL, from_status TEXT NOT NULL,
                    to_status TEXT NOT NULL, occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS interact_queued_messages (
                    id TEXT PRIMARY KEY, goal_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL, content TEXT NOT NULL,
                    created_at TEXT NOT NULL, status TEXT NOT NULL
                );
            ''')
            db.commit()

    @staticmethod
    def _id(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 120:
            raise ValueError(f'{name} requires a bounded identifier.')
        return value

    @staticmethod
    def _time(value: datetime) -> str:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('An aware timestamp is required.')
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _source(db: sqlite3.Connection, source_id: str) -> None:
        row = db.execute('SELECT role FROM conversation_messages WHERE id=?',
                         (source_id,)).fetchone()
        if row is None or row[0] not in ('user', 'assistant'):
            raise ValueError('Goal needs an actual saved conversation source.')

    def create_goal(self, *, goal_id: str, source_id: str, title: str,
                    kind: str, priority: int, at: datetime) -> Goal:
        self._id(goal_id, 'goal_id')
        self._id(source_id, 'source_id')
        if not isinstance(title, str) or not title.strip() or len(title) > 160:
            raise ValueError('A concise goal title is required.')
        if kind not in ('question', 'lab_suggestion', 'review'):
            raise ValueError('Unknown goal kind; no arbitrary tool operations.')
        if type(priority) is not int or not 0 <= priority <= 5:
            raise ValueError('Priority must be an integer between 0 and 5.')
        goal = Goal(goal_id, source_id, title.strip(), kind, priority,
                    'proposed', self._time(at))
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.execute('BEGIN IMMEDIATE')
            self._source(db, source_id)
            previous = db.execute('SELECT * FROM interact_goals WHERE id=?',
                                  (goal_id,)).fetchone()
            if previous is not None and tuple(previous) != tuple(vars(goal).values()):
                raise ValueError('Goal ID reused for different content.')
            if previous is None:
                db.execute('INSERT INTO interact_goals VALUES (?,?,?,?,?,?,?)',
                           tuple(vars(goal).values()))
            db.commit()
        return goal

    def transition(self, *, goal_id: str, transition_id: str,
                   source_id: str, expected_status: str, next_status: str,
                   at: datetime) -> Goal:
        for name, value in (('goal_id', goal_id), ('transition_id', transition_id),
                            ('source_id', source_id)):
            self._id(value, name)
        allowed = {
            'proposed': ('active', 'cancelled'),
            'active': ('paused', 'completed', 'cancelled'),
            'paused': ('active', 'cancelled'),
        }
        if next_status not in allowed.get(expected_status, ()):
            raise ValueError('Illegal goal transition.')
        when = self._time(at)
        transition = (transition_id, goal_id, source_id, expected_status,
                      next_status, when)
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.execute('BEGIN IMMEDIATE')
            self._source(db, source_id)
            old = db.execute('SELECT * FROM interact_goal_transitions WHERE transition_id=?',
                             (transition_id,)).fetchone()
            if old is not None and old != transition:
                raise ValueError('Transition ID reused with different evidence.')
            if old is None:
                changed = db.execute('UPDATE interact_goals SET status=? WHERE id=? AND status=?',
                                     (next_status, goal_id, expected_status))
                if changed.rowcount != 1:
                    raise ValueError('Goal changed concurrently or does not exist.')
                db.execute('INSERT INTO interact_goal_transitions VALUES (?,?,?,?,?,?)',
                           transition)
            row = db.execute('SELECT * FROM interact_goals WHERE id=?', (goal_id,)).fetchone()
            db.commit()
        return Goal(*row)

    def next_goal(self, *, enabled: bool, user_idle: bool) -> Goal | None:
        if not isinstance(enabled, bool) or not isinstance(user_idle, bool):
            raise TypeError('Explicit boolean settings are required.')
        if not enabled or not user_idle:
            return None
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            row = db.execute('''SELECT * FROM interact_goals WHERE status='active'
                ORDER BY priority DESC, created_at ASC, id ASC LIMIT 1''').fetchone()
        return Goal(*row) if row else None

    def queue_message(self, *, message_id: str, goal_id: str,
                      evidence_id: str, content: str, at: datetime,
                      opted_in: bool, presence: str, mode: str) -> PendingMessage | None:
        """Never send a message. `away` must come from an actual client signal."""
        if not isinstance(opted_in, bool) or presence not in ('present', 'away', 'unknown'):
            raise ValueError('Explicit opt-in and an explicit presence signal are required.')
        if mode not in ('silent', 'queue_only'):
            raise ValueError('Only silent and queue-only modes are implemented.')
        if not opted_in or mode == 'silent' or presence != 'away':
            return None
        self._id(message_id, 'message_id')
        self._id(goal_id, 'goal_id')
        self._id(evidence_id, 'evidence_id')
        if not isinstance(content, str) or not content.strip() or len(content) > 320:
            raise ValueError('A bounded reviewed message is required.')
        queued = PendingMessage(message_id, goal_id, evidence_id, content.strip(),
                                self._time(at), 'queued')
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.execute('BEGIN IMMEDIATE')
            self._source(db, evidence_id)
            goal = db.execute('SELECT status FROM interact_goals WHERE id=?',
                              (goal_id,)).fetchone()
            if goal is None or goal[0] != 'active':
                raise ValueError('Only active recorded goals may queue messages.')
            old = db.execute('SELECT * FROM interact_queued_messages WHERE id=?',
                             (message_id,)).fetchone()
            if old is not None and old != tuple(vars(queued).values()):
                raise ValueError('Queued message ID was reused for different content.')
            if old is None:
                # Bounded pending outbox and per-goal cooldown. Identical IDs
                # replay above; a novel message cannot spam the same goal.
                pending_count = db.execute("SELECT COUNT(*) FROM interact_queued_messages "
                                           "WHERE status='queued'").fetchone()[0]
                latest = db.execute('''SELECT created_at FROM interact_queued_messages
                    WHERE goal_id=? ORDER BY created_at DESC LIMIT 1''',
                    (goal_id,)).fetchone()
                if pending_count >= 3:
                    return None
                if latest is not None and at.astimezone(timezone.utc) < (
                        datetime.fromisoformat(latest[0]) + timedelta(hours=6)):
                    return None
                db.execute('INSERT INTO interact_queued_messages VALUES (?,?,?,?,?,?)',
                           tuple(vars(queued).values()))
            db.commit()
        return queued

    def pending(self, *, limit: int = 10) -> tuple[PendingMessage, ...]:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError('Bounded outbox limit required.')
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            rows = db.execute('''SELECT * FROM interact_queued_messages
                WHERE status='queued' ORDER BY created_at, id LIMIT ?''',
                (limit,)).fetchall()
        return tuple(PendingMessage(*row) for row in rows)

    def cancel_message(self, message_id: str) -> None:
        self._id(message_id, 'message_id')
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            db.execute("UPDATE interact_queued_messages SET status='cancelled' "
                       "WHERE id=? AND status='queued'", (message_id,))
            db.commit()
