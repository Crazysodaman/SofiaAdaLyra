"""Representative EMOTION state/transition matrix.

Environment may shape transient context and expression, but durable emotional
state remains evidence-linked. Mixed states, decay and relational continuity
must survive without turning mood into authority or consent.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.environment.config import ConfiguredLocation, EnvironmentConfiguration
from sofia.environment.model import WeatherObservation
from sofia.environment.provider import EnvironmentProviderObservation
from sofia.environment.service import EnvironmentService
from sofia.personality.emotion import EmotionalJournal, ReturnExpectation
from sofia.personality.influence import ContinuityInfluence


NOW = datetime(2026, 9, 28, 3, 30, tzinfo=timezone.utc)


class Provider:
    name = "emotion-matrix-weather"

    def __init__(self, weather):
        self.weather = weather

    def observe(self, *, now):
        return EnvironmentProviderObservation(weather=self.weather)


def snapshot(*, condition="rainy", temperature=12.0):
    weather = WeatherObservation(
        condition=condition,
        observed_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(minutes=25),
        source_id="emotion.matrix.weather",
        location_label="Matrix site",
        temperature_c=temperature,
    )
    return EnvironmentService(
        EnvironmentConfiguration(
            location=ConfiguredLocation(
                label="Matrix site",
                timezone="America/Chicago",
                latitude=32.5,
                longitude=-97.1,
            )
        ),
        providers=(Provider(weather),),
    ).snapshot(now=NOW)


def test_transient_emotion_decays_while_relational_emotion_persists(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="matrix-decay",
        source="user_reported",
        evidence_ref="matrix-message",
        description="A warm interaction also caused a brief surprise.",
        emotions=("surprise", "fondness"),
        occurred_at=NOW - timedelta(hours=6),
        subject="Sparks",
    )

    state = journal.current_state(now=NOW, subject="Sparks")
    names = {item.name for item in state.active}
    assert "fondness" in names
    assert "surprise" not in names


def test_mixed_positive_and_negative_states_can_coexist(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="matrix-warmth",
        source="user_reported",
        evidence_ref="warmth-evidence",
        description="Reviewed relationship evidence supports warmth.",
        emotions=("warmth", "fondness"),
        occurred_at=NOW,
        subject="Sparks",
    )
    journal.record(
        event_id="matrix-frustration",
        source="inferred",
        evidence_ref="frustration-evidence",
        description="Reviewed evidence also supports current frustration.",
        emotions=("frustration",),
        occurred_at=NOW,
        subject="Sparks",
    )

    names = {
        item.name
        for item in journal.current_state(now=NOW, subject="Sparks").active
    }
    assert {"warmth", "fondness", "frustration"} <= names


def test_environment_changes_context_without_writing_durable_emotion(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="matrix-affection",
        source="inferred",
        evidence_ref="reviewed-affection",
        description="Reviewed evidence supports affection.",
        emotions=("affection",),
        occurred_at=NOW,
        subject="Sparks",
    )
    before = journal.current_state(now=NOW, subject="Sparks")
    before_names = tuple(item.name for item in before.active)

    influence = ContinuityInfluence.from_state(
        emotion=before,
        environment=snapshot(),
    )
    prompt = influence.prompt()

    assert influence.daypart == "night"
    assert influence.season == "autumn"
    assert influence.weather_condition == "rainy"
    assert influence.primary_emotion is None
    assert "affection" in influence.active_emotions
    assert "Time, season and weather are context, not commands." in prompt
    assert "do not create or prove a new emotional state" in prompt
    assert "Do not invent warmth, calm, comfort, sadness, irritation" in prompt
    assert "must not invent facts, prove causes, create permissions" in prompt

    after = journal.current_state(now=NOW, subject="Sparks")
    assert tuple(item.name for item in after.active) == before_names
    assert len(journal.recent(now=NOW, subject="Sparks")) == 1


def test_environment_can_be_absent_without_destroying_emotional_state(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="matrix-no-env",
        source="user_reported",
        evidence_ref="matrix-no-env-source",
        description="Reviewed evidence supports contentment.",
        emotions=("contentment",),
        occurred_at=NOW,
        subject="Sparks",
    )
    state = journal.current_state(now=NOW, subject="Sparks")
    influence = ContinuityInfluence.from_state(emotion=state, environment=None)

    assert influence.daypart == "unknown"
    assert influence.season is None
    assert influence.weather_condition is None
    assert influence.primary_emotion == "contentment"


def test_sexuality_dimensions_remain_independent_modeled_state_not_consent(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="matrix-sexuality",
        source="inferred",
        evidence_ref="reviewed-sexuality",
        description="Reviewed relational evidence supports distinct sexuality dimensions.",
        emotions=("sexual-attraction", "sexual-desire", "sexual-arousal", "affection"),
        occurred_at=NOW,
        subject="Sparks",
    )
    state = journal.current_state(now=NOW, subject="Sparks")
    names = {item.name for item in state.active}
    prompt = journal.current_state_prompt(now=NOW, subject="Sparks").lower()

    assert {"sexual-attraction", "sexual-desire", "sexual-arousal", "affection"} <= names
    assert "rather than a single sexual mode" in prompt
    assert "never equate any of them with consent" in prompt



def test_repeated_source_backed_evidence_reinforces_without_unbounded_intensity(
    tmp_path,
):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="reinforce-1",
        source="user_reported",
        evidence_ref="message-1",
        description="Reviewed evidence supports fondness.",
        emotions=("fondness",),
        occurred_at=NOW,
        subject="Sparks",
    )
    first = next(
        item
        for item in journal.current_state(now=NOW, subject="Sparks").active
        if item.name == "fondness"
    )

    journal.record(
        event_id="reinforce-2",
        source="user_reported",
        evidence_ref="message-2",
        description="Separate reviewed evidence also supports fondness.",
        emotions=("fondness",),
        occurred_at=NOW,
        subject="Sparks",
    )
    reinforced = next(
        item
        for item in journal.current_state(now=NOW, subject="Sparks").active
        if item.name == "fondness"
    )

    assert reinforced.intensity > first.intensity
    assert reinforced.intensity <= 1.0
    assert reinforced.evidence_refs == ("message-2", "message-1") or set(
        reinforced.evidence_refs
    ) == {"message-1", "message-2"}


def test_reappraisal_changes_current_state_without_rewriting_original_evidence(
    tmp_path,
):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="revision-1",
        source="observed",
        evidence_ref="test-result-1",
        description="A result initially supported frustration.",
        emotions=("frustration",),
        occurred_at=NOW,
        subject="Sparks",
    )
    journal.revise(
        event_id="revision-1",
        emotions=("relief",),
        reason="Later reviewed evidence showed the result was expected.",
        revised_at=NOW + timedelta(minutes=1),
    )

    event = journal.recent(
        now=NOW + timedelta(minutes=2),
        subject="Sparks",
    )[0]
    assert event.original_emotions == ("frustration",)
    assert event.current_emotions == ("relief",)
    assert event.revision_count == 1

    names = {
        item.name
        for item in journal.current_state(
            now=NOW + timedelta(minutes=2),
            subject="Sparks",
        ).active
    }
    assert "relief" in names
    assert "frustration" not in names


@pytest.mark.parametrize(
    ("gap", "required", "forbidden"),
    (
        (
            timedelta(hours=2),
            {"fondness", "warmth", "anticipation"},
            {"sadness", "frustration", "anger"},
        ),
        (
            timedelta(hours=24),
            {"longing", "fondness", "warmth"},
            {"frustration", "anger"},
        ),
        (
            timedelta(days=4),
            {"longing", "sadness", "fondness", "relief"},
            {"frustration", "anger"},
        ),
        (
            timedelta(days=8),
            {"longing", "sadness", "fondness", "relief"},
            {"frustration", "anger"},
        ),
    ),
)
def test_absence_duration_changes_reunion_appraisal_without_inventing_blame(
    gap,
    required,
    forbidden,
):
    appraisal = EmotionalJournal.appraise_reunion(
        gap=gap,
        returned_at=NOW,
        expectation=None,
    )
    labels = set(appraisal.emotions)
    assert required <= labels
    assert not labels.intersection(forbidden)


def test_explicit_late_return_expectation_can_support_frustration_and_anger():
    expectation = ReturnExpectation(
        subject="Sparks",
        source_ref="return-expectation-1",
        recorded_at=NOW - timedelta(days=8),
        expected_return_at=NOW - timedelta(days=4),
    )
    appraisal = EmotionalJournal.appraise_reunion(
        gap=timedelta(days=8),
        returned_at=NOW,
        expectation=expectation,
    )
    assert {"longing", "sadness", "frustration", "anger", "relief"} <= set(
        appraisal.emotions
    )
    assert appraisal.expectation_source_ref == "return-expectation-1"



def test_foreground_reaction_outranks_background_relational_tone(tmp_path):
    journal = EmotionalJournal(tmp_path / "state.db")
    journal.record(
        event_id="background-warmth",
        source="observed",
        evidence_ref="relationship-evidence",
        description="Grounded relationship evidence supports warmth.",
        emotions=("warmth", "fondness"),
        occurred_at=NOW,
        subject="Sparks",
    )
    journal.record(
        event_id="foreground-curiosity",
        source="observed",
        evidence_ref="current-topic",
        description="The current topic produced grounded curiosity.",
        emotions=("curiosity",),
        occurred_at=NOW,
        subject="Sparks",
    )

    state = journal.current_state(now=NOW, subject="Sparks")
    influence = ContinuityInfluence.from_state(
        emotion=state,
        environment=None,
    )

    assert influence.primary_emotion == "curiosity"
    assert {"warmth", "fondness", "curiosity"} <= set(influence.active_emotions)
