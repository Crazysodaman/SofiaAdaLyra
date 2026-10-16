"""CA-6406 canonical source-linked conflict integration and scope regression."""
from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from sofia.application.act_service import SofiaActService
from sofia.social.principals import local_sparks_principal
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.application.presence import (
    CrossModalObservationReceipt, ObservationModality,
    OriginalDataAccess, ObservationPrivacy, PresenceInitiativeEngine,
    WorldAvailability, WorldEpistemicState, WorldObservation,
)

pytestmark = pytest.mark.pkg_verify
NOW = datetime(2026, 10, 15, 20, tzinfo=timezone.utc)


def engine(tmp_path):
    path = tmp_path / "sofia.db"
    path.touch()
    return path, PresenceInitiativeEngine(
        state_path=path, act_service=SofiaActService(path),
    )


def source(identity, value, *, event="event:one", audience="local:text",
           when=NOW):
    return WorldObservation(
        observation_id=identity, subject_id="service:example",
        predicate="service.status", source_id="sensor:" + identity,
        observed_at=when, expires_at=when+timedelta(minutes=10),
        confidence=0.8, epistemic_state=WorldEpistemicState.OBSERVED,
        availability=WorldAvailability.ONLINE,
        value=value, audience_id=audience, correlation_event_id=event,
    )


def receipt(item, modality=ObservationModality.APP):
    return CrossModalObservationReceipt(
        observation_id=item.observation_id, modality=modality,
        source_id=item.source_id, observed_at=item.observed_at,
        received_at=item.observed_at, expires_at=item.expires_at,
        original_access=OriginalDataAccess.VERIFIED_REF,
        original_ref="source:" + item.observation_id,
        privacy=ObservationPrivacy.PRIVATE,
        interpretation_confidence=0.7,
        epistemic_state=item.epistemic_state,
    )


def test_same_event_disagreement_is_source_linked_and_persists_on_restart(tmp_path):
    path, owner = engine(tmp_path)
    first = source("first", "private sensitive running")
    second = source("second", "stopped")
    owner.observe(first, receipt=receipt(first, ObservationModality.SCREEN))
    owner.observe(second, receipt=receipt(second))
    matches = owner.correlated_conflicts(principal=local_sparks_principal())
    assert len(matches) == 1
    assert set((matches[0]["first_source_ref"],
                matches[0]["second_source_ref"])) == {"first", "second"}
    assert matches[0]["kind"] == "value_conflict"
    assert matches[0]["requires_authorized_review"]
    assert matches[0]["factual_resolution"] is None
    assert "private sensitive running" not in str(matches)
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT * FROM presence_observation_conflict").fetchone()
        assert "private sensitive running" not in str(row)
    restarted = PresenceInitiativeEngine(
        state_path=path, act_service=SofiaActService(path),
    )
    assert restarted.correlated_conflicts(principal=local_sparks_principal()) == matches
    assert restarted.correlated_conflicts(principal=local_sparks_principal("discord:shared")) == ()
    # An identical retry cannot create a second contradiction.
    restarted.observe(second, receipt=receipt(second))
    assert len(restarted.correlated_conflicts(principal=local_sparks_principal())) == 1


def test_different_events_or_audiences_never_merge(tmp_path):
    _, owner = engine(tmp_path)
    first = source("first", "running")
    owner.observe(first, receipt=receipt(first))
    second = source("second", "stopped", event="event:other")
    owner.observe(second, receipt=receipt(second))
    third = source("third", "stopped", audience="discord:shared")
    owner.observe(third, receipt=receipt(third))
    assert owner.correlated_conflicts(principal=local_sparks_principal()) == ()
    assert owner.correlated_conflicts(principal=local_sparks_principal("discord:shared")) == ()


def test_missing_provenance_and_rebinding_fail_closed_without_write(tmp_path):
    path, owner = engine(tmp_path)
    first = source("first", "running")
    with pytest.raises(PermissionError, match="provenance"):
        owner.observe(first)
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT count(*) FROM presence_world_observation"
        ).fetchone()[0] == 0
    owner.observe(first, receipt=receipt(first))
    edited = source("first", "running", event="event:other")
    with pytest.raises(ValueError):
        owner.observe(edited, receipt=receipt(edited))
    assert owner.correlated_conflicts(principal=local_sparks_principal()) == ()


@pytest.mark.parametrize("event", ["", "event spaces", "private\nevent"])
def test_correlation_event_id_is_bounded(event):
    with pytest.raises(ValueError):
        source("first", "running", event=event)


def test_raw_transcripts_and_unrelated_unscoped_values_not_compared(tmp_path):
    _, owner = engine(tmp_path)
    first = source("first", {"private_content": "never copy this"})
    second = source("second", {"private_content": "also private"})
    owner.observe(first, receipt=receipt(first, ObservationModality.VOICE))
    owner.observe(second, receipt=receipt(second, ObservationModality.VOICE))
    assert owner.correlated_conflicts(principal=local_sparks_principal()) == ()


def test_conflict_review_rejects_unbound_or_wrong_principal(tmp_path):
    _, owner = engine(tmp_path)
    with pytest.raises(TypeError):
        owner.correlated_conflicts(principal="local:text")
    with pytest.raises(PermissionError):
        owner.correlated_conflicts(principal=PrincipalContext(
            "person:untrusted", "local:text", AudienceKind.PRIVATE,
        ))
    with pytest.raises(PermissionError):
        owner.correlated_conflicts(principal=PrincipalContext(
            "person:sparks", "local:text", AudienceKind.SHARED,
        ))
    with pytest.raises(ValueError):
        owner.correlated_conflicts(principal=local_sparks_principal(), limit=0)
