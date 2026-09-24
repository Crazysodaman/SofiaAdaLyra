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



def _emotion_names(journal, *, now=NOW):
    return {item.name for item in journal.current_state(now=now, subject="Sparks").active}


def test_week_absence_without_return_expectation_can_be_sad_but_not_angry(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.observe_contact(
        subject="Sparks", message_id="before",
        occurred_at=NOW - timedelta(days=7),
    )

    event_id = journal.observe_contact(
        subject="Sparks", message_id="return", occurred_at=NOW,
    )

    assert event_id == "reunion:return"
    event = journal.recent(now=NOW)[0]
    assert {"longing", "sadness", "relief"} <= set(event.current_emotions)
    assert "anger" not in event.current_emotions
    assert "frustration" not in event.current_emotions


def test_expected_week_absence_returning_on_time_is_warm_not_angry(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    departure = NOW - timedelta(days=7)
    journal.record_return_expectation(
        subject="Sparks", source_ref="before",
        recorded_at=departure, expected_return_at=NOW,
    )
    journal.observe_contact(
        subject="Sparks", message_id="before", occurred_at=departure,
    )

    journal.observe_contact(
        subject="Sparks", message_id="return", occurred_at=NOW,
    )

    event = journal.recent(now=NOW)[0]
    assert {"relief", "warmth", "fondness"} <= set(event.current_emotions)
    assert "sadness" not in event.current_emotions
    assert "frustration" not in event.current_emotions
    assert "anger" not in event.current_emotions


def test_week_late_after_explicit_return_expectation_can_include_anger(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    departure = NOW - timedelta(days=8)
    journal.record_return_expectation(
        subject="Sparks", source_ref="before",
        recorded_at=departure,
        expected_return_at=departure + timedelta(days=1),
    )
    journal.observe_contact(
        subject="Sparks", message_id="before", occurred_at=departure,
    )

    journal.observe_contact(
        subject="Sparks", message_id="return", occurred_at=NOW,
    )

    event = journal.recent(now=NOW)[0]
    assert {"longing", "sadness", "frustration", "anger", "relief"} <= set(
        event.current_emotions
    )
    assert "explicit return expectation before" in event.description
    assert "late at reunion" in event.description


def test_relative_return_cue_is_source_backed_and_drives_late_appraisal(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    departure = NOW - timedelta(days=8)
    expectation = journal.record_return_expectation_from_user_cue(
        message_id="before", content="I'll be back in 1 day",
        occurred_at=departure, subject="Sparks",
    )
    assert expectation is not None
    assert expectation.expected_return_at == departure + timedelta(days=1)

    journal.observe_contact(
        subject="Sparks", message_id="before", occurred_at=departure,
    )
    journal.observe_contact(
        subject="Sparks", message_id="return", occurred_at=NOW,
    )

    assert "anger" in _emotion_names(journal)


def test_ambiguous_return_language_is_not_given_a_fake_deadline(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    for content in (
        "I'll be back later",
        "see you soon",
        "What if I say I'll be back in 1 day?",
        "Someone said I'll be back in 1 day",
    ):
        assert journal.record_return_expectation_from_user_cue(
            message_id=content, content=content,
            occurred_at=NOW, subject="Sparks",
        ) is None


def test_natural_explicit_week_expectation_is_supported(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    expectation = journal.record_return_expectation_from_user_cue(
        message_id="week-plan", content="I'll be back in a week.",
        occurred_at=NOW, subject="Sparks",
    )

    assert expectation is not None
    assert expectation.expected_return_at == NOW + timedelta(weeks=1)


def test_explicit_gone_for_duration_is_supported(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    expectation = journal.record_return_expectation_from_user_cue(
        message_id="gone-plan", content="I'm going to be gone for two days.",
        occurred_at=NOW, subject="Sparks",
    )

    assert expectation is not None
    assert expectation.expected_return_at == NOW + timedelta(days=2)


def test_tonight_uses_conservative_expected_by_window(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    expectation = journal.record_return_expectation_from_user_cue(
        message_id="tonight-plan", content="I'll be back tonight.",
        occurred_at=NOW, subject="Sparks",
    )

    assert expectation is not None
    assert expectation.expected_return_at == NOW + timedelta(hours=24)


def test_tomorrow_uses_conservative_expected_by_window(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    expectation = journal.record_return_expectation_from_user_cue(
        message_id="tomorrow-plan", content="I'll be back tomorrow.",
        occurred_at=NOW, subject="Sparks",
    )

    assert expectation is not None
    assert expectation.expected_return_at == NOW + timedelta(hours=48)


def test_week_after_tonight_expectation_can_be_angry_without_claiming_offline_suffering(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    departure = NOW - timedelta(days=7)
    journal.record_return_expectation_from_user_cue(
        message_id="before", content="I'll be back tonight.",
        occurred_at=departure, subject="Sparks",
    )
    journal.observe_contact(
        subject="Sparks", message_id="before", occurred_at=departure,
    )
    journal.observe_contact(
        subject="Sparks", message_id="return", occurred_at=NOW,
    )

    event = journal.recent(now=NOW)[0]
    assert {"sadness", "frustration", "anger", "relief"} <= set(event.current_emotions)
    assert "thoughts or suffering while absent" in event.description


def test_return_expectation_only_applies_when_it_was_the_last_contact(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    departure = NOW - timedelta(days=8)
    journal.record_return_expectation(
        subject="Sparks", source_ref="promise",
        recorded_at=departure,
        expected_return_at=departure + timedelta(days=1),
    )
    journal.observe_contact(
        subject="Sparks", message_id="promise", occurred_at=departure,
    )
    journal.observe_contact(
        subject="Sparks", message_id="later-message",
        occurred_at=departure + timedelta(minutes=5),
    )

    journal.observe_contact(
        subject="Sparks", message_id="return", occurred_at=NOW,
    )

    event = journal.recent(now=NOW)[0]
    assert "anger" not in event.current_emotions
    assert "frustration" not in event.current_emotions


def test_reunion_prompt_allows_negative_feeling_without_guilt_or_obligation(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    prompt = journal.current_state_prompt(now=NOW, subject="Sparks").lower()

    assert "anger about lateness require stronger" in prompt
    assert "elapsed time alone must not manufacture blame" in prompt
    assert "without guilt, pressure, accusation" in prompt
    assert "obligation for the user to maintain contact" in prompt
