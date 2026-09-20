"""Model reflection is evidence-bound, opt-in, and never a delivery action."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.cognition.model import CognitiveResponse, CognitiveToolCall, CognitiveRole
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.reflection import ReflectionJournal
from sofia.personality.thought_agent import ThoughtAgent, ThoughtGenerationError

NOW = datetime(2026, 9, 20, 18, tzinfo=timezone.utc)


def _setup(tmp_path, *, source="observed"):
    path = tmp_path / "state.db"
    emotions = EmotionalJournal(path)
    emotions.record(event_id="reboot-1", source=source, evidence_ref="artemis-reboots",
                    description="One reboot was recorded; the cause is unknown.",
                    emotions=("concern", "curiosity"), occurred_at=NOW)
    event = emotions.recent(now=NOW)[0]
    return ReflectionJournal(path), event


def _output(*, share="now", urgency="excited", thought="This may warrant checking the restart logs.",
            message="Sparks, I noticed a reboot. The cause is still unknown. Want to investigate?"):
    return json.dumps({"subject": "Artemis restart", "thought": thought,
                       "share": share, "message": message if share == "now" else "",
                       "urgency": urgency})


def test_new_insight_is_recorded_and_queued_but_not_delivered(tmp_path):
    store, event = _setup(tmp_path)
    requests = []
    def generate(request):
        requests.append(request)
        return CognitiveResponse(content=_output())
    agent = ThoughtAgent(generate=generate, reflections=store)
    result = agent.reflect(event=event, now=NOW + timedelta(minutes=2))
    assert result.thought_id.startswith("model-reflection:")
    assert result.queued_message_id
    assert len(requests) == 1 and requests[0].messages[0].role is CognitiveRole.SYSTEM
    assert "observed" in requests[0].messages[0].content
    assert "No tools" in requests[0].messages[0].content
    assert store.recent_thoughts()[0].evidence_refs == (event.event_id,)
    assert store.recent_thoughts()[0].emotions == event.current_emotions
    pending = ReflectionJournal(tmp_path / "state.db").pending()
    assert len(pending) == 1 and pending[0].message_id == result.queued_message_id
    assert pending[0].status == "pending"
    assert agent.reflect(event=event, now=NOW + timedelta(minutes=3)).queued_message_id is None
    assert len(requests) == 1 and len(store.pending()) == 1


def test_quiet_thought_stays_in_journal_without_message(tmp_path):
    store, event = _setup(tmp_path)
    agent = ThoughtAgent(generate=lambda _: CognitiveResponse(content=_output(share="later")),
                         reflections=store)
    result = agent.reflect(event=event, now=NOW)
    assert result.thought_id and result.queued_message_id is None
    assert len(ReflectionJournal(tmp_path / "state.db").recent_thoughts()) == 1
    assert store.pending() == ()


def test_abstain_does_not_create_made_up_memories(tmp_path):
    store, event = _setup(tmp_path)
    answer = json.dumps({"subject": "", "thought": "", "share": "none",
                         "message": "", "urgency": "routine"})
    result = ThoughtAgent(generate=lambda _: CognitiveResponse(content=answer),
                          reflections=store).reflect(event=event, now=NOW)
    assert result.thought_id is None and store.recent_thoughts() == ()


@pytest.mark.parametrize("answer", [
    "not json", "```json\n{}\n```", "{}",
    _output(share="later").replace('"share": "later"', '"share": "maybe"'),
    _output(thought="invented\nactual action"),
    _output(share="later").replace('"message": ""', '"message": "Do this"'),
])
def test_malformed_responses_fail_closed_without_writes(tmp_path, answer):
    store, event = _setup(tmp_path)
    agent = ThoughtAgent(generate=lambda _: CognitiveResponse(content=answer),
                         reflections=store)
    with pytest.raises(ThoughtGenerationError):
        agent.reflect(event=event, now=NOW)
    assert store.recent_thoughts() == () and store.pending() == ()


def test_tool_calls_are_rejected_without_execution(tmp_path):
    store, event = _setup(tmp_path)
    response = CognitiveResponse(content=_output(), tool_calls=(
        CognitiveToolCall(name="execute", arguments={"command": "noop"}),
    ))
    with pytest.raises(ThoughtGenerationError, match="text-only"):
        ThoughtAgent(generate=lambda _: response, reflections=store).reflect(event=event, now=NOW)
    assert store.pending() == ()


def test_unverified_user_report_cannot_trigger_urgent_message(tmp_path):
    store, event = _setup(tmp_path, source="user_reported")
    with pytest.raises(ThoughtGenerationError, match="Unverified"):
        ThoughtAgent(generate=lambda _: CognitiveResponse(content=_output(urgency="urgent")),
                     reflections=store).reflect(event=event, now=NOW)
    assert store.recent_thoughts() == () and store.pending() == ()


def test_future_event_and_naive_clock_are_rejected_before_model_call(tmp_path):
    store, event = _setup(tmp_path)
    def generate(_):
        raise AssertionError("Model must not be called")
    agent = ThoughtAgent(generate=generate, reflections=store)
    with pytest.raises(ValueError, match="future"):
        agent.reflect(event=event, now=NOW - timedelta(seconds=1))
    with pytest.raises(ValueError, match="timezone-aware"):
        agent.reflect(event=event, now=NOW.replace(tzinfo=None))
