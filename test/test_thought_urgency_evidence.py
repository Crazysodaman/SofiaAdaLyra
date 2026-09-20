"""An emotion label, report or one observed incident cannot prove worsening."""
from datetime import datetime, timezone
import json

import pytest

from sofia.cognition.model import CognitiveResponse
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.reflection import ReflectionJournal
from sofia.personality.thought_agent import ThoughtAgent, ThoughtGenerationError

NOW = datetime(2026, 9, 20, 20, tzinfo=timezone.utc)


def _fixture(tmp_path, source="observed"):
    path = tmp_path / "state.db"
    events = EmotionalJournal(path)
    events.record(event_id="single-incident", source=source,
                  evidence_ref="incident-record", description="One service error was recorded.",
                  emotions=("concern",), occurred_at=NOW)
    return ReflectionJournal(path), events.recent(now=NOW)[0]


def _urgent(_):
    return CognitiveResponse(content=json.dumps({
        "subject": "Single incident", "thought": "The cause is unknown.",
        "share": "now", "message": "One error was recorded.", "urgency": "urgent",
    }))


def test_observed_single_incident_is_not_verified_worsening(tmp_path):
    journal, event = _fixture(tmp_path)
    with pytest.raises(ThoughtGenerationError, match="non-worsening"):
        ThoughtAgent(generate=_urgent, reflections=journal).reflect(event=event, now=NOW)
    assert journal.recent_thoughts() == ()
    assert journal.pending() == ()


def test_explicitly_verified_observed_worsening_allows_urgent_outbox_not_delivery(tmp_path):
    journal, event = _fixture(tmp_path)
    payloads = []
    def generate(request):
        payloads.append(request.messages[0].content)
        return _urgent(request)
    result = ThoughtAgent(generate=generate, reflections=journal).reflect(
        event=event, now=NOW, verified_worsening=True,
    )
    assert '"verified_worsening": true' in payloads[0]
    assert result.queued_message_id is not None
    assert journal.pending()[0].urgency == "urgent"
    assert journal.pending()[0].status == "pending"


def test_user_report_cannot_assert_verified_worsening(tmp_path):
    journal, event = _fixture(tmp_path, source="user_reported")
    agent = ThoughtAgent(generate=lambda _: pytest.fail("Must reject before model"),
                         reflections=journal)
    with pytest.raises(ValueError, match="Unverified"):
        agent.reflect(event=event, now=NOW, verified_worsening=True)
    with pytest.raises(TypeError, match="bool"):
        agent.reflect(event=event, now=NOW, verified_worsening="true")
    assert journal.pending() == ()
