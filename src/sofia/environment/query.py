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
    _TIMEZONE_FORMS = frozenset(
        {
            "what is my timezone",
            "what's my timezone",
            "what timezone am i in",
            "what time zone am i in",
            "what timezone are you using",
            "what time zone are you using",
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
            | cls._TIMEZONE_FORMS
            | cls._SEASON_FORMS
            | cls._DAYLIGHT_FORMS
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

        if normalized in self._TIME_FORMS:
            local = (
                snapshot.user_local_time
                or snapshot.host_local_time
            )
            if snapshot.user_local_time is not None:
                return EnvironmentQueryAnswer(
                    True,
                    (
                        "The current time in the configured/evidenced "
                        f"timezone ({snapshot.timezone}) is "
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
            qualifier = (
                f"in {snapshot.timezone}"
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
                        f"{current.source_id}."
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

        if normalized in self._TIMEZONE_FORMS:
            if snapshot.timezone is None:
                return EnvironmentQueryAnswer(
                    True,
                    "I don't have an evidenced user/site timezone.",
                )
            return EnvironmentQueryAnswer(
                True,
                (
                    "The configured/evidenced user-site timezone is "
                    f"{snapshot.timezone}."
                ),
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
