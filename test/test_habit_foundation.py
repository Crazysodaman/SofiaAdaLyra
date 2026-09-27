from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from sofia.habits.engine import HabitPatternEngine, pattern_signature
from sofia.habits.expectations import (
    ExpectationStatus,
    HabitExpectationEngine,
    HabitExpectationStore,
)
from sofia.habits.model import ObservationCoverage, SourceQuality
from sofia.habits.pattern_store import HabitPatternStore
from sofia.habits.patterns import CadenceKind, HabitCategory
from sofia.habits.recorder import HabitObservationRecorder
from sofia.habits.store import HabitObservationStore
from sofia.state.sqlite_plane import SQLiteStatePlane


PRINCIPAL = "sparks"
AUDIENCE = "owner-private"
NOW = datetime(2026, 9, 27, 20, 0, tzinfo=timezone.utc)


def stack(tmp_path):
    plane = SQLiteStatePlane(tmp_path / "state.db")
    observations = HabitObservationStore(plane)
    recorder = HabitObservationRecorder(observations)
    patterns = HabitPatternStore(plane)
    engine = HabitPatternEngine(patterns)
    expectations = HabitExpectationStore(plane)
    expectation_engine = HabitExpectationEngine(expectations)
    return recorder, observations, patterns, engine, expectations, expectation_engine


def observation(recorder, *, evidence: str, when: datetime = NOW, coverage=ObservationCoverage.OBSERVED):
    return recorder.record(
        principal_id=PRINCIPAL,
        audience_id=AUDIENCE,
        kind="conversation.user_message",
        occurred_at=when,
        local_timestamp=when,
        timezone_name="UTC",
        context={"daypart": "evening", "day_type": "weekend"},
        evidence_ref=evidence,
        source_quality=SourceQuality.VERIFIED,
        coverage=coverage,
    )


def support(engine, item, *, now=NOW):
    return engine.observe_support(
        item,
        category=HabitCategory.CONVERSATION_ROUTINE,
        cadence=CadenceKind.DAILY,
        pattern_context={"daypart": "evening", "day_type": "weekend"},
        now=now,
    )


def test_sensitive_observation_requires_explicit_user_evidence(tmp_path):
    recorder, observations, *_ = stack(tmp_path)

    with pytest.raises(ValueError, match="explicit user evidence"):
        recorder.record(
            principal_id=PRINCIPAL,
            audience_id=AUDIENCE,
            kind="preference.private",
            occurred_at=NOW,
            local_timestamp=NOW,
            timezone_name="UTC",
            context={"topic": "private"},
            evidence_ref="msg-sensitive",
            source_quality=SourceQuality.USER_REPORTED,
            sensitive=True,
            explicit_user_evidence=False,
        )

    saved = recorder.record(
        principal_id=PRINCIPAL,
        audience_id=AUDIENCE,
        kind="preference.private",
        occurred_at=NOW,
        local_timestamp=NOW,
        timezone_name="UTC",
        context={"topic": "private"},
        evidence_ref="msg-sensitive",
        source_quality=SourceQuality.USER_REPORTED,
        sensitive=True,
        explicit_user_evidence=True,
    )

    restored = observations.observations(
        principal_id=PRINCIPAL,
        audience_id=AUDIENCE,
    )
    assert restored == (saved,)
    assert restored[0].sensitive is True
    assert restored[0].explicit_user_evidence is True


def test_replayed_evidence_does_not_inflate_pattern_confidence(tmp_path):
    recorder, _, _, engine, *_ = stack(tmp_path)
    item = observation(recorder, evidence="msg-1")

    first = support(engine, item)
    second = support(engine, item)

    assert first is not None
    assert second is not None
    assert second.pattern_id == first.pattern_id
    assert second.support_count == 1
    assert second.observable_count == 1
    assert second.evidence_refs == ("msg-1",)


def test_offline_or_unknown_coverage_never_becomes_contradiction(tmp_path):
    recorder, _, _, engine, *_ = stack(tmp_path)
    pattern = support(engine, observation(recorder, evidence="msg-1"))
    assert pattern is not None

    unchanged = engine.observe_covered_nonoccurrence(
        pattern=pattern,
        evidence_ref="offline-gap",
        observed_at=NOW + timedelta(hours=1),
        coverage=ObservationCoverage.SOFIA_OFFLINE,
    )

    assert unchanged == pattern
    assert unchanged.contradiction_count == 0
    assert "offline-gap" not in unchanged.evidence_refs


