from datetime import datetime, timedelta, timezone

import pytest

from sofia.environment.config import (
    ConfiguredLocation,
    EnvironmentConfiguration,
)
from sofia.environment.model import (
    LocationEvidenceKind,
    LocationObservation,
    LocationSubject,
    ForecastPeriod,
    IndoorEnvironmentObservation,
    WeatherObservation,
)
from sofia.environment.provider import EnvironmentProviderObservation
from sofia.environment.query import EnvironmentQueryResolver
from sofia.environment.service import EnvironmentService


NOW = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)


class Provider:
    name = "query"

    def __init__(self, observation):
        self.observation = observation

    def observe(self, *, now):
        return self.observation


def config():
    return EnvironmentConfiguration(
        location=ConfiguredLocation(
            label="Configured area",
            timezone="America/Chicago",
            latitude=32.5,
            longitude=-97.1,
        )
    )


def test_direct_time_uses_evidenced_timezone_not_host_assumption():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what time is it?",
        snapshot=snapshot,
    )
    assert answer.recognized
    assert "America/Chicago" in answer.content


def test_direct_day_query_includes_weekday_and_iso_date():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what day is it?",
        snapshot=snapshot,
    )

    assert answer.recognized
    assert "Friday, September 25, 2026" in answer.content
    assert "2026-09-25" in answer.content
    assert "America/Chicago" in answer.content


def test_direct_location_distinguishes_configured_from_current():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "where am I?",
        snapshot=snapshot,
    )
    assert answer.recognized
    assert "configured location is Configured area" in answer.content
    assert "won't claim you're there right now" in answer.content


def test_direct_location_uses_only_fresh_user_current_evidence():
    current = LocationObservation(
        label="Current place",
        source_id="test.current",
        subject=LocationSubject.USER,
        kind=LocationEvidenceKind.CURRENT,
        timezone="America/Chicago",
        latitude=32.6,
        longitude=-97.2,
        precision_meters=12.0,
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=10),
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    current_location=current,
                )
            ),
        ),
    ).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what is my current location",
        snapshot=snapshot,
    )
    assert "Current location evidence says you're at Current place" in answer.content
    assert "precision about 12 m" in answer.content


def test_where_are_you_does_not_reuse_user_location_as_host_location():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "where are you?",
        snapshot=snapshot,
    )
    assert answer.recognized
    assert "runtime host/site" in answer.content
    assert "Configured area" not in answer.content


def test_timezone_query_reports_only_evidenced_timezone():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's my timezone?",
        snapshot=snapshot,
    )
    assert answer.content.endswith("America/Chicago.")


def test_current_weather_today_common_phrasings_are_recognized():
    resolver = EnvironmentQueryResolver()
    for query in (
        "what's the weather today?",
        "what is the weather today?",
        "how's the weather today?",
        "hows the weather",
        "how is the weather today?",
        "today's weather",
        "todays weather",
        "weather today",
    ):
        assert resolver.might_match(query), query


def test_direct_weather_refuses_stale_observation():
    weather = WeatherObservation(
        condition="rainy",
        observed_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(hours=1),
        source_id="test.weather",
        temperature_c=12.0,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    weather=weather,
                )
            ),
        ),
    ).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's the weather?",
        snapshot=snapshot,
    )
    assert answer.recognized
    assert "don't have current weather evidence" in answer.content
    assert "stale" in answer.content
    assert "12.0" not in answer.content


def test_direct_weather_reports_current_source_and_observation():
    weather = WeatherObservation(
        condition="clear",
        observed_at=NOW - timedelta(minutes=3),
        expires_at=NOW + timedelta(minutes=20),
        source_id="test.weather",
        location_label="Configured area",
        temperature_c=24.5,
        humidity_percent=40.0,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    weather=weather,
                )
            ),
        ),
    ).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's the weather like?",
        snapshot=snapshot,
    )
    assert "Current weather for Configured area: clear" in answer.content
    assert "76 °F" in answer.content
    assert "°C" not in answer.content
    assert "test.weather" in answer.content


def test_unknown_direct_environment_question_is_not_hijacked():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "Tell me a story about winter.",
        snapshot=snapshot,
    )
    assert not answer.recognized
    assert answer.content == ""

