"""Workstream C: bounded simulated emotion/appraisal state per Core."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.contracts import EvidenceState
from sofia.core.multicore.emotion import (
    MACK_EMOTION_PROFILE,
    NOVA_EMOTION_PROFILE,
    SIMULATED_EMOTION_DISCLAIMER,
    CoreEmotionAppraisal,
    EmotionEvidenceError,
    EmotionFeedbackError,
    EmotionReading,
    apply_emotion_appraisal,
    initial_emotion_state,
    project_simulated_emotion,
    render_emotion_context,
)

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)


def appraisal(
    core_id,
    *,
    readings: tuple[EmotionReading, ...] = (
        EmotionReading("joy", 0.7),
        EmotionReading("curiosity", 0.6),
    ),
    evidence_ids: tuple | None = None,
    occurred_at: datetime = NOW,
    evidence_state: EvidenceState = EvidenceState.REPORTED,
    confidence: float = 1.0,
) -> CoreEmotionAppraisal:
    return CoreEmotionAppraisal(
        appraisal_id=uuid4(),
        core_id=core_id,
        occurred_at=occurred_at,
        readings=readings,
        evidence=(uuid4(),) if evidence_ids is None else evidence_ids,
        evidence_state=evidence_state,
        reason="A bounded appraisal grounded in the recorded exchange.",
        confidence=confidence,
    )


def test_simulated_emotion_is_explicitly_not_consciousness():
    core = uuid4()
    state = initial_emotion_state(core_id=core, profile=MACK_EMOTION_PROFILE, now=NOW)
    state = apply_emotion_appraisal(
        state,
        appraisal(core),
        profile=MACK_EMOTION_PROFILE,
        now=NOW,
    )
    current = project_simulated_emotion(
        state,
        profile=MACK_EMOTION_PROFILE,
        now=NOW,
    )
    assert current.simulated is True
    assert current.consciousness_claimed is False
    assert "not consciousness" in current.disclaimer
    assert "not consciousness" in SIMULATED_EMOTION_DISCLAIMER
    assert current.intensity("joy") > 0.0


def test_appraisal_belongs_to_exactly_one_core():
    core = uuid4()
    other = uuid4()
    state = initial_emotion_state(core_id=core, profile=MACK_EMOTION_PROFILE, now=NOW)
    with pytest.raises(ValueError, match="another Core"):
        apply_emotion_appraisal(
            state,
            appraisal(other),
            profile=MACK_EMOTION_PROFILE,
            now=NOW,
        )


def test_profile_must_match_the_core_continuity_key():
    core = uuid4()
    state = initial_emotion_state(core_id=core, profile=MACK_EMOTION_PROFILE, now=NOW)
    with pytest.raises(ValueError, match="does not belong"):
        apply_emotion_appraisal(
            state,
            appraisal(core),
            profile=NOVA_EMOTION_PROFILE,
            now=NOW,
        )


def test_no_endless_emotional_feedback_from_repeated_evidence():
    core = uuid4()
    state = initial_emotion_state(core_id=core, profile=NOVA_EMOTION_PROFILE, now=NOW)
    evidence_ids = (uuid4(),)
    first = appraisal(core, evidence_ids=evidence_ids)
    state = apply_emotion_appraisal(
        state,
        first,
        profile=NOVA_EMOTION_PROFILE,
        now=NOW,
    )
    replay = appraisal(core, evidence_ids=evidence_ids)
    with pytest.raises(EmotionFeedbackError, match="replays evidence"):
        apply_emotion_appraisal(
            state,
            replay,
            profile=NOVA_EMOTION_PROFILE,
            now=NOW + timedelta(minutes=1),
        )


def test_speculative_evidence_cannot_drive_affect():
    with pytest.raises(EmotionEvidenceError, match="speculative"):
        appraisal(uuid4(), evidence_state=EvidenceState.SPECULATIVE)


def test_projection_is_bounded_and_decays():
    core = uuid4()
    state = initial_emotion_state(core_id=core, profile=MACK_EMOTION_PROFILE, now=NOW)
    readings = tuple(
        EmotionReading(name, 0.9)
        for name in ("joy", "curiosity", "concern", "warmth", "relief", "pride")
    )
    state = apply_emotion_appraisal(
        state,
        appraisal(core, readings=readings),
        profile=MACK_EMOTION_PROFILE,
        now=NOW,
    )
    early = project_simulated_emotion(
        state,
        profile=MACK_EMOTION_PROFILE,
        now=NOW,
    )
    late = project_simulated_emotion(
        state,
        profile=MACK_EMOTION_PROFILE,
        now=NOW + timedelta(days=4),
    )
    assert len(early.readings) <= 6
    assert len(late.readings) <= 6
    assert late.intensity("joy") < early.intensity("joy")


def test_mack_and_nova_have_distinct_behavioral_profiles():
    assert MACK_EMOTION_PROFILE.display_name == "Mack Fuller"
    assert NOVA_EMOTION_PROFILE.display_name == "Nova Arden"
    assert MACK_EMOTION_PROFILE.temperament["steadiness"] > 0.5
    assert NOVA_EMOTION_PROFILE.temperament["playfulness"] > 0.5
    assert NOVA_EMOTION_PROFILE.expressiveness > MACK_EMOTION_PROFILE.expressiveness
    assert "safety" in MACK_EMOTION_PROFILE.serious_contexts
    assert "boundaries" in NOVA_EMOTION_PROFILE.serious_contexts


def test_render_context_is_explicitly_non_authoritative():
    core = uuid4()
    state = initial_emotion_state(core_id=core, profile=NOVA_EMOTION_PROFILE, now=NOW)
    state = apply_emotion_appraisal(
        state,
        appraisal(core, readings=(EmotionReading("playfulness", 0.8),)),
        profile=NOVA_EMOTION_PROFILE,
        now=NOW,
    )
    text = render_emotion_context(
        state,
        profile=NOVA_EMOTION_PROFILE,
        now=NOW,
    )
    assert "SIMULATED AFFECT CONTEXT" in text
    assert "not consciousness" in text
    assert "never grants permission" in text
    assert "playfulness" in text


def test_emotion_state_carries_no_model_or_provider_binding():
    core = uuid4()
    state = initial_emotion_state(core_id=core, profile=MACK_EMOTION_PROFILE, now=NOW)
    assert not hasattr(state, "model_id")
    assert not hasattr(state, "provider_id")
    assert state.continuity_key == "mack-fuller"
