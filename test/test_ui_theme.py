from datetime import datetime, timedelta, timezone

from sofia.avatar.presentation import (
    AppearanceState,
    AttireMode,
    AudienceScope,
    PresentationProjection,
)
from sofia.environment.model import (
    DaylightObservation,
    DaylightState,
    EnvironmentFreshness,
    EnvironmentSnapshot,
    WeatherObservation,
)
from sofia.personality.emotion import (
    ActiveEmotion,
    CurrentEmotionalState,
)
from sofia.ui.theme import (
    AdaptiveThemePolicy,
    ThemeSignals,
    canonical_theme,
    theme_signals_from_sources,
)


NOW = datetime(
    2026,
    9,
    26,
    21,
    0,
    tzinfo=timezone.utc,
)


def _environment(
    *,
    daylight=DaylightState.NIGHT,
    weather: str | None = None,
    freshness=EnvironmentFreshness.UNKNOWN,
):
    observation = None
    if weather is not None:
        observation = WeatherObservation(
            condition=weather,
            observed_at=NOW,
            expires_at=NOW + timedelta(hours=1),
            source_id="weather:test",
        )
    return EnvironmentSnapshot(
        observed_at=NOW,
        utc_time=NOW,
        host_local_time=NOW,
        host_timezone_label="UTC",
        daylight=DaylightObservation(
            state=daylight
        ),
        weather=observation,
        weather_freshness=freshness,
    )


def _presentation(
    outfit_id: str = "engineer.signature",
):
    return PresentationProjection(
        audience=AudienceScope.PUBLIC,
        source_revision=1,
        attire=AttireMode.CLOTHED,
        outfit_id=outfit_id,
        item_ids=("item",),
        appearance=AppearanceState(
            hairstyle="canonical",
            hair_color="deep crimson",
            tail_color="dark violet",
            style_tags=("canonical", "engineer"),
        ),
        private_fallback_used=False,
        reason="test",
    )


def _emotion(
    name: str,
    *,
    intensity: float = 0.8,
    tone: str = "positive",
):
    return CurrentEmotionalState(
        as_of=NOW,
        subject="Sparks",
        tone=tone,
        active=(
            ActiveEmotion(
                name=name,
                intensity=intensity,
                evidence_refs=("event-source",),
                event_ids=("event-1",),
            ),
        ),
    )


def test_theme_uses_current_weather_but_not_stale_weather():
    current = theme_signals_from_sources(
        environment=_environment(
            weather="Light rain",
            freshness=EnvironmentFreshness.CURRENT,
        ),
        presentation=_presentation(),
        emotion=None,
    )
    stale = theme_signals_from_sources(
        environment=_environment(
            weather="Light rain",
            freshness=EnvironmentFreshness.STALE,
        ),
        presentation=_presentation(),
        emotion=None,
    )

    assert current.weather_condition == "Light rain"
    assert stale.weather_condition is None


def test_lounge_and_warmth_produce_warmer_palette():
    signals = theme_signals_from_sources(
        environment=_environment(),
        presentation=_presentation("lounge.relaxed"),
        emotion=_emotion("warmth"),
    )

    palette = AdaptiveThemePolicy().select(
        signals
    )

    assert palette.primary == "#8B1E3F"
    assert "lounge" in palette.drivers
    assert "emotion:warmth" in palette.drivers


def test_rain_changes_secondary_accent_without_animation_state():
    palette = AdaptiveThemePolicy().select(
        ThemeSignals(
            local_time=NOW,
            daylight=DaylightState.DAY,
            weather_condition="Rain showers",
            outfit_id="engineer.signature",
        )
    )

    assert palette.secondary == "#5AC8E8"
    assert "rain" in palette.drivers


def test_strong_anger_uses_bounded_hot_accent():
    palette = AdaptiveThemePolicy().select(
        ThemeSignals(
            local_time=NOW,
            daylight=DaylightState.NIGHT,
            outfit_id="engineer.signature",
            primary_emotion="anger",
            primary_emotion_intensity=0.9,
            emotional_tone="negative",
        )
    )

    assert palette.primary == "#9F2020"
    assert palette.secondary == "#D58B3A"
    assert "emotion:anger" in palette.drivers


def test_night_is_darker_than_day():
    policy = AdaptiveThemePolicy()
    night = policy.select(
        ThemeSignals(
            local_time=NOW,
            daylight=DaylightState.NIGHT,
        )
    )
    day = policy.select(
        ThemeSignals(
            local_time=NOW,
            daylight=DaylightState.DAY,
        )
    )

    assert night.panel != day.panel
    assert "night" in night.drivers
    assert "day" in day.drivers


def test_canonical_theme_is_stable_manual_fallback():
    palette = canonical_theme()

    assert palette.name == "canonical"
    assert palette.background == "#000000"
    assert palette.primary == "#9400D3"
    assert palette.secondary == "#00C2FF"
    assert palette.tertiary == "#39FF14"
    assert palette.drivers == ("manual",)
