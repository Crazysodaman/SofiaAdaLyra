"""CA-6405 cross-modal provenance at the existing Presence source owner.

Regressions authored for future execution. No sensors are queried here.
"""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.application.act_service import SofiaActService
from sofia.application.presence import (
    CrossModalObservationReceipt, ObservationModality,
    OriginalDataAccess, ObservationPrivacy, PresenceInitiativeEngine,
    WorldAvailability, WorldEpistemicState, WorldObservation,
)


NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


def _engine(tmp_path):
    state=tmp_path / "sofia.db"
    state.touch()
    return state,PresenceInitiativeEngine(
        state_path=state,act_service=SofiaActService(state),
    )


def _observed(*, audience="local:text", epistemic=WorldEpistemicState.OBSERVED):
    return WorldObservation(
        observation_id="observation:voice-source-1",
        subject_id="voice:transcription",
        predicate="voice.transcription",
        source_id="voice:local",
        observed_at=NOW,expires_at=NOW+timedelta(minutes=3),
        confidence=0.9,epistemic_state=epistemic,
        availability=WorldAvailability.ONLINE,
        value={"content":"recognized phrase, not inferred truth"},
        audience_id=audience,
    )


def _receipt(*,original=OriginalDataAccess.VERIFIED_REF,ref="voice:recording-1"):
    return CrossModalObservationReceipt(
        observation_id="observation:voice-source-1",
        modality=ObservationModality.VOICE,source_id="voice:local",
        observed_at=NOW,received_at=NOW+timedelta(seconds=2),
        expires_at=NOW+timedelta(minutes=3),
        original_access=original,original_ref=ref,
        privacy=ObservationPrivacy.PRIVATE,
        interpretation_confidence=0.6,
        epistemic_state=WorldEpistemicState.OBSERVED,
    )


def test_source_receipt_persists_atomically_with_original_world_event(tmp_path):
    state,owner=_engine(tmp_path)
    observation=_observed()
    receipt=_receipt()
    owner.observe(observation,receipt=receipt)
    persisted=owner.source_receipt(
        observation_id=observation.observation_id,
        audience_id="local:text",
    )
    assert persisted == receipt
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM presence_cross_modal_receipt"
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT value_json FROM presence_world_observation "
            "WHERE observation_id=?", (observation.observation_id,),
        ).fetchone() is not None
    owner.observe(observation,receipt=receipt)


def test_cross_modal_private_provenance_never_leaks_to_other_audience(tmp_path):
    _,owner=_engine(tmp_path)
    owner.observe(_observed(),receipt=_receipt())
    with pytest.raises(PermissionError,match="audience"):
        owner.source_receipt(
            observation_id="observation:voice-source-1",
            audience_id="mobile:standard",
        )
    with pytest.raises(PermissionError,match="audience"):
        owner.source_receipt(
            observation_id="observation:voice-source-1",
            audience_id=None,
        )


def test_source_conflict_and_fabricated_direct_observation_fail_closed(tmp_path):
    _,owner=_engine(tmp_path)
    record=_observed()
    owner.observe(record,receipt=_receipt())
    changed=_receipt(original=OriginalDataAccess.VERIFIED_REF,ref="voice:other")
    with pytest.raises(ValueError,match="changed"):
        owner.observe(record,receipt=changed)
    with pytest.raises(ValueError,match="unavailable original"):
        _receipt(
            original=OriginalDataAccess.UNAVAILABLE,ref=None,
        ).validate(record)


def test_host_does_not_invent_cross_modal_receipt_for_legacy_observation(tmp_path):
    _,owner=_engine(tmp_path)
    observation=_observed()
    owner.observe(observation)
    assert owner.source_receipt(
        observation_id=observation.observation_id,audience_id="local:text",
    ) is None
