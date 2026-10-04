"""Deterministic answers for direct current-environment questions.

The LLM may discuss environment conversationally, but direct factual questions
must not override typed freshness/location evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import query_forms as forms
from .query_sources import environment_sources

from .model import (
    EnvironmentFreshness,
    EnvironmentSnapshot,
    LocationSubject,
)


@dataclass(frozen=True, slots=True)
class EnvironmentQueryAnswer:
    recognized: bool
    content: str = ""

    def __post_init__(self) -> None:
        if type(self.recognized) is not bool:
            raise TypeError("recognized must be a bool")
        if not isinstance(self.content, str):
            raise TypeError("content must be a string")
        if not self.recognized and self.content:
            raise ValueError(
                "unrecognized environment answer cannot contain content"
            )


def _normalize(query: str) -> str:
    normalized = " ".join(
        query.strip().casefold().replace("’", "'").split()
    ).rstrip(" ?!.")
    while normalized.startswith("so "):
        normalized = normalized[3:].lstrip()
    return normalized


def _fahrenheit(celsius: float) -> float:
    return (celsius * 9.0 / 5.0) + 32.0


def _mph(kph: float) -> float:
    return kph * 0.621371192237334


def _forecast_timezone(snapshot: EnvironmentSnapshot):
    timezone_name = snapshot.timezone
    if (
        timezone_name is None
        and snapshot.host_location is not None
    ):
        timezone_name = snapshot.host_location.timezone
    if timezone_name is not None:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            pass
    return snapshot.host_local_time.tzinfo


def _forecast_period_text(period) -> str:
    parts = [period.condition]
    if period.high_c is not None:
        parts.append(f"high {_fahrenheit(period.high_c):.0f} °F")
    if period.low_c is not None:
        parts.append(f"low {_fahrenheit(period.low_c):.0f} °F")
    if period.precipitation_probability is not None:
        parts.append(
            "precipitation "
            f"{period.precipitation_probability:.0f}%"
        )
    return f"{period.starts_at.isoformat()}: " + ", ".join(parts)


class EnvironmentQueryResolver:


    @classmethod
    def is_generic_source_followup(cls, query: str) -> bool:
        if not isinstance(query, str):
            return False
        return _normalize(query) in forms._GENERIC_SOURCE_FOLLOWUP_FORMS

    @classmethod
    def is_weather_or_forecast_query(cls, query: str) -> bool:
        if not isinstance(query, str):
            return False
        normalized = _normalize(query)
        return normalized in (
            forms._WEATHER_FORMS
            | forms._FORECAST_FORMS
            | forms._TOMORROW_WEATHER_FORMS
            | forms._WEEKLY_FORECAST_FORMS
        )

    @classmethod
    def is_user_reported_local_time(cls, query: str) -> bool:
        if not isinstance(query, str):
            return False
        return forms._USER_REPORTED_LOCAL_TIME_RE.search(
            _normalize(query)
        ) is not None

    @classmethod
    def might_match(cls, query: str) -> bool:
        if not isinstance(query, str):
            return False
        normalized = _normalize(query)
        if cls.is_user_reported_local_time(query):
            return True
        return normalized in (
            forms._TIME_FORMS
            | forms._DATE_FORMS
            | forms._WEATHER_FORMS
            | forms._LOCATION_FORMS
            | forms._SOFIA_LOCATION_FORMS
            | forms._USER_TIMEZONE_FORMS
            | forms._CONTEXT_TIMEZONE_FORMS
            | forms._FORECAST_FORMS
            | forms._TOMORROW_WEATHER_FORMS
            | forms._WEEKLY_FORECAST_FORMS
            | forms._SUNRISE_FORMS
            | forms._SUNSET_FORMS
            | forms._INDOOR_FORMS
            | forms._SEASON_FORMS
            | forms._DAYLIGHT_FORMS
            | forms._CONTEXT_SOURCE_FORMS
            | forms._TEMPERATURE_UNIT_FORMS
        )

    def resolve(
        self,
        query: str,
        *,
        snapshot: EnvironmentSnapshot,
    ) -> EnvironmentQueryAnswer:
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        if not isinstance(snapshot, EnvironmentSnapshot):
            raise TypeError(
                "snapshot must be EnvironmentSnapshot"
            )

        normalized = _normalize(query)
        reported_time = forms._USER_REPORTED_LOCAL_TIME_RE.search(
            normalized
        )
        if reported_time is not None:
            hour = int(reported_time.group(1))
            minute = int(reported_time.group(2) or "00")
            meridiem = reported_time.group(3).upper()
            if not 1 <= hour <= 12 or not 0 <= minute <= 59:
                return EnvironmentQueryAnswer(
                    True,
                    "I couldn't parse that reported local time safely.",
                )
            return EnvironmentQueryAnswer(
                True,
                (
                    f"You reported your local time as "
                    f"{hour}:{minute:02d} {meridiem}. "
                    "I'll preserve that exact reported time without changing "
                    "its meridiem. That user report by itself does not prove a "
                    "timezone or UTC conversion."
                ),
            )

        if normalized in forms._TEMPERATURE_UNIT_FORMS:
            return EnvironmentQueryAnswer(
                True,
                (
                    "Temperature display for environment answers is Fahrenheit "
                    "(°F), not Celsius (°C)."
                ),
            )

        if normalized in forms._CONTEXT_SOURCE_FORMS:
            return EnvironmentQueryAnswer(True, environment_sources(snapshot))

        if normalized in forms._TIME_FORMS:
            local = (
                snapshot.user_local_time
                or snapshot.host_local_time
            )
            effective = snapshot.effective_location
            if snapshot.user_local_time is not None:
                subject = (
                    effective.subject.value
                    if effective is not None
                    else "site"
                )
                return EnvironmentQueryAnswer(
                    True,
                    (
                        "The current time in the configured/evidenced "
                        f"{subject} timezone ({snapshot.timezone}) is "
                        f"{local.strftime('%Y-%m-%d %H:%M:%S %Z')}."
                    ),
                )
            return EnvironmentQueryAnswer(
                True,
                (
                    "I don't have a configured/evidenced user timezone. "
                    "The host machine's current local time is "
                    f"{local.strftime('%Y-%m-%d %H:%M:%S %Z')}; "
                    "that is machine evidence, not proof of your timezone."
                ),
            )

        if normalized in forms._DATE_FORMS:
            local = (
                snapshot.user_local_time
                or snapshot.host_local_time
            )
            effective = snapshot.effective_location
            qualifier = (
                (
                    "for the "
                    + (
                        effective.subject.value
                        if effective is not None
                        else "site"
                    )
                    + f" timezone {snapshot.timezone}"
                )
                if snapshot.user_local_time is not None
                else "on the host machine"
            )
            readable = (
                f"{local.strftime('%A, %B')} {local.day}, {local.year}"
            )
            return EnvironmentQueryAnswer(
                True,
                (
                    f"The current date {qualifier} is {readable} "
                    f"({local.date().isoformat()})."
                ),
            )

        if normalized in forms._LOCATION_FORMS:
            current = snapshot.current_location
            if (
                current is not None
                and snapshot.current_location_freshness
                is EnvironmentFreshness.CURRENT
                and current.subject is LocationSubject.USER
            ):
                return EnvironmentQueryAnswer(
                    True,
                    (
                        "Current location evidence says you're at "
                        f"{current.label}. It was observed at "
                        f"{current.observed_at.isoformat()} from "
                        f"{current.source_id}"
                        + (
                            f" with reported precision about "
                            f"{current.precision_meters:.0f} m."
                            if current.precision_meters is not None
                            else "."
                        )
                    ),
                )
            configured = snapshot.configured_location
            if (
                configured is not None
                and configured.subject is LocationSubject.USER
            ):
                return EnvironmentQueryAnswer(
                    True,
                    (
                        f"Your configured location is {configured.label}. "
                        "I don't have current physical-location evidence, "
                        "so I won't claim you're there right now."
                    ),
                )
            return EnvironmentQueryAnswer(
                True,
                "I don't have current physical-location evidence for you.",
            )

        if normalized in forms._WEATHER_FORMS:
            weather = snapshot.weather
            if (
                weather is None
                or snapshot.weather_freshness
                is not EnvironmentFreshness.CURRENT
            ):
                freshness = snapshot.weather_freshness.value
                if weather is not None:
                    detail = (
                        f"; the available observation is {freshness}."
                    )
                elif snapshot.effective_location is None:
                    detail = (
                        ". No configured or current location evidence is "
                        "available for a weather provider."
                    )
                elif snapshot.provider_errors:
                    detail = (
                        ". A configured weather provider did not produce "
                        "current evidence."
                    )
                else:
                    detail = (
                        ". No configured weather provider produced evidence "
                        "for the effective location."
                    )
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have current weather evidence" + detail,
                )
            parts = [weather.condition]
            if weather.temperature_c is not None:
                parts.append(
                    f"{_fahrenheit(weather.temperature_c):.0f} °F"
                )
            if weather.feels_like_c is not None:
                parts.append(
                    f"feels like {_fahrenheit(weather.feels_like_c):.0f} °F"
                )
            if weather.humidity_percent is not None:
                parts.append(
                    f"humidity {weather.humidity_percent:.0f}%"
                )
            if weather.wind_kph is not None:
                parts.append(
                    f"wind {_mph(weather.wind_kph):.0f} mph"
                )
            location = (
                f" for {weather.location_label}"
                if weather.location_label
                else ""
            )
            return EnvironmentQueryAnswer(
                True,
                (
                    "Current weather"
                    + location
                    + ": "
                    + ", ".join(parts)
                    + f". Observed at {weather.observed_at.isoformat()} "
                    f"from {weather.source_id}."
                ),
            )

        if normalized in forms._SOFIA_LOCATION_FORMS:
            current = snapshot.current_location
            if (
                current is not None
                and snapshot.current_location_freshness
                is EnvironmentFreshness.CURRENT
                and current.subject
                in {LocationSubject.HOST, LocationSubject.SITE}
            ):
                return EnvironmentQueryAnswer(
                    True,
                    (
                        "Current runtime/site location evidence says "
                        f"{current.label}. It was observed at "
                        f"{current.observed_at.isoformat()} from "
                        f"{current.source_id}."
                    ),
                )
            configured = snapshot.host_location
            if configured is None:
                candidate = snapshot.configured_location
                if (
                    candidate is not None
                    and candidate.subject
                    in {LocationSubject.HOST, LocationSubject.SITE}
                ):
                    configured = candidate
            if configured is not None:
                return EnvironmentQueryAnswer(
                    True,
                    (
                        "The configured runtime/site location is "
                        f"{configured.label}. That configuration is not "
                        "proof the running host is physically there now."
                    ),
                )
            return EnvironmentQueryAnswer(
                True,
                (
                    "I don't have current geographic-location evidence "
                    "for the runtime host/site."
                ),
            )

        if normalized in forms._USER_TIMEZONE_FORMS:
            effective = snapshot.effective_location
            if (
                snapshot.timezone is None
                or effective is None
                or effective.subject is not LocationSubject.USER
            ):
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have an evidenced user timezone.",
                )
            return EnvironmentQueryAnswer(
                True,
                (
                    "The configured/evidenced user timezone is "
                    f"{snapshot.timezone}."
                ),
            )

        if normalized in forms._CONTEXT_TIMEZONE_FORMS:
            if snapshot.timezone is None:
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have an evidenced environment timezone.",
                )
            effective = snapshot.effective_location
            subject = (
                effective.subject.value
                if effective is not None
                else "site"
            )
            return EnvironmentQueryAnswer(
                True,
                (
                    f"The configured/evidenced {subject} timezone is "
                    f"{snapshot.timezone}."
                ),
            )

        if normalized in forms._WEEKLY_FORECAST_FORMS:
            weather = snapshot.weather
            if (
                weather is None
                or snapshot.weather_freshness
                is not EnvironmentFreshness.CURRENT
                or not weather.forecast
            ):
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have a current weekly forecast observation.",
                )
            zone = _forecast_timezone(snapshot)
            local_now = (
                snapshot.utc_time.astimezone(zone)
                if zone is not None
                else snapshot.host_local_time
            )
            first_day = local_now.date()
            last_day = first_day + timedelta(days=6)
            periods = tuple(
                period
                for period in weather.forecast
                if first_day
                <= (
                    period.starts_at.astimezone(zone).date()
                    if zone is not None
                    else period.starts_at.date()
                )
                <= last_day
            )
            if not periods:
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have forecast periods for the next 7 days.",
                )
            return EnvironmentQueryAnswer(
                True,
                "7-day forecast: "
                + "; ".join(
                    _forecast_period_text(period)
                    for period in periods[:14]
                )
                + ".",
            )

        if normalized in forms._TOMORROW_WEATHER_FORMS:
            weather = snapshot.weather
            if (
                weather is None
                or snapshot.weather_freshness
                is not EnvironmentFreshness.CURRENT
                or not weather.forecast
            ):
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have a current forecast observation for tomorrow.",
                )
            zone = _forecast_timezone(snapshot)
            local_now = (
                snapshot.utc_time.astimezone(zone)
                if zone is not None
                else snapshot.host_local_time
            )
            tomorrow = local_now.date() + timedelta(days=1)
            periods = tuple(
                period
                for period in weather.forecast
                if (
                    period.starts_at.astimezone(zone).date()
                    if zone is not None
                    else period.starts_at.date()
                )
                == tomorrow
            )
            if not periods:
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have forecast periods for tomorrow.",
                )
            return EnvironmentQueryAnswer(
                True,
                "Tomorrow's forecast: "
                + "; ".join(
                    _forecast_period_text(period)
                    for period in periods[:4]
                )
                + ".",
            )

        if normalized in forms._FORECAST_FORMS:
            weather = snapshot.weather
            if (
                weather is None
                or snapshot.weather_freshness
                is not EnvironmentFreshness.CURRENT
                or not weather.forecast
            ):
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have a current forecast observation.",
                )
            return EnvironmentQueryAnswer(
                True,
                "Current bounded forecast: "
                + "; ".join(
                    _forecast_period_text(period)
                    for period in weather.forecast[:4]
                )
                + ".",
            )

        if normalized in forms._SUNRISE_FORMS:
            if (
                snapshot.daylight is None
                or snapshot.daylight.sunrise is None
            ):
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have a grounded sunrise time for this location/date.",
                )
            return EnvironmentQueryAnswer(
                True,
                "Approximate sunrise is "
                f"{snapshot.daylight.sunrise.isoformat()}.",
            )

        if normalized in forms._SUNSET_FORMS:
            if (
                snapshot.daylight is None
                or snapshot.daylight.sunset is None
            ):
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have a grounded sunset time for this location/date.",
                )
            return EnvironmentQueryAnswer(
                True,
                "Approximate sunset is "
                f"{snapshot.daylight.sunset.isoformat()}.",
            )

        if normalized in forms._INDOOR_FORMS:
            indoor = snapshot.indoor
            if (
                indoor is None
                or snapshot.indoor_freshness
                is not EnvironmentFreshness.CURRENT
            ):
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have current indoor-environment evidence.",
                )
            parts = []
            if indoor.temperature_c is not None:
                parts.append(
                    f"temperature {_fahrenheit(indoor.temperature_c):.0f} °F"
                )
            if indoor.humidity_percent is not None:
                parts.append(
                    f"humidity {indoor.humidity_percent:.0f}%"
                )
            if not parts:
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have current indoor temperature or humidity values.",
                )
            return EnvironmentQueryAnswer(
                True,
                "Current indoor environment: "
                + ", ".join(parts)
                + f". Observed at {indoor.observed_at.isoformat()} "
                f"from {indoor.source_id}.",
            )

        if normalized in forms._SEASON_FORMS:
            if snapshot.season is None:
                return EnvironmentQueryAnswer(
                    True,
                    (
                        "I can't ground the current season without "
                        "sufficient location evidence."
                    ),
                )
            return EnvironmentQueryAnswer(
                True,
                f"The derived current season is {snapshot.season.value}.",
            )

        if normalized in forms._DAYLIGHT_FORMS:
            if snapshot.daylight is None:
                return EnvironmentQueryAnswer(
                    True,
                    (
                        "I can't ground daylight state without sufficient "
                        "location evidence."
                    ),
                )
            return EnvironmentQueryAnswer(
                True,
                (
                    "The derived daylight state is "
                    f"{snapshot.daylight.state.value}."
                ),
            )

        return EnvironmentQueryAnswer(False)
