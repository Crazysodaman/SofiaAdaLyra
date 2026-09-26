"""Deterministic answers for direct current-environment questions.

The LLM may discuss environment conversationally, but direct factual questions
must not override typed freshness/location evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

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
    return " ".join(query.strip().casefold().split()).rstrip(" ?!.")


class EnvironmentQueryResolver:
    _TIME_FORMS = frozenset(
        {
            "what time is it",
            "what time is it right now",
            "what's the time",
            "what is the current time",
            "current time",
        }
    )
    _DATE_FORMS = frozenset(
        {
            "what date is it",
            "what's the date",
            "what is today's date",
            "what day is it",
            "what day is it today",
        }
    )
    _WEATHER_FORMS = frozenset(
        {
            "what's the weather",
            "what is the weather",
            "what's the weather like",
            "what is the weather like",
            "what's the weather right now",
            "what is the weather right now",
            "how's the weather",
            "how is the weather",
        }
    )
    _LOCATION_FORMS = frozenset(
        {
            "where am i",
            "what is my location",
            "what's my location",
            "what is my current location",
            "what's my current location",
            "do you know where i am",
        }
    )
    _SOFIA_LOCATION_FORMS = frozenset(
        {
            "where are you",
            "what is your location",
            "what's your location",
            "what is your current location",
            "what's your current location",
            "do you know where you are",
        }
    )
    _USER_TIMEZONE_FORMS = frozenset(
        {
            "what is my timezone",
            "what's my timezone",
            "what timezone am i in",
            "what time zone am i in",
        }
    )
    _CONTEXT_TIMEZONE_FORMS = frozenset(
        {
            "what timezone are you using",
            "what time zone are you using",
            "what timezone is configured",
            "what time zone is configured",
        }
    )
    _FORECAST_FORMS = frozenset(
        {
            "what's the forecast",
            "what is the forecast",
            "what's the weather forecast",
            "what is the weather forecast",
            "what's the forecast tomorrow",
            "what is the forecast tomorrow",
        }
    )
    _SUNRISE_FORMS = frozenset(
        {
            "when is sunrise",
            "what time is sunrise",
            "when does the sun rise",
        }
    )
    _SUNSET_FORMS = frozenset(
        {
            "when is sunset",
            "what time is sunset",
            "when does the sun set",
        }
    )
    _INDOOR_FORMS = frozenset(
        {
            "what's the indoor temperature",
            "what is the indoor temperature",
            "what's the temperature inside",
            "what is the temperature inside",
            "what's the indoor humidity",
            "what is the indoor humidity",
        }
    )
    _SEASON_FORMS = frozenset(
        {
            "what season is it",
            "what's the season",
            "what season are we in",
            "what is the current season",
        }
    )
    _DAYLIGHT_FORMS = frozenset(
        {
            "is it day",
            "is it daytime",
            "is it night",
            "is it nighttime",
            "is it dark outside",
            "is it light outside",
        }
    )
    _CONTEXT_SOURCE_FORMS = frozenset(
        {
            "explain your current environment context sources",
            "what are your current environment context sources",
            "what are your environment context sources",
            "what environment sources are you using",
            "where does your environment context come from",
        }
    )

    @classmethod
    def might_match(cls, query: str) -> bool:
        if not isinstance(query, str):
            return False
        normalized = _normalize(query)
        return normalized in (
            cls._TIME_FORMS
            | cls._DATE_FORMS
            | cls._WEATHER_FORMS
            | cls._LOCATION_FORMS
            | cls._SOFIA_LOCATION_FORMS
            | cls._USER_TIMEZONE_FORMS
            | cls._CONTEXT_TIMEZONE_FORMS
            | cls._FORECAST_FORMS
            | cls._SUNRISE_FORMS
            | cls._SUNSET_FORMS
            | cls._INDOOR_FORMS
            | cls._SEASON_FORMS
            | cls._DAYLIGHT_FORMS
            | cls._CONTEXT_SOURCE_FORMS
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

        if normalized in self._CONTEXT_SOURCE_FORMS:
            sources = [
                "Environment context sources:",
                "- Clock: trusted runtime host clock.",
            ]
            configured = snapshot.configured_location
            if configured is None:
                sources.append("- Configured location: unavailable.")
            else:
                sources.append(
                    "- Configured location: "
                    f"{configured.label} ({configured.subject.value}) "
                    f"from {configured.source_id}; configuration is not "
                    "current physical-location proof."
                )

            current = snapshot.current_location
            if current is None:
                sources.append(
                    "- Current physical location evidence: unavailable."
                )
            else:
                sources.append(
                    "- Current physical location evidence: "
                    f"{current.source_id} "
                    f"({snapshot.current_location_freshness.value}, "
                    f"subject={current.subject.value})."
                )

            if snapshot.timezone is None:
                sources.append("- Environment timezone: unavailable.")
            else:
                sources.append(
                    "- Environment timezone: "
                    f"{snapshot.timezone}, derived from the effective "
                    "location evidence."
                )

            if snapshot.season is None:
                sources.append("- Season: unavailable.")
            else:
                sources.append(
                    "- Season: derived from the effective location and date."
                )

            if snapshot.daylight is None:
                sources.append("- Daylight/sunrise/sunset: unavailable.")
            else:
                sources.append(
                    "- Daylight/sunrise/sunset: derived from the effective "
                    "location, date, and timezone."
                )

            weather = snapshot.weather
            if weather is None:
                sources.append("- Weather/forecast evidence: unavailable.")
            else:
                sources.append(
                    "- Weather/forecast evidence: "
                    f"{weather.source_id} "
                    f"({snapshot.weather_freshness.value})."
                )

            indoor = snapshot.indoor
            if indoor is None:
                sources.append("- Indoor environment evidence: unavailable.")
            else:
                sources.append(
                    "- Indoor environment evidence: "
                    f"{indoor.source_id} "
                    f"({snapshot.indoor_freshness.value})."
                )

            if snapshot.provider_errors:
                sources.append(
                    "- Provider status: degraded evidence is present; "
                    "provider error details are intentionally bounded."
                )

            sources.append(
                "Coordinates and provider credentials are not exposed in "
                "this report."
            )
            return EnvironmentQueryAnswer(
                True,
                "\n".join(sources),
            )

        if normalized in self._TIME_FORMS:
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

        if normalized in self._DATE_FORMS:
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
            return EnvironmentQueryAnswer(
                True,
                f"The current date {qualifier} is {local.date().isoformat()}.",
            )

        if normalized in self._LOCATION_FORMS:
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

        if normalized in self._WEATHER_FORMS:
            weather = snapshot.weather
            if (
                weather is None
                or snapshot.weather_freshness
                is not EnvironmentFreshness.CURRENT
            ):
                freshness = snapshot.weather_freshness.value
                return EnvironmentQueryAnswer(
                    True,
                    (
                        "I don't have current weather evidence"
                        + (
                            f"; the available observation is {freshness}."
                            if weather is not None
                            else "."
                        )
                    ),
                )
            parts = [weather.condition]
            if weather.temperature_c is not None:
                parts.append(
                    f"{weather.temperature_c:.1f} °C"
                )
            if weather.feels_like_c is not None:
                parts.append(
                    f"feels like {weather.feels_like_c:.1f} °C"
                )
            if weather.humidity_percent is not None:
                parts.append(
                    f"humidity {weather.humidity_percent:.0f}%"
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

        if normalized in self._SOFIA_LOCATION_FORMS:
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
            configured = snapshot.configured_location
            if (
                configured is not None
                and configured.subject
                in {LocationSubject.HOST, LocationSubject.SITE}
            ):
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

        if normalized in self._USER_TIMEZONE_FORMS:
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

        if normalized in self._CONTEXT_TIMEZONE_FORMS:
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

        if normalized in self._FORECAST_FORMS:
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
            periods = []
            for period in weather.forecast[:4]:
                parts = [period.condition]
                if period.high_c is not None:
                    parts.append(f"high {period.high_c:.1f} °C")
                if period.low_c is not None:
                    parts.append(f"low {period.low_c:.1f} °C")
                if period.precipitation_probability is not None:
                    parts.append(
                        "precipitation "
                        f"{period.precipitation_probability:.0f}%"
                    )
                periods.append(
                    f"{period.starts_at.isoformat()}: "
                    + ", ".join(parts)
                )
            return EnvironmentQueryAnswer(
                True,
                "Current bounded forecast: " + "; ".join(periods) + ".",
            )

        if normalized in self._SUNRISE_FORMS:
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

        if normalized in self._SUNSET_FORMS:
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

        if normalized in self._INDOOR_FORMS:
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
                    f"temperature {indoor.temperature_c:.1f} °C"
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

        if normalized in self._SEASON_FORMS:
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

        if normalized in self._DAYLIGHT_FORMS:
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
