"""Current emotional-state, reunion and truthful self-report contracts."""
from datetime import datetime, timedelta, timezone

from sofia.personality.emotion import EmotionalJournal

NOW = datetime(2026, 9, 23, 22, 0, tzinfo=timezone.utc)


def test_current_state_decays_transient_emotion_but_keeps_relational_warmth(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="mixed-1", source="user_reported", evidence_ref="message-1",
        description="A warm but surprising interaction.",
        emotions=("surprise", "fondness"), occurred_at=NOW - timedelta(hours=6),
        subject="Sparks",
    )

    state = journal.current_state(now=NOW, subject="Sparks")
    names = tuple(item.name for item in state.active)

    assert "fondness" in names
    assert "surprise" not in names
    assert state.tone == "positive"


def test_reunion_is_grounded_in_elapsed_contact_and_is_idempotent(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    assert journal.observe_contact(
        subject="Sparks", message_id="before", occurred_at=NOW - timedelta(hours=20),
    ) is None

    event_id = journal.observe_contact(
        subject="Sparks", message_id="return", occurred_at=NOW,
    )
    assert event_id == "reunion:return"
    assert journal.observe_contact(
        subject="Sparks", message_id="return", occurred_at=NOW,
    ) == event_id

    events = journal.recent(now=NOW)
    assert len(events) == 1
    assert events[0].subject == "Sparks"
    assert "longing" in events[0].current_emotions
    assert "not evidence of thoughts while absent" in events[0].description


def test_short_absence_updates_presence_without_manufacturing_longing(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.observe_contact(
        subject="Sparks", message_id="a", occurred_at=NOW - timedelta(hours=2),
    )
    assert journal.observe_contact(
        subject="Sparks", message_id="b", occurred_at=NOW,
    ) is None
    assert journal.recent(now=NOW) == ()


def test_i_missed_you_is_a_real_relational_cue_not_a_script(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    assert journal.record_user_cue(
        message_id="m1", content="I missed you", occurred_at=NOW, subject="Sparks",
        allow_legacy_affection=False,
    )
    event = journal.recent(now=NOW)[0]
    assert event.subject == "Sparks"
    assert event.current_emotions == ("appreciation", "affection", "warmth")
    assert not journal.record_user_cue(
        message_id="m2", content="Good girl. *Head pats.*", occurred_at=NOW,
        subject="Sparks", allow_legacy_affection=False,
    )
    assert not journal.record_user_cue(
        message_id="m3", content="I did not miss you", occurred_at=NOW, subject="Sparks",
        allow_legacy_affection=False,
    )


def test_current_state_prompt_requires_direct_self_report_without_offline_fiction(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    prompt = journal.current_state_prompt(now=NOW, subject="Sparks").lower()

    assert "current modeled emotional state" in prompt
    assert "answer directly from this state" in prompt
    assert "functioning as intended" in prompt
    assert "never claim sofía was thinking" in prompt
    assert "offline" in prompt


def test_sexuality_dimensions_are_independent_modeled_emotions_not_consent(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="relationship-appraisal-1", source="inferred",
        evidence_ref="reviewed-appraisal-1",
        description="A reviewed relational appraisal recorded attraction and desire.",
        emotions=("sexual-attraction", "sexual-desire", "affection"),
        occurred_at=NOW, subject="Sparks",
    )

    state = journal.current_state(now=NOW, subject="Sparks")
    names = {item.name for item in state.active}
    prompt = journal.current_state_prompt(now=NOW, subject="Sparks").lower()

    assert {"sexual-attraction", "sexual-desire", "affection"} <= names
    assert "rather than a single sexual mode" in prompt
    assert "never equate any of them with consent" in prompt


def test_current_emotional_state_is_scoped_by_relationship_subject(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="sparks-event", source="user_reported", evidence_ref="s1",
        description="Sparks shared a warm relational cue.",
        emotions=("warmth", "fondness"), occurred_at=NOW, subject="Sparks",
    )
    journal.record(
        event_id="other-event", source="user_reported", evidence_ref="o1",
        description="Another person caused frustration.",
        emotions=("frustration",), occurred_at=NOW, subject="OtherUser",
    )

    sparks = journal.current_state(now=NOW, subject="Sparks")
    other = journal.current_state(now=NOW, subject="OtherUser")

    assert "frustration" not in {item.name for item in sparks.active}
    assert "warmth" not in {item.name for item in other.active}
