"""Regression: emotional conversation startup accepts configured string DB paths."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from sofia.application.conversation_service import ConversationService
from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.filesystem.changes import FilesystemChangeEvent
from sofia.personality.clarification import ClarificationJournal
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.reflection import ReflectionJournal


def test_string_state_path_opens_emotional_journals_and_observation_bridge(
    tmp_path: Path, monkeypatch,
) -> None:
    # Isolate just the emotional startup boundary; application integration
    # tests separately exercise the real conversation store and runtime.
    monkeypatch.setattr(ConversationService, "open", lambda self: None)
    event = FilesystemChangeEvent(
        previous_observed_at=None,
        current_observed_at=datetime.now(timezone.utc),
        new=(), modified=(), removed=(), baseline_available=False,
    )
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(
        configuration=SimpleNamespace(state_path=str(tmp_path / "sofia.db")),
        personality=object(), workspace_changes=event,
    )
    service._emotional_journal = None
    service._reflection_journal = None
    service._clarification_journal = None

    service.open()

    assert isinstance(service.emotional_journal, EmotionalJournal)
    assert isinstance(service.reflection_journal, ReflectionJournal)
    assert isinstance(service.clarification_journal, ClarificationJournal)
    assert service.emotional_journal.recent(now=datetime.now(timezone.utc)) == ()
