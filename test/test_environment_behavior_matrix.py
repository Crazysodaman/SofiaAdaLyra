"""Cross-package context behavior matrix for ENVIRONMENT, EMOTION, INTERACT and AVATAR.

These tests intentionally exercise equivalence classes instead of a giant
Cartesian product. One trusted environment snapshot may influence expression,
interaction context and presentation, but it never creates consent, durable
emotion, renderer evidence or action authority.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from types import SimpleNamespace

from sofia.application.conversation_service import ConversationService
from sofia.avatar.wardrobe_planner import wardrobe_emotion_influences
from sofia.cognition.matrix.expression_plan import EmbodiedExpressionPlanner
from sofia.avatar.presentation import AppearanceState, PresentationAuthority
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_planner import Activity, OutfitPlanner, WardrobeContext
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.embodiment.store import EmbodimentStore
from sofia.environment.config import ConfiguredLocation, EnvironmentConfiguration
from sofia.environment.astronomy import season_for
from sofia.environment.model import EnvironmentFreshness, Season, WeatherObservation
from sofia.environment.provider import EnvironmentProviderObservation
from sofia.environment.service import EnvironmentService
from sofia.interaction.expanded_service import ExpandedConversationService
from sofia.emotion.journal import EmotionalJournal
from sofia.personality.influence import ContinuityInfluence, daypart


ROOT = Path(__file__).resolve().parents[1]
AVATAR = ROOT / "src" / "sofia" / "data" / "avatar.json"
# 03:30 UTC is 22:30 local on the previous date in America/Chicago here.
NOW = datetime(2026, 9, 28, 3, 30, tzinfo=timezone.utc)


class Provider:
    name = "matrix-weather"

    def __init__(self, weather: WeatherObservation | None) -> None:
        self.weather = weather

    def observe(self, *, now):
        return EnvironmentProviderObservation(weather=self.weather)


class FixedEnvironment:
    def __init__(self, snapshot) -> None:
        self.snapshot_value = snapshot

    def snapshot(self, *, now=None, refresh_providers=False):
        return self.snapshot_value


def environment_snapshot(*, stale_weather: bool = False):
    observed = NOW - (timedelta(hours=3) if stale_weather else timedelta(minutes=5))
    expires = NOW - timedelta(hours=2) if stale_weather else NOW + timedelta(minutes=25)
    weather = WeatherObservation(
        condition="rainy",
        observed_at=observed,
        expires_at=expires,
        source_id="matrix.weather",
        location_label="Matrix site",
        temperature_c=12.0,
    )
    config = EnvironmentConfiguration(
        location=ConfiguredLocation(
            label="Matrix site",
            timezone="America/Chicago",
            latitude=32.5,
            longitude=-97.1,
        )
    )
    return EnvironmentService(
        config,
        providers=(Provider(weather),),
    ).snapshot(now=NOW)


def modeled_state(tmp_path):
    journal = EmotionalJournal(tmp_path / "matrix.db")
    journal.record(
        event_id="matrix-affection",
        source="inferred",
        evidence_ref="reviewed:matrix-affection",
        description="Reviewed relationship evidence supports a warm modeled appraisal.",
        emotions=("fondness",),
        occurred_at=NOW,
        subject="Sparks",
    )
    return journal, journal.current_state(now=NOW, subject="Sparks")


def presentation_authority():
    catalog = build_starter_wardrobe()
    return catalog, PresentationAuthority(
        catalog.wardrobe,
        outfits={plan.outfit_id: plan.item_ids for plan in catalog.presets},
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            "long layered",
            "deep crimson",
            "dark violet",
            ("engineer",),
        ),
    )


def test_one_snapshot_drives_emotion_context_avatar_and_outfit_without_becoming_authority(tmp_path):
    snapshot = environment_snapshot()
    journal, state = modeled_state(tmp_path)
    influence = ContinuityInfluence.from_state(
        emotion=state,
        environment=snapshot,
    )

    assert influence.daypart == "night"
    assert influence.season == "autumn"
    assert influence.weather_condition == "rainy"
    assert influence.weather_freshness == "current"
    assert influence.primary_emotion == "fondness"
    assert influence.foreground_emotion is None
    assert "create permissions" in influence.prompt()

    # ENVIRONMENT is contextual input, not a durable emotional-event writer.
    assert {
        item.name for item in journal.current_state(now=NOW, subject="Sparks").active
    } == {"fondness"}

    catalog, authority = presentation_authority()
    expression = EmbodiedExpressionPlanner().plan(
        message_id="environment-matrix-current",
        influence=influence,
    )
    assert {"daypart", "weather"} <= set(expression.active_signals)
    assert expression.primary is not None

    context = WardrobeContext.from_environment_snapshot(
        snapshot,
        activity=Activity.CONVERSATION,
        emotion_influences=wardrobe_emotion_influences(influence),
    )
    proposal = OutfitPlanner(
        catalog.wardrobe,
        catalog.presets,
    ).suggest(context)
    assert proposal.outfit_id == "lounge.relaxed"


def test_stale_weather_cannot_influence_avatar_or_wardrobe(tmp_path):
    snapshot = environment_snapshot(stale_weather=True)
    _, state = modeled_state(tmp_path)
    influence = ContinuityInfluence.from_state(
        emotion=state,
        environment=snapshot,
    )

    assert influence.weather_condition is None
    assert influence.temperature_c is None
    assert influence.weather_freshness == "stale"
    assert "Weather condition: unknown" in influence.prompt()
    assert "Weather freshness: stale" in influence.prompt()

    catalog, authority = presentation_authority()
    expression = EmbodiedExpressionPlanner().plan(
        message_id="environment-matrix-stale",
        influence=influence,
    )
    assert "weather" not in expression.active_signals

    context = WardrobeContext.from_environment_snapshot(
        snapshot,
        activity=Activity.CONVERSATION,
    )
    assert context.weather is None


def test_interact_receives_same_context_without_weather_or_emotion_granting_consent(
    monkeypatch,
    tmp_path,
):
    snapshot = environment_snapshot()
    content = "I touch your chest"
    original = CognitiveRequest(
        messages=(CognitiveMessage(role=CognitiveRole.USER, content=content),),
        allow_tools=False,
    )
    monkeypatch.setattr(
        ConversationService,
        "_build_request",
        lambda self: original,
    )
    user = SimpleNamespace(
        id="matrix-user-1",
        session_id="matrix-session-1",
        role=ConversationRole.USER,
        content=content,
        created_at=NOW,
    )
    monkeypatch.setattr(
        ExpandedConversationService,
        "messages",
        lambda self: (user,),
    )

    service = object.__new__(ExpandedConversationService)
    service._runtime = SimpleNamespace(
        personality=object(),
        embodiment=EmbodimentStore(AVATAR).load(),
        configuration=SimpleNamespace(state_path=tmp_path / "matrix.db"),
        environment_service=FixedEnvironment(snapshot),
    )
    service._emotional_journal = EmotionalJournal(tmp_path / "matrix.db")
    service._reflection_journal = None
    service._clarification_journal = None

    request = service._build_request()
    system = "\n".join(
        message.content
        for message in request.messages
        if message.role is CognitiveRole.SYSTEM
    )

    assert "CONTINUITY INFLUENCE CONTEXT" in system
    assert "Local daypart: night" in system
    assert "Season: autumn" in system
    assert "Weather condition: rainy" in system
    assert "TRUSTED INTERACTION INTERPRETATION" in system
    assert '"policy_status": "accepted"' in system
    assert '"region_id": "chest"' in system
    lowered = system.casefold()
    assert "accepted" in lowered
    assert "recognized" in lowered
    assert "consent" in lowered
    assert request.tools == ()
    assert request.allow_tools is False



@pytest.mark.parametrize(
    ("hour", "expected"),
    (
        (0, "night"),
        (4, "night"),
        (5, "morning"),
        (11, "morning"),
        (12, "afternoon"),
        (16, "afternoon"),
        (17, "evening"),
        (21, "evening"),
        (22, "night"),
        (23, "night"),
    ),
)
def test_daypart_boundary_matrix(hour, expected):
    assert daypart(NOW.replace(hour=hour)) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    (
        (date(2026, 1, 15), Season.WINTER),
        (date(2026, 4, 15), Season.SPRING),
        (date(2026, 7, 15), Season.SUMMER),
        (date(2026, 10, 15), Season.AUTUMN),
    ),
)
def test_northern_season_matrix(day, expected):
    assert season_for(day=day, latitude=32.5) is expected


@pytest.mark.parametrize(
    ("day", "expected"),
    (
        (date(2026, 1, 15), Season.SUMMER),
        (date(2026, 4, 15), Season.AUTUMN),
        (date(2026, 7, 15), Season.WINTER),
        (date(2026, 10, 15), Season.SPRING),
    ),
)
def test_southern_hemisphere_inverts_season_matrix(day, expected):
    assert season_for(day=day, latitude=-33.9) is expected


def test_future_weather_is_diagnostic_only_and_cannot_influence_shared_context(
    tmp_path,
):
    future = WeatherObservation(
        condition="stormy",
        observed_at=NOW + timedelta(minutes=10),
        expires_at=NOW + timedelta(minutes=40),
        source_id="matrix.future-weather",
        location_label="Matrix site",
        temperature_c=8.0,
    )
    config = EnvironmentConfiguration(
        location=ConfiguredLocation(
            label="Matrix site",
            timezone="America/Chicago",
            latitude=32.5,
            longitude=-97.1,
        )
    )
    snapshot = EnvironmentService(
        config,
        providers=(Provider(future),),
    ).snapshot(now=NOW)
    assert snapshot.weather_freshness is EnvironmentFreshness.FUTURE

    _, state = modeled_state(tmp_path)
    influence = ContinuityInfluence.from_state(
        emotion=state,
        environment=snapshot,
    )
    assert influence.weather_condition is None
    assert influence.temperature_c is None
    assert influence.weather_freshness == "future"

    context = WardrobeContext.from_environment_snapshot(
        snapshot,
        activity=Activity.CONVERSATION,
    )
    assert context.weather is None
