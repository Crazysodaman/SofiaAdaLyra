"""Trusted observation bridge tests; no fabricated remote observations or LLM."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.filesystem.changes import FilesystemChange, FilesystemChangeEvent, FilesystemChangeKind
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.observation_bridge import (
    record_user_reappraisal, record_verified_test_run, record_workspace_observation,
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


def test_verified_test_result_and_original_appraisal_survive_user_correction(tmp_path):
    emotions, reflections = _stores(tmp_path)
    event_id = record_verified_test_run(
        run_id="pytest-123", evidence_ref="trusted-run-123", completed_at=NOW,
        passed=26, failed=1, skipped=0, emotions=emotions, reflections=reflections,
    )
    record_user_reappraisal(
        event_id=event_id, message_id="user-msg-1",
        clarification="The failure was expected by the test harness.",
        new_emotions=("relief", "curiosity"), revised_at=NOW + timedelta(minutes=1),
        journal=emotions,
    )
    found = EmotionalJournal(tmp_path / "sofia.db").recent(now=NOW + timedelta(minutes=2))[0]
    assert found.original_emotions == ("concern", "curiosity", "determination")
    assert found.current_emotions == ("relief", "curiosity")
    assert found.revision_count == 1
    assert len(reflections.recent_thoughts()) == 1
    assert "26 passed, 1 failed" in reflections.recent_thoughts()[0].content
    assert reflections.pending() == ()
    assert record_verified_test_run(
        run_id="pytest-123", evidence_ref="trusted-run-123", completed_at=NOW,
        passed=26, failed=1, skipped=0, emotions=emotions, reflections=reflections,
    ) == event_id
    assert len(emotions.recent(now=NOW)) == 1


def test_result_validation_and_conflicting_ids_fail_closed(tmp_path):
    emotions, reflections = _stores(tmp_path)
    params = dict(run_id="a", evidence_ref="b", completed_at=NOW,
                  passed=1, failed=0, skipped=0, emotions=emotions,
                  reflections=reflections)
    assert record_verified_test_run(**params) == "test-run:a"
    with pytest.raises(ValueError, match="different evidence"):
        record_verified_test_run(**{**params, "failed": 1})
    with pytest.raises(ValueError, match="empty test result"):
        record_verified_test_run(**{**params, "passed": 0})
    with pytest.raises(ValueError, match="nonnegative integers"):
        record_verified_test_run(**{**params, "passed": True})
    with pytest.raises(ValueError, match="timezone-aware"):
        record_verified_test_run(**{**params, "completed_at": NOW.replace(tzinfo=None)})


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
