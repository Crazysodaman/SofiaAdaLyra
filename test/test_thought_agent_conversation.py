"""Conversation reflection uses only selected recorded events, not an invented background life."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveResponse
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.reflection import ReflectionJournal


def _service(tmp_path, *, profile=True, active=True):
    path = tmp_path / "state.db"
    journal = EmotionalJournal(path)
    now = datetime.now(timezone.utc) - timedelta(minutes=1)
    journal.record(
        event_id="real-event", occurred_at=now, source="observed",
        evidence_ref="evidence-1", description="One observed file changed.",
        emotions=("curiosity",),
    )
    seen = []
    def respond(request):
        seen.append(request)
        return CognitiveResponse(content=json.dumps({
            "subject": "Change to investigate",
            "thought": "The change may be relevant to our next check.",
            "share": "later", "message": "", "urgency": "routine",
        }))
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(
        personality=object() if profile else None, respond=respond,
    )
    service._session = object() if active else None
    service._emotional_journal = journal
    service._reflection_journal = ReflectionJournal(path)
    return service, seen


def test_selected_real_event_generates_persisted_thought_without_delivery(tmp_path):
    service, seen = _service(tmp_path)
    outcome = service.reflect_on_event(event_id="real-event")
    assert outcome.thought_id is not None and outcome.queued_message_id is None
    assert len(seen) == 1
    stored = ReflectionJournal(tmp_path / "state.db")
    assert stored.recent_thoughts()[0].evidence_refs == ("real-event",)
    assert stored.pending() == ()
    service.reflect_on_event(event_id="real-event")
    assert len(seen) == 1


def test_unknown_event_never_reaches_model(tmp_path):
    service, seen = _service(tmp_path)
    with pytest.raises(KeyError, match="No matching"):
        service.reflect_on_event(event_id="invented")
    assert seen == []
    assert service.reflection_journal.recent_thoughts() == ()


@pytest.mark.parametrize("profile,active", [(False, True), (True, False)])
def test_personality_and_active_session_are_required(tmp_path, profile, active):
    service, seen = _service(tmp_path, profile=profile, active=active)
    with pytest.raises(RuntimeError):
        service.reflect_on_event(event_id="real-event")
    assert seen == []
