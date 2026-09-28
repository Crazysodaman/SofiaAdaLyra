"""Regression coverage for journal use across UI/Discord worker threads."""

from datetime import datetime, timezone
from threading import Thread

from sofia.personality.clarification import ClarificationJournal
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.reflection import ReflectionJournal


NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def _run_in_thread(action):
    errors = []

    def run():
        try:
            action()
        except BaseException as exc:  # Surface worker failures to pytest.
            errors.append(exc)

    worker = Thread(target=run)
    worker.start()
    worker.join(timeout=5)

    assert not worker.is_alive()
    if errors:
        raise errors[0]


def test_reflection_journal_created_on_one_thread_can_write_on_another(tmp_path):
    journal = ReflectionJournal(tmp_path / "state.db")

    _run_in_thread(
        lambda: journal.record_thought(
            thought_id="thread-reflection",
            kind="observation",
            subject="Cross-thread journal regression",
            content="A worker thread recorded this observation.",
            evidence_refs=("thread:test",),
            created_at=NOW,
        )
    )

    rows = journal.recent_thoughts(limit=5)
    assert rows[0].thought_id == "thread-reflection"


def test_clarification_journal_created_on_one_thread_can_write_on_another(tmp_path):
    state_path = tmp_path / "state.db"
    emotions = EmotionalJournal(state_path)
    emotions.record(
        event_id="thread-event",
        occurred_at=NOW,
        source="observed",
        evidence_ref="thread:test",
        description="Cross-thread clarification regression event.",
        emotions=("curiosity",),
    )
    journal = ClarificationJournal(state_path)

    _run_in_thread(
        lambda: journal.record(
            event_id="thread-event",
            message_id="thread-message",
            content="Worker-thread clarification.",
            created_at=NOW,
        )
    )

    rows = journal.recent(now=NOW)
    assert rows[0].event_id == "thread-event"
    assert rows[0].message_id == "thread-message"