def test_my_timezone_does_not_relabel_host_timezone_as_user_timezone():
    host_config = EnvironmentConfiguration(
        location=ConfiguredLocation(
            label="Runtime host",
            timezone="America/Chicago",
            subject=LocationSubject.HOST,
            latitude=32.5,
            longitude=-97.1,
        )
    )
    snapshot = EnvironmentService(host_config).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's my timezone?",
        snapshot=snapshot,
    )
    assert answer.content == "I don't have an evidenced user timezone."

    context_answer = EnvironmentQueryResolver().resolve(
        "what timezone are you using?",
        snapshot=snapshot,
    )
    assert "host timezone" in context_answer.content
    assert "America/Chicago" in context_answer.content


def test_direct_forecast_returns_bounded_current_forecast():
    weather = WeatherObservation(
        condition="clear",
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=20),
        source_id="test.weather",
        forecast=(
            ForecastPeriod(
                starts_at=NOW + timedelta(hours=1),
                condition="cloudy",
                high_c=24.0,
                low_c=16.0,
                precipitation_probability=20.0,
            ),
        ),
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    weather=weather,
                )
            ),
        ),
    ).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's the forecast?",
        snapshot=snapshot,
    )
    assert "Current bounded forecast:" in answer.content
    assert "cloudy" in answer.content
    assert "high 75 °F" in answer.content
    assert "low 61 °F" in answer.content
    assert "°C" not in answer.content
    assert "precipitation 20%" in answer.content


def test_natural_tomorrow_weather_query_is_direct_and_host_timezone_aware():
    weather = WeatherObservation(
        condition="clear",
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=20),
        source_id="nws:test",
        location_label="Home Lab",
        forecast=(
            ForecastPeriod(
                starts_at=NOW + timedelta(hours=2),
                condition="clear tonight",
                low_c=20.0,
            ),
            ForecastPeriod(
                starts_at=NOW + timedelta(hours=20),
                condition="mostly sunny",
                high_c=30.0,
                precipitation_probability=10.0,
            ),
            ForecastPeriod(
                starts_at=NOW + timedelta(hours=32),
                condition="mostly clear",
                low_c=21.0,
                precipitation_probability=5.0,
            ),
            ForecastPeriod(
                starts_at=NOW + timedelta(hours=44),
                condition="next day",
                high_c=31.0,
            ),
        ),
    )
    snapshot = EnvironmentService(
        EnvironmentConfiguration(
            host_location=ConfiguredLocation(
                label="Home Lab",
                timezone="America/Chicago",
                subject=LocationSubject.HOST,
                latitude=32.9,
                longitude=-97.02,
                source_id="machine.location:test",
            )
        ),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    weather=weather,
                )
            ),
        ),
    ).snapshot(now=NOW)

    resolver = EnvironmentQueryResolver()
    assert resolver.might_match("whats tomorrows weather?")

    answer = resolver.resolve(
        "whats tomorrows weather?",
        snapshot=snapshot,
    )

    assert answer.recognized
    assert answer.content.startswith("Tomorrow's forecast:")
    assert "mostly sunny" in answer.content
    assert "high 86 °F" in answer.content
    assert "mostly clear" in answer.content
    assert "low 70 °F" in answer.content
    assert "clear tonight" not in answer.content
    assert "next day" not in answer.content
    assert "°C" not in answer.content


def test_tomorrow_weather_common_phrasings_are_recognized():
    resolver = EnvironmentQueryResolver()
    for query in (
        "what's tomorrow's weather?",
        "what is tomorrow's weather?",
        "what's the weather tomorrow?",
        "what will the weather be tomorrow?",
        "tomorrow's weather",
        "weather tomorrow",
    ):
        assert resolver.might_match(query), query


