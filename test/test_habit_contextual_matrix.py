"""HABIT contextual behavior matrix acceptance tests."""
from __future__ import annotations

from datetime import datetime, timezone

from sofia.habits.continuity import HabitContinuityCoordinator
from sofia.habits.model import ObservationCoverage, SourceQuality
from sofia.habits.patterns import CadenceKind, HabitCategory
from sofia.state.sqlite_plane import SQLiteStatePlane


NOW = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)


def coordinator(tmp_path) -> HabitContinuityCoordinator:
    return HabitContinuityCoordinator(
        SQLiteStatePlane(tmp_path / "state.db")
    )


def record_contextual_observation(service: HabitContinuityCoordinator, *, evidence: str):
    return service.recorder.record(
        principal_id="sparks",
        audience_id="owner-private",
        kind="conversation.user_message",
        occurred_at=NOW,
        local_timestamp=NOW,
        timezone_name="UTC",
        context={
            "daypart": "evening",
            "day_type": "weekday",
            "season": "autumn",
            "daylight": "night",
            "weather": "light rain",
        },
        evidence_ref=evidence,
        source_quality=SourceQuality.VERIFIED,
        coverage=ObservationCoverage.OBSERVED,
    )


def test_contextual_analysis_keeps_daily_seasonal_and_environment_patterns_separate(tmp_path):
    service = coordinator(tmp_path)
    record_contextual_observation(service, evidence="msg-context-1")

    service.analyze_conversation_patterns(
        principal_id="sparks",
        audience_id="owner-private",
        now=NOW,
    )

    patterns = service.patterns.patterns(
        principal_id="sparks",
        audience_id="owner-private",
    )

    assert any(
        item.category is HabitCategory.CONVERSATION_ROUTINE
        and item.cadence is CadenceKind.DAILY
        and item.context.get("daypart") == "evening"
        and item.context.get("day_type") == "weekday"
        for item in patterns
    )
    assert any(
        item.category is HabitCategory.CONVERSATION_ROUTINE
        and item.cadence is CadenceKind.SEASONAL
        and item.context.get("season") == "autumn"
        and item.context.get("daypart") == "evening"
        for item in patterns
    )
    assert any(
        item.category is HabitCategory.ENVIRONMENT_CORRELATION
        and item.context.get("weather") == "light rain"
        and item.context.get("daypart") == "evening"
        for item in patterns
    )
    assert any(
        item.category is HabitCategory.ENVIRONMENT_CORRELATION
        and item.context.get("daylight") == "night"
        and item.context.get("daypart") == "evening"
        for item in patterns
    )


def test_contextual_habit_evidence_remains_tentative_after_one_observation(tmp_path):
    service = coordinator(tmp_path)
    record_contextual_observation(service, evidence="msg-context-1")

    service.analyze_conversation_patterns(
        principal_id="sparks",
        audience_id="owner-private",
        now=NOW,
    )

    patterns = service.patterns.patterns(
        principal_id="sparks",
        audience_id="owner-private",
    )
    contextual = tuple(
        item
        for item in patterns
        if (
            item.cadence is CadenceKind.SEASONAL
            or item.category is HabitCategory.ENVIRONMENT_CORRELATION
        )
    )

    assert contextual
    assert all(item.support_count == 1 for item in contextual)
    assert all(item.lifecycle.value == "tentative" for item in contextual)


def test_reanalysis_of_same_observation_does_not_inflate_contextual_support(tmp_path):
    service = coordinator(tmp_path)
    record_contextual_observation(service, evidence="msg-context-1")

    for _ in range(2):
        service.analyze_conversation_patterns(
            principal_id="sparks",
            audience_id="owner-private",
            now=NOW,
        )

    patterns = service.patterns.patterns(
        principal_id="sparks",
        audience_id="owner-private",
    )

    assert patterns
    assert all(item.support_count == 1 for item in patterns)
    assert all(item.evidence_refs == ("msg-context-1",) for item in patterns)
