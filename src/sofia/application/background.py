from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from threading import Event, Thread
from typing import Callable
from uuid import uuid4

from sofia.application.idle_reflection import IdleReflectionWorker
from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.habits.emotion_bridge import record_expectation_appraisals
from sofia.run.periodic import (
    OpportunityPolicy,
    PeriodicThoughtGate,
)


class BackgroundBudget:
    """Durable single-flight budget shared by application background work."""

    def __init__(
        self,
        state_path: Path,
        *,
        max_attempts_per_utc_day: int = 48,
    ) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be a Path")
        if type(max_attempts_per_utc_day) is not int or not (
            1 <= max_attempts_per_utc_day <= 288
        ):
            raise ValueError("max_attempts_per_utc_day must be in 1..288")
        self.path = state_path
        self.max_attempts_per_utc_day = max_attempts_per_utc_day
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS application_background_claims (
                        claim_id TEXT PRIMARY KEY,
                        task_kind TEXT NOT NULL,
                        claimed_at TEXT NOT NULL,
                        day_utc TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(
                            status IN ('working','done','failed')
                        ),
                        finished_at TEXT,
                        error_type TEXT
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def claim(self, task_kind: str, *, now: datetime) -> str | None:
        if not isinstance(task_kind, str) or not task_kind.strip():
            raise ValueError("task_kind must be nonempty")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                working = db.execute(
                    """
                    SELECT 1
                    FROM application_background_claims
                    WHERE status='working'
                    LIMIT 1
                    """
                ).fetchone()
                if working is not None:
                    return None
                count = db.execute(
                    """
                    SELECT COUNT(*)
                    FROM application_background_claims
                    WHERE day_utc=?
                    """,
                    (moment.date().isoformat(),),
                ).fetchone()[0]
                if count >= self.max_attempts_per_utc_day:
                    return None
                claim_id = str(uuid4())
                db.execute(
                    """
                    INSERT INTO application_background_claims (
                        claim_id, task_kind, claimed_at, day_utc,
                        status, finished_at, error_type
                    )
                    VALUES (?, ?, ?, ?, 'working', NULL, NULL)
                    """,
                    (
                        claim_id,
                        task_kind,
                        moment.isoformat(),
                        moment.date().isoformat(),
                    ),
                )
                return claim_id

    def finish(
        self,
        claim_id: str,
        *,
        now: datetime,
        error: BaseException | None = None,
    ) -> None:
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise ValueError("claim_id must be nonempty")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        status = "done" if error is None else "failed"
        with closing(self._connect()) as db:
            with db:
                changed = db.execute(
                    """
                    UPDATE application_background_claims
                    SET status=?, finished_at=?, error_type=?
                    WHERE claim_id=? AND status='working'
                    """,
                    (
                        status,
                        now.astimezone(timezone.utc).isoformat(),
                        None if error is None else type(error).__name__,
                        claim_id,
                    ),
                )
                if changed.rowcount != 1:
                    raise RuntimeError(
                        "background claim is missing or already finished"
                    )


class ApplicationBackgroundCoordinator:
    """
    Application-owned RUN coordinator.

    Foreground conversation has priority. At most one background unit runs at a
    time, with a durable global budget. ACT delivery is an optional host callback
    and is never enabled merely because a message exists.
    """

    def __init__(
        self,
        *,
        service: EmotionalConversationService,
        state_path: Path,
        poll_seconds: float = 90.0,
        idle_seconds: float = 45.0,
        opportunity_policy: OpportunityPolicy | None = None,
        reflection_enabled: bool = True,
        habit_enabled: bool = True,
    ) -> None:
        if not isinstance(service, EmotionalConversationService):
            raise TypeError("service must be an EmotionalConversationService")
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be a Path")
        if not isinstance(reflection_enabled, bool):
            raise TypeError("reflection_enabled must be boolean")
        if not isinstance(habit_enabled, bool):
            raise TypeError("habit_enabled must be boolean")
        if not isinstance(poll_seconds, (int, float)) or poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        if not isinstance(idle_seconds, (int, float)) or idle_seconds <= 0:
            raise ValueError("idle_seconds must be positive")
        self.service = service
        self.reflection_enabled = reflection_enabled
        self.habit_enabled = habit_enabled
        self.state_path = state_path
        self.poll_seconds = float(poll_seconds)
        self.idle_seconds = float(idle_seconds)
        self.budget = BackgroundBudget(state_path)
        self.idle = IdleReflectionWorker(
            service=service,
            state_path=state_path,
            poll_seconds=poll_seconds,
            idle_seconds=idle_seconds,
        )
        self.periodic = PeriodicThoughtGate(
            state_path,
            opportunity_policy
            or OpportunityPolicy(
                enabled=True,
                interval_seconds=max(300, int(poll_seconds)),
                max_attempts_per_utc_day=48,
            ),
        )
        self._act_delivery: Callable[[datetime], object | None] | None = None
        self._presentation_update: Callable[[datetime], object | None] | None = None
        self._presentation_interval = timedelta(hours=3)
        self._presentation_last_attempt: datetime | None = None
        self._stop_event = Event()
        self._thread: Thread | None = None
        self.last_error: str | None = None
        self._habit_last_tick: datetime | None = None

    def set_act_delivery(
        self,
        callback: Callable[[datetime], object | None] | None,
    ) -> None:
        if callback is not None and not callable(callback):
            raise TypeError("ACT delivery callback must be callable or None")
        self._act_delivery = callback

    def set_presentation_update(
        self,
        callback: Callable[[datetime], object | None] | None,
        *,
        interval: timedelta = timedelta(hours=3),
    ) -> None:
        if callback is not None and not callable(callback):
            raise TypeError(
                "presentation callback must be callable or None"
            )
        if (
            not isinstance(interval, timedelta)
            or interval < timedelta(minutes=30)
            or interval > timedelta(days=1)
        ):
            raise ValueError(
                "presentation interval must be between 30 minutes and one day"
            )
        self._presentation_update = callback
        self._presentation_interval = interval

    def _source_refs(self, now: datetime) -> tuple[str, ...]:
        absence = self.service.observe_background_absence(now=now)
        events = self.service.emotional_journal.recent(
            now=now,
            days=366,
            limit=16,
        )
        refs = [event.event_id for event in events]
        if absence is not None and absence not in refs:
            refs.insert(0, absence)
        return tuple(dict.fromkeys(refs))[:16]

    def run_once(self, *, now: datetime | None = None) -> str:
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

        principal = self.service.current_principal
        if self.habit_enabled and principal is not None:
            previous = self._habit_last_tick
            if previous is not None:
                self.service.habit_learning.record_running_coverage(
                    principal_id=principal.principal_id,
                    started_at=previous,
                    ended_at=moment,
                )
            self._habit_last_tick = moment
            resolved = self.service.habit_learning.evaluate(
                principal_id=principal.principal_id,
                now=moment,
            )
            if resolved:
                record_expectation_appraisals(
                    expectations=resolved,
                    store=self.service.habit_learning.store,
                    journal=self.service.emotional_journal,
                    at=moment,
                )
            snapshot = self.service._runtime.environment_service.snapshot(
                now=moment,
                refresh_providers=False,
            )
            self.service.habit_learning.expectations.ensure_time_expectations(
                principal_id=principal.principal_id,
                timezone_name=snapshot.timezone,
                now=moment,
            )

        if not self.service.ready_for_idle_reflection(
            idle_seconds=self.idle_seconds
        ):
            return "foreground_busy"

        presentation_due = (
            self._presentation_update is not None
            and (
                self._presentation_last_attempt is None
                or moment - self._presentation_last_attempt
                >= self._presentation_interval
            )
        )
        if presentation_due:
            claim_id = self.budget.claim(
                "avatar_presentation",
                now=moment,
            )
            if claim_id is None:
                return "budget_busy"
            try:
                result = self._presentation_update(moment)
                self._presentation_last_attempt = moment
                self.budget.finish(claim_id, now=moment)
                return (
                    "avatar_idle"
                    if result is None
                    else str(result)
                )
            except Exception as exc:
                self.budget.finish(
                    claim_id,
                    now=datetime.now(timezone.utc),
                    error=exc,
                )
                self.last_error = type(exc).__name__
                raise

        refs = self._source_refs(moment) if self.reflection_enabled else ()
        opportunity = (
            self.periodic.claim(
                now=moment,
                source_refs=refs,
                user_active=False,
            )
            if self.reflection_enabled
            else None
        )
        if opportunity is not None and opportunity.status == "claimed":
            claim_id = self.budget.claim("reflection", now=moment)
            if claim_id is None:
                self.periodic.finish(
                    opportunity.slot_id,
                    status="no_event",
                )
                return "budget_busy"
            try:
                event_id = self.idle.run_once(now=moment)
                if event_id is None:
                    self.periodic.finish(
                        opportunity.slot_id,
                        status="no_event",
                    )
                    self.budget.finish(claim_id, now=moment)
                    return "reflection_no_event"
                if event_id not in refs:
                    raise RuntimeError(
                        "background reflection returned unbudgeted evidence"
                    )
                self.periodic.finish(
                    opportunity.slot_id,
                    status="reflected",
                    event_id=event_id,
                )
                self.budget.finish(claim_id, now=moment)
                return "reflected"
            except Exception as exc:
                self.periodic.finish(
                    opportunity.slot_id,
                    status="failed",
                )
                self.budget.finish(
                    claim_id,
                    now=datetime.now(timezone.utc),
                    error=exc,
                )
                self.last_error = type(exc).__name__
                raise

        if self._act_delivery is not None:
            claim_id = self.budget.claim("act_delivery", now=moment)
            if claim_id is None:
                return "budget_busy"
            try:
                result = self._act_delivery(moment)
                self.budget.finish(claim_id, now=moment)
                return (
                    "act_idle"
                    if result is None
                    else "act_attempted"
                )
            except Exception as exc:
                self.budget.finish(
                    claim_id,
                    now=datetime.now(timezone.utc),
                    error=exc,
                )
                self.last_error = type(exc).__name__
                raise

        return "reflection_disabled" if opportunity is None else opportunity.status

    def _loop(self) -> None:
        while not self._stop_event.wait(self.poll_seconds):
            try:
                self.run_once()
                self.last_error = None
            except Exception as exc:
                self.last_error = type(exc).__name__

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("background coordinator already started")
        self._stop_event.clear()
        thread = Thread(
            target=self._loop,
            name="sofia-background-coordinator",
            daemon=True,
        )
        thread.start()
        self._thread = thread

    def stop(self, *, timeout_seconds: float = 180.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is None:
            return
        thread.join(timeout=timeout_seconds)
        if thread.is_alive():
            raise RuntimeError(
                "background coordinator did not stop safely"
            )
        self._thread = None