def test_weekly_weather_query_is_direct_fahrenheit_and_bounded_to_seven_days():
    weather = WeatherObservation(
        condition="clear",
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=20),
        source_id="nws:test",
        location_label="Home Lab",
        forecast=tuple(
            ForecastPeriod(
                starts_at=NOW + timedelta(days=day, hours=2),
                condition=f"day {day}",
                high_c=20.0 + day,
                precipitation_probability=float(day),
            )
            for day in range(8)
        ),
    )
    snapshot = EnvironmentService(
        EnvironmentConfiguration(
            host_location=ConfiguredLocation(
                label="Home Lab",
                timezone="America/Chicago",
                subject=LocationSubject.HOST,
                latitude=32.9,
                longitude=-97.02,
                source_id="machine.location:test",
            )
        ),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    weather=weather,
                )
            ),
        ),
    ).snapshot(now=NOW)

    resolver = EnvironmentQueryResolver()
    answer = resolver.resolve(
        "what's the 7 day forecast?",
        snapshot=snapshot,
    )

    assert answer.recognized
    assert answer.content.startswith("7-day forecast:")
    assert "day 0" in answer.content
    assert "day 5" in answer.content
    assert "day 6" in answer.content
    assert "day 7" not in answer.content
    assert "68 °F" in answer.content
    assert "°C" not in answer.content


def test_weekly_weather_common_phrasings_are_recognized():
    resolver = EnvironmentQueryResolver()
    for query in (
        "weekly forecast",
        "weekly weather",
        "what's the weather this week?",
        "this week's weather",
        "whats this weeks weather",
        "what's the 7 day forecast?",
        "seven day forecast",
    ):
        assert resolver.might_match(query), query


def test_sunrise_and_sunset_are_directly_queryable():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    sunrise = EnvironmentQueryResolver().resolve(
        "when is sunrise?",
        snapshot=snapshot,
    )
    sunset = EnvironmentQueryResolver().resolve(
        "when is sunset?",
        snapshot=snapshot,
    )
    assert sunrise.recognized
    assert "Approximate sunrise is" in sunrise.content
    assert sunset.recognized
    assert "Approximate sunset is" in sunset.content


def test_current_indoor_environment_is_directly_queryable():
    indoor = IndoorEnvironmentObservation(
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=10),
        source_id="test.indoor",
        temperature_c=22.0,
        humidity_percent=45.0,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    indoor=indoor,
                )
            ),
        ),
    ).snapshot(now=NOW)
    answer = EnvironmentQueryResolver().resolve(
        "what's the temperature inside?",
        snapshot=snapshot,
    )
    assert "temperature 72 °F" in answer.content
    assert "°C" not in answer.content
    assert "humidity 45%" in answer.content
    assert "test.indoor" in answer.content

def test_environment_context_sources_are_direct_and_privacy_bounded():
    snapshot = EnvironmentService(config()).snapshot(now=NOW)
    resolver = EnvironmentQueryResolver()

    assert resolver.might_match(
        "Explain your current environment context sources."
    )
    answer = resolver.resolve(
        "Explain your current environment context sources.",
        snapshot=snapshot,
    )

    assert answer.recognized
    assert "Environment context sources:" in answer.content
    assert "trusted runtime host clock" in answer.content
    assert "Configured area" in answer.content
    assert "config.environment" in answer.content
    assert "not current physical-location proof" in answer.content
    assert "Current physical location evidence: unavailable." in answer.content
    assert "Weather/forecast evidence: unavailable." in answer.content
    assert "32.5" not in answer.content
    assert "-97.1" not in answer.content

def test_where_are_you_uses_independent_host_location_not_user_location():
    snapshot = EnvironmentService(
        EnvironmentConfiguration(
            location=ConfiguredLocation(
                label="Sparks home",
                timezone="America/Chicago",
                subject=LocationSubject.USER,
                latitude=32.5,
                longitude=-97.1,
            ),
            host_location=ConfiguredLocation(
                label="Artemis server room",
                timezone="America/Chicago",
                subject=LocationSubject.HOST,
                latitude=32.6,
                longitude=-97.2,
                source_id="config.environment.host",
            ),
        )
    ).snapshot(now=NOW)

    answer = EnvironmentQueryResolver().resolve(
        "where are you?",
        snapshot=snapshot,
    )

    assert answer.recognized
    assert "Artemis server room" in answer.content
    assert "Sparks home" not in answer.content
    assert "not proof" in answer.content



def test_generic_source_followup_is_classified_without_globally_hijacking_it():
    resolver = EnvironmentQueryResolver()
    assert resolver.is_generic_source_followup("where you pull the info")
    assert resolver.is_weather_or_forecast_query("hows the weather")
    assert not resolver.might_match("where you pull the info")


