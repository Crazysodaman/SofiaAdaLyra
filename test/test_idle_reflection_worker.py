"""Idle reflection uses recorded history; no Ollama, network or delivery."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import sqlite3

import pytest

from sofia.application.idle_reflection import IdleReflectionWorker
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.reflection import ReflectionJournal

NOW = datetime(2026, 9, 20, 14, tzinfo=timezone.utc)


def _fixture(tmp_path, *, busy=False, fail=False):
    path = tmp_path / "state.db"
    emotions = EmotionalJournal(path)
    reflections = ReflectionJournal(path)
    emotions.record(event_id="event-1", evidence_ref="real-1", source="observed",
                    description="A recorded change happened.", emotions=("curiosity",),
                    occurred_at=NOW - timedelta(days=2))
    calls = []

    def reflect(*, event_id):
        calls.append(event_id)
        if fail and len(calls) == 1:
            raise RuntimeError("synthetic model failure")
        reflections.record_thought(
            thought_id="thought:" + event_id, kind="reflection", subject="Recorded thought",
            content="The change warrants a later check.", evidence_refs=(event_id,),
            created_at=NOW,
        )

    service = SimpleNamespace(
        reflection_journal=reflections,
        emotional_journal=emotions,
        ready_for_idle_reflection=lambda *, idle_seconds: not busy,
        reflect_on_event=reflect,
    )
    worker = IdleReflectionWorker(service=service, state_path=path,
                                  poll_seconds=1, idle_seconds=1, retry_seconds=60)
    return worker, service, calls, path


def test_tick_creates_due_periods_and_one_reflection_once_across_restart(tmp_path):
    worker, service, calls, path = _fixture(tmp_path)
    assert worker.run_once(now=NOW) == "event-1"
    assert calls == ["event-1"]
    assert len(service.reflection_journal.recent_thoughts()) > 1
    assert worker.run_once(now=NOW) is None
    restarted = IdleReflectionWorker(service=service, state_path=path,
                                     poll_seconds=1, idle_seconds=1)
    assert restarted.run_once(now=NOW) is None
    assert calls == ["event-1"]
    assert service.reflection_journal.pending() == ()


def test_busy_conversation_defers_model_but_not_periodic_record(tmp_path):
    worker, service, calls, _ = _fixture(tmp_path, busy=True)
    assert worker.run_once(now=NOW) is None
    assert calls == []
    assert service.reflection_journal.recent_thoughts()


def test_failed_generation_persists_error_and_retries_without_spamming(tmp_path):
    worker, service, calls, path = _fixture(tmp_path, fail=True)
    with pytest.raises(RuntimeError, match="synthetic model failure"):
        worker.run_once(now=NOW)
    assert worker.last_error == "RuntimeError"
    assert worker.run_once(now=NOW + timedelta(seconds=59)) is None
    assert worker.run_once(now=NOW + timedelta(seconds=61)) == "event-1"
    assert calls == ["event-1", "event-1"]
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT status, last_error_type FROM idle_reflection_attempts").fetchone() == ("done", None)


def test_abandoned_claim_is_recoverable_and_duplicate_worker_does_not_claim(tmp_path):
    worker, service, calls, path = _fixture(tmp_path)
    assert worker._claim("event-1", NOW)
    another = IdleReflectionWorker(service=service, state_path=path,
                                   poll_seconds=1, idle_seconds=1)
    assert another.run_once(now=NOW + timedelta(minutes=1)) is None
    assert calls == []
    assert another.run_once(now=NOW + timedelta(minutes=11)) == "event-1"
    assert calls == ["event-1"]


def test_no_unrecorded_event_does_not_create_thought(tmp_path):
    path = tmp_path / "blank.db"
    emotions = EmotionalJournal(path)
    reflections = ReflectionJournal(path)
    service = SimpleNamespace(
        reflection_journal=reflections, emotional_journal=emotions,
        ready_for_idle_reflection=lambda *, idle_seconds: True,
        reflect_on_event=lambda **_: pytest.fail("No observation"),
    )
    worker = IdleReflectionWorker(service=service, state_path=path)
    assert worker.run_once(now=NOW) is None
    assert reflections.recent_thoughts() == ()


def test_stop_without_start_is_safe_and_start_twice_is_rejected(tmp_path):
    worker, _, _, _ = _fixture(tmp_path)
    worker.stop()
    worker.start()
    with pytest.raises(RuntimeError, match="already started"):
        worker.start()
    worker.stop(timeout_seconds=2)
    assert worker._thread is None



def test_idle_worker_observes_running_absence_before_selecting_event(tmp_path):
    path = tmp_path / "state.db"
    emotions = EmotionalJournal(path)
    reflections = ReflectionJournal(path)
    seen = []

    class Service:
        emotional_journal = emotions
        reflection_journal = reflections

        @staticmethod
        def ready_for_idle_reflection(*, idle_seconds):
            return True

        @staticmethod
        def observe_background_absence(*, now):
            seen.append(now)
            return None

        @staticmethod
        def reflect_on_event(*, event_id):
            return None

    worker = IdleReflectionWorker(service=Service(), state_path=path)
    assert worker.run_once(now=NOW) is None
    assert seen == [NOW]


def test_busy_worker_does_not_create_background_absence_appraisal(tmp_path):
    path = tmp_path / "state.db"
    emotions = EmotionalJournal(path)
    reflections = ReflectionJournal(path)
    seen = []

    class Service:
        emotional_journal = emotions
        reflection_journal = reflections

        @staticmethod
        def ready_for_idle_reflection(*, idle_seconds):
            return False

        @staticmethod
        def observe_background_absence(*, now):
            seen.append(now)
            return None

    worker = IdleReflectionWorker(service=Service(), state_path=path)
    assert worker.run_once(now=NOW) is None
    assert seen == []



def test_new_absence_milestone_is_reflected_before_older_backlog(tmp_path):
    path = tmp_path / "state.db"
    emotions = EmotionalJournal(path)
    reflections = ReflectionJournal(path)
    emotions.record(
        event_id="older", evidence_ref="old-evidence", source="observed",
        description="An older recorded event.", emotions=("curiosity",),
        occurred_at=NOW - timedelta(days=3),
    )
    calls = []

    class Service:
        emotional_journal = emotions
        reflection_journal = reflections

        @staticmethod
        def ready_for_idle_reflection(*, idle_seconds):
            return True

        @staticmethod
        def observe_background_absence(*, now):
            emotions.record(
                event_id="absence:new", evidence_ref="last-contact",
                source="inferred", description="Current absence milestone.",
                emotions=("longing",), occurred_at=now,
            )
            return "absence:new"

        @staticmethod
        def reflect_on_event(*, event_id):
            calls.append(event_id)

    worker = IdleReflectionWorker(service=Service(), state_path=path)

    assert worker.run_once(now=NOW) == "absence:new"
    assert calls == ["absence:new"]
