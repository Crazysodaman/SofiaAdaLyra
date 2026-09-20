"""Prevent Sofía's own journal writes from becoming endless emotional events."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from sofia.filesystem.changes import FilesystemChange, FilesystemChangeEvent, FilesystemChangeKind
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.observation_bridge import record_workspace_observation
from sofia.personality.reflection import ReflectionJournal

NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


def _change(path):
    return FilesystemChange(
        kind=FilesystemChangeKind.MODIFIED, path=path,
        previous=object(), current=object(),
    )


def _event(*paths):
    return FilesystemChangeEvent(
        previous_observed_at=NOW - timedelta(minutes=2), current_observed_at=NOW,
        new=(), modified=tuple(_change(p) for p in paths), removed=(),
        baseline_available=True,
    )


def test_only_state_database_and_sidecars_produce_no_emotion_or_thought(tmp_path):
    state = tmp_path / "sofia.db"
    emotions = EmotionalJournal(state)
    reflections = ReflectionJournal(state)
    event = _event(state, *(Path(str(state) + suffix) for suffix in ("-wal", "-shm", "-journal")))
    assert record_workspace_observation(
        event=event, emotions=emotions, reflections=reflections,
        ignored_paths=(state,),
    ) is None
    assert emotions.recent(now=NOW) == ()
    assert reflections.recent_thoughts() == ()


def test_real_change_survives_noise_exclusion_and_remains_idempotent(tmp_path):
    state = tmp_path / "sofia.db"
    real = tmp_path / "src" / "real.py"
    emotions = EmotionalJournal(state)
    reflections = ReflectionJournal(state)
    event = _event(state, Path(str(state) + "-wal"), real)
    first = record_workspace_observation(
        event=event, emotions=emotions, reflections=reflections,
        ignored_paths=(state,),
    )
    assert first is not None
    assert record_workspace_observation(
        event=event, emotions=emotions, reflections=reflections,
        ignored_paths=(state,),
    ) == first
    saved = emotions.recent(now=NOW)
    assert len(saved) == 1
    assert "1 modified" in saved[0].description
    assert "3 modified" not in saved[0].description
    assert len(reflections.recent_thoughts()) == 1


def test_application_open_does_not_journal_only_its_own_state_change(monkeypatch, tmp_path):
    from sofia.application.conversation_service import ConversationService
    from sofia.application.emotional_conversation import EmotionalConversationService

    state = tmp_path / "sofia.db"
    monkeypatch.setattr(ConversationService, "open", lambda self: None)
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(
        personality=object(), workspace_changes=_event(state),
        configuration=SimpleNamespace(state_path=state),
    )
    service._emotional_journal = None
    service._reflection_journal = None
    service.open()
    assert service.emotional_journal.recent(now=NOW) == ()
    assert service.reflection_journal.recent_thoughts() == ()
