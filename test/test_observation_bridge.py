"""Trusted observation bridge tests; no fabricated remote observations or LLM."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.filesystem.changes import FilesystemChange, FilesystemChangeEvent, FilesystemChangeKind
from sofia.emotion.journal import EmotionalJournal
from sofia.personality.observation_bridge import (
    record_workspace_observation,
)
from sofia.personality.reflection import ReflectionJournal

UTC = timezone.utc
NOW = datetime(2026, 9, 20, 12, tzinfo=UTC)


def _workspace(*, baseline=True, removed=False):
    change = FilesystemChange(
        kind=FilesystemChangeKind.REMOVED if removed else FilesystemChangeKind.NEW,
        path=Path("src/sofia/example.py"),
        previous=object() if removed else None,
        current=None if removed else object(),
    )
    return FilesystemChangeEvent(
        previous_observed_at=NOW - timedelta(minutes=5) if baseline else None,
        current_observed_at=NOW,
        new=(change,) if not removed and baseline else (),
        modified=(),
        removed=(change,) if removed and baseline else (),
        baseline_available=baseline,
    )


def _stores(tmp_path):
    path = tmp_path / "sofia.db"
    return EmotionalJournal(path), ReflectionJournal(path)


def test_real_workspace_delta_records_one_grounded_event_and_thought(tmp_path):
    emotions, reflections = _stores(tmp_path)
    event_id = record_workspace_observation(
        event=_workspace(removed=True), emotions=emotions, reflections=reflections,
    )
    assert event_id.startswith("workspace-change:")
    assert record_workspace_observation(
        event=_workspace(removed=True), emotions=emotions, reflections=reflections,
    ) == event_id
    entries = EmotionalJournal(tmp_path / "sofia.db").recent(now=NOW)
    assert len(entries) == 1
    assert entries[0].source == "observed"
    assert entries[0].original_emotions == ("curiosity", "caution")
    assert "1 removed" in entries[0].description
    thoughts = ReflectionJournal(tmp_path / "sofia.db").recent_thoughts()
    assert len(thoughts) == 1 and thoughts[0].evidence_refs == (event_id,)
    assert "not established" in thoughts[0].content
    assert reflections.pending() == ()


def test_no_baseline_means_no_observed_changes(tmp_path):
    emotions, reflections = _stores(tmp_path)
    assert record_workspace_observation(
        event=_workspace(baseline=False), emotions=emotions, reflections=reflections,
    ) is None
    assert emotions.recent(now=NOW) == ()
    assert reflections.recent_thoughts() == ()






def test_application_open_ingests_only_actual_workspace_delta(monkeypatch, tmp_path):
    from sofia.application.conversation_service import ConversationService
    from sofia.application.emotional_conversation import EmotionalConversationService

    monkeypatch.setattr(ConversationService, "open", lambda self: None)
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(
        personality=object(), workspace_changes=_workspace(),
        configuration=SimpleNamespace(state_path=tmp_path / "sofia.db"),
    )
    service._emotional_journal = None
    service._reflection_journal = None
    service.open()
    assert len(service.emotional_journal.recent(now=NOW)) == 1
    assert len(service.reflection_journal.recent_thoughts()) == 1


def test_open_without_personality_does_not_infer_emotion(monkeypatch, tmp_path):
    from sofia.application.conversation_service import ConversationService
    from sofia.application.emotional_conversation import EmotionalConversationService

    monkeypatch.setattr(ConversationService, "open", lambda self: None)
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(
        personality=None, workspace_changes=_workspace(),
        configuration=SimpleNamespace(state_path=tmp_path / "sofia.db"),
    )
    service._emotional_journal = None
    service._reflection_journal = None
    service.open()
    assert service.emotional_journal.recent(now=NOW) == ()