def test_missing_weather_without_location_explains_location_dependency():
    snapshot = EnvironmentService(
        EnvironmentConfiguration()
    ).snapshot(now=NOW)

    answer = EnvironmentQueryResolver().resolve(
        "how is the weather",
        snapshot=snapshot,
    )

    assert answer.recognized
    assert "don't have current weather evidence" in answer.content
    assert "No configured or current location evidence" in answer.content


@pytest.mark.parametrize(
    "query",
    (
        "so whats the weather",
        "so whats the weather?",
        "so what's the weather",
        "whats the weather",
    ),
)
def test_casual_weather_phrasing_stays_deterministic(query):
    snapshot = EnvironmentService(
        EnvironmentConfiguration()
    ).snapshot(now=NOW)

    answer = EnvironmentQueryResolver().resolve(
        query,
        snapshot=snapshot,
    )

    assert answer.recognized
    assert "don't have current weather evidence" in answer.content
    assert "No configured or current location evidence" in answer.content


def test_literal_weather_and_time_are_deterministic():
    snapshot = EnvironmentService(
        EnvironmentConfiguration()
    ).snapshot(now=NOW)
    resolver = EnvironmentQueryResolver()

    weather = resolver.resolve("Weather", snapshot=snapshot)
    current_time = resolver.resolve("Time", snapshot=snapshot)

    assert weather.recognized
    assert "don't have current weather evidence" in weather.content
    assert current_time.recognized
    assert "host machine's current local time" in current_time.content


@pytest.mark.parametrize(
    "query",
    (
        "Use F not C",
        "fahrenheit not celsius",
        "use fahrenheit instead of celsius",
        "don't use celsius",
    ),
)
def test_temperature_unit_followup_cannot_become_fake_f_mode(query):
    snapshot = EnvironmentService(
        EnvironmentConfiguration()
    ).snapshot(now=NOW)

    answer = EnvironmentQueryResolver().resolve(
        query,
        snapshot=snapshot,
    )

    assert answer.recognized
    assert "Fahrenheit" in answer.content
    assert "Celsius" in answer.content
    assert "mode" not in answer.content.casefold()


def test_user_reported_local_time_preserves_am_pm_without_fake_conversion():
    snapshot = EnvironmentService(
        EnvironmentConfiguration()
    ).snapshot(now=NOW)

    answer = EnvironmentQueryResolver().resolve(
        "I was asleep and its 2:10 am for me",
        snapshot=snapshot,
    )

    assert answer.recognized
    assert "2:10 AM" in answer.content
    assert "PM" not in answer.content
    assert "does not prove a timezone or UTC conversion" in answer.content


def test_weather_source_live_wording_is_deterministic():
    weather = WeatherObservation(
        condition="cloudy",
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=20),
        source_id="nws:KGKY",
        location_label="Homelab",
        temperature_c=22.0,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    weather=weather,
                )
            ),
        ),
    ).snapshot(now=NOW)

    answer = EnvironmentQueryResolver().resolve(
        "what weather source are you using",
        snapshot=snapshot,
    )

    assert answer.recognized
    assert "Weather/forecast evidence: nws:KGKY" in answer.content
    assert "Coordinates and provider credentials are not exposed" in (
        answer.content
    )


def test_current_weather_uses_whole_fahrenheit_and_mph():
    weather = WeatherObservation(
        condition="light rain",
        observed_at=NOW - timedelta(minutes=2),
        expires_at=NOW + timedelta(minutes=20),
        source_id="nws:KGKY",
        location_label="Homelab",
        temperature_c=22.0,
        feels_like_c=22.7,
        humidity_percent=94.1,
        wind_kph=12.9,
    )
    snapshot = EnvironmentService(
        config(),
        providers=(
            Provider(
                EnvironmentProviderObservation(
                    weather=weather,
                )
            ),
        ),
    ).snapshot(now=NOW)

    answer = EnvironmentQueryResolver().resolve(
        "current weather?",
        snapshot=snapshot,
    )

    assert answer.recognized
    assert "72 °F" in answer.content
    assert "feels like 73 °F" in answer.content
    assert "humidity 94%" in answer.content
    assert "wind 8 mph" in answer.content
    assert ".0 °F" not in answer.content
    assert ".1 °F" not in answer.content
    assert "km/h" not in answer.content
