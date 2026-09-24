"""Opt-in, bounded idle reflection while Sofía's application remains running.

The worker only processes *recorded* emotional events. It does not inspect
systems, deliver messages, invent elapsed activity, or grant model authority.
An application-owned cognitive lock must serialize this with conversations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import sqlite3
from threading import Event, Thread
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sofia.application.emotional_conversation import EmotionalConversationService

_LOG = logging.getLogger(__name__)


class IdleReflectionWorker:
    """One worker per application; durable attempts avoid repeated model calls.

    A check interval is not a message quota. The outbox is unsent until a
    separate, authorized delivery adapter is installed.
    """

    def __init__(
        self, *, service: EmotionalConversationService, state_path: Path,
        poll_seconds: float = 90.0, idle_seconds: float = 45.0,
        retry_seconds: float = 600.0,
    ) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("A Path to the existing application state is required.")
        for label, value in (("poll", poll_seconds), ("idle", idle_seconds),
                             ("retry", retry_seconds)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 3600:
                raise ValueError(f"{label} seconds must be in (0, 3600].")
        self._service = service
        self._path = state_path
        self._poll_seconds = float(poll_seconds)
        self._idle_seconds = float(idle_seconds)
        self._retry_seconds = float(retry_seconds)
        self._stop_event = Event()
        self._thread: Thread | None = None
        self.last_error: str | None = None
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS idle_reflection_attempts (
                    event_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    next_retry_at TEXT,
                    last_error_type TEXT
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _claim(self, event_id: str, now: datetime) -> bool:
        """Atomically reserve an event, including recovery after a crash."""
        iso = now.isoformat()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status, claimed_at, next_retry_at FROM idle_reflection_attempts "
                "WHERE event_id=?", (event_id,),
            ).fetchone()
            if row is not None:
                status, claimed_at, retry_at = row
                if status == "done":
                    return False
                if status == "working" and now - datetime.fromisoformat(claimed_at) < timedelta(minutes=10):
                    return False
                if status == "failed" and retry_at is not None and now < datetime.fromisoformat(retry_at):
                    return False
            db.execute(
                "INSERT INTO idle_reflection_attempts "
                "(event_id, status, claimed_at, next_retry_at, last_error_type) "
                "VALUES (?, 'working', ?, NULL, NULL) "
                "ON CONFLICT(event_id) DO UPDATE SET status='working', "
                "claimed_at=excluded.claimed_at, next_retry_at=NULL, last_error_type=NULL",
                (event_id, iso),
            )
            return True

    def _finish(self, event_id: str, now: datetime, error: BaseException | None) -> None:
        with self._connect() as db:
            if error is None:
                db.execute(
                    "UPDATE idle_reflection_attempts SET status='done', next_retry_at=NULL, "
                    "last_error_type=NULL WHERE event_id=?", (event_id,),
                )
            else:
                db.execute(
                    "UPDATE idle_reflection_attempts SET status='failed', next_retry_at=?, "
                    "last_error_type=? WHERE event_id=?",
                    ((now + timedelta(seconds=self._retry_seconds)).isoformat(),
                     type(error).__name__, event_id),
                )

    def run_once(self, *, now: datetime | None = None) -> str | None:
        """Make completed-period summaries and process at most one due event.

        Never infer activity in unrecorded periods. Return the event ID that
        was attempted, or None if there is nothing to do or the user is active.
        Failures are persisted and raised to the caller, not silently swallowed.
        """
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("Worker time must be timezone-aware.")
        current = current.astimezone(timezone.utc)
        self._service.reflection_journal.reflect_due(now=current)
        if not self._service.ready_for_idle_reflection(idle_seconds=self._idle_seconds):
            return None
        if hasattr(self._service, "observe_background_absence"):
            self._service.observe_background_absence(now=current)
        # Existing journal has a bounded 50-event/366-day read contract.
        # Iterate oldest-first to keep an active burst from starving the
        # oldest event inside that window. General archival retrieval is K/23.
        events = reversed(self._service.emotional_journal.recent(
            now=current, days=366, limit=50,
        ))
        for event in events:
            if not self._claim(event.event_id, current):
                continue
            try:
                self._service.reflect_on_event(event_id=event.event_id)
            except Exception as exc:
                self.last_error = type(exc).__name__
                self._finish(event.event_id, current, exc)
                raise
            self._finish(event.event_id, current, None)
            self.last_error = None
            return event.event_id
        return None

    def _loop(self) -> None:
        # Give the user time to start talking before any initial model call.
        while not self._stop_event.wait(self._poll_seconds):
            try:
                self.run_once()
            except Exception:
                _LOG.exception("Idle reflection failed; recorded for a later retry")

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("Idle reflection worker already started.")
        self._stop_event.clear()
        thread = Thread(target=self._loop, name="sofia-idle-reflection", daemon=True)
        thread.start()
        self._thread = thread

    def stop(self, *, timeout_seconds: float = 180.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is None:
            return
        thread.join(timeout=timeout_seconds)
        if thread.is_alive():
            raise RuntimeError("Idle reflection has not stopped; runtime shutdown is unsafe.")
        self._thread = None