def test_source_invalidation_rebuilds_current_pattern_truth(tmp_path):
    recorder, observations, patterns, engine, *_ = stack(tmp_path)
    first = observation(recorder, evidence="msg-1", when=NOW)
    second = observation(
        recorder,
        evidence="msg-2",
        when=NOW + timedelta(minutes=10),
    )
    pattern = support(engine, first, now=NOW)
    assert pattern is not None
    pattern = support(engine, second, now=NOW + timedelta(minutes=10))
    assert pattern is not None and pattern.support_count == 2

    patterns.invalidate_evidence(
        principal_id=PRINCIPAL,
        audience_id=AUDIENCE,
        evidence_ref="msg-1",
        reason="user corrected source",
        created_at=NOW + timedelta(minutes=20),
    )
    rebuilt = engine.rebuild_from_observations(
        pattern=pattern,
        observations=observations.observations(
            principal_id=PRINCIPAL,
            audience_id=AUDIENCE,
        ),
        now=NOW + timedelta(minutes=20),
    )

    assert rebuilt.support_count == 1
    assert rebuilt.observable_count == 1
    assert rebuilt.evidence_refs == ("msg-2",)


def test_suppression_tombstone_prevents_immediate_relearning(tmp_path):
    recorder, _, patterns, engine, *_ = stack(tmp_path)
    first = observation(recorder, evidence="msg-1")
    pattern = support(engine, first)
    assert pattern is not None

    signature = pattern_signature(
        category=pattern.category,
        cadence=pattern.cadence,
        kind=pattern.context["observation_kind"],
        context={
            key: value
            for key, value in pattern.context.items()
            if key != "observation_kind"
        },
    )
    engine.suppress(
        pattern=pattern,
        signature=signature,
        reason="not a habit",
        evidence_ref="correction-1",
        created_at=NOW + timedelta(minutes=1),
    )

    later = observation(
        recorder,
        evidence="msg-2",
        when=NOW + timedelta(days=1),
    )
    assert support(
        engine,
        later,
        now=NOW + timedelta(days=1),
    ) is None
    assert patterns.is_suppressed(
        principal_id=PRINCIPAL,
        audience_id=AUDIENCE,
        signature=signature,
    )


def test_expectation_resolution_does_not_modify_habit_confidence(tmp_path):
    recorder, _, _, engine, expectations, expectation_engine = stack(tmp_path)
    pattern = support(engine, observation(recorder, evidence="msg-1"))
    assert pattern is not None
    original_confidence = pattern.confidence

    expected = expectation_engine.create(
        pattern=pattern,
        window_start_utc=NOW + timedelta(hours=1),
        window_end_utc=NOW + timedelta(hours=2),
        local_window_start=NOW + timedelta(hours=1),
        local_window_end=NOW + timedelta(hours=2),
        timezone_name="UTC",
        created_at=NOW,
    )
    resolved = expectation_engine.resolve(
        expected,
        status=ExpectationStatus.UNOBSERVABLE,
        resolved_at=NOW + timedelta(hours=3),
        evidence_ref=None,
    )

    assert resolved.status is ExpectationStatus.UNOBSERVABLE
    assert resolved.confidence_snapshot == original_confidence
    assert pattern.confidence == original_confidence
    assert expectations.get(
        resolved.expectation_id,
        principal_id=PRINCIPAL,
        audience_id=AUDIENCE,
    ) == resolved


def test_missed_expectation_requires_resolution_evidence(tmp_path):
    recorder, _, _, engine, _, expectation_engine = stack(tmp_path)
    pattern = support(engine, observation(recorder, evidence="msg-1"))
    assert pattern is not None

    expected = expectation_engine.create(
        pattern=pattern,
        window_start_utc=NOW + timedelta(hours=1),
        window_end_utc=NOW + timedelta(hours=2),
        local_window_start=NOW + timedelta(hours=1),
        local_window_end=NOW + timedelta(hours=2),
        timezone_name="UTC",
        created_at=NOW,
    )

    with pytest.raises(ValueError, match="require evidence"):
        expectation_engine.resolve(
            expected,
            status=ExpectationStatus.MISSED,
            resolved_at=NOW + timedelta(hours=3),
            evidence_ref=None,
        )
