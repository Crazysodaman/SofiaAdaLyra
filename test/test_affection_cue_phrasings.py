"""Natural phrasing of an invited head pat is durable, never a physical observation."""
from datetime import datetime, timezone

import pytest

from sofia.personality.emotion import EmotionalJournal

NOW = datetime(2026, 9, 20, 19, tzinfo=timezone.utc)


@pytest.mark.parametrize("content", [
    "head pat", "Head pats", "pat pat", "Good girl.",
    "pats head", "pats your head", "pat her head", "pat the head",
    "so how are you feeling rn then pats head, and how are you feeling now",
    "*pats head*",
])
def test_positive_conversational_cues_without_required_asterisks(tmp_path, content):
    journal = EmotionalJournal(tmp_path / "sofia.db")
    assert journal.record_user_cue(message_id="user-1", content=content, occurred_at=NOW)
    assert journal.record_user_cue(message_id="user-1", content=content, occurred_at=NOW)
    event, = journal.recent(now=NOW)
    assert event.source == "user_reported"
    assert event.evidence_ref == "user-1"
    assert event.current_emotions == ("affection", "appreciation", "playfulness")


@pytest.mark.parametrize("content", [
    "don't pat her head", "do not pat your head", "never head pats",
    "not good girl", "```pats head```", "Are your logs okay?",
])
def test_negated_code_fenced_or_unrelated_text_does_not_create_cue(tmp_path, content):
    journal = EmotionalJournal(tmp_path / "sofia.db")
    assert not journal.record_user_cue(message_id="user-1", content=content, occurred_at=NOW)
    assert journal.recent(now=NOW) == ()
