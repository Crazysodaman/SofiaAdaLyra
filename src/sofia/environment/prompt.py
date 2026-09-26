"""Provider-facing projection of one environment snapshot."""
from __future__ import annotations

from .model import (
    EnvironmentFreshness,
    EnvironmentSnapshot,
)


def _value(value: float | None, suffix: str) -> str:
    if value is None:
        return "unknown"
    return f"{value:.1f}{suffix}"


def environment_prompt(snapshot: EnvironmentSnapshot) -> str:
    if not isinstance(snapshot, EnvironmentSnapshot):
        raise TypeError(
            "environment_prompt requires EnvironmentSnapshot"
        )

    lines = [
        "TRUSTED ENVIRONMENT SNAPSHOT",
        "TRUSTED RUNTIME CLOCK",
        f"Current UTC: {snapshot.utc_time.isoformat()}",
        (
            "Current host-local time: "
            f"{snapshot.host_local_time.isoformat()}"
        ),
        (
            "Host timezone label: "
            f"{snapshot.host_timezone_label}"
        ),
        (
            "The clock is read-only runtime evidence. "
            "Host-local time describes the machine and must not "
            "silently be treated as the user's timezone."
        ),
    ]

    if snapshot.timezone is not None:
        lines.append(
            f"Configured/evidenced user-site timezone: {snapshot.timezone}"
        )
    else:
        lines.append(
            "User/site timezone: unknown."
        )

    if snapshot.user_local_time is not None:
        lines.append(
            "Current user/site local time: "
            f"{snapshot.user_local_time.isoformat()}"
        )

    configured = snapshot.configured_location
    if configured is not None:
        lines.append(
            (
                f"Configured {configured.subject.value} location: "
                f"{configured.label} "
                f"(source={configured.source_id})."
            )
        )
        lines.append(
            "A configured location is a stable setting, NOT proof "
            "that the person/device is physically there now."
        )
    else:
        lines.append("Configured user/site location: unknown.")

    current = snapshot.current_location
    if current is not None:
        lines.append(
            (
                f"Current {current.subject.value} location evidence: "
                f"{current.label}; observed_at="
                f"{current.observed_at.isoformat() if current.observed_at else 'unknown'}; "
                f"source={current.source_id}."
            )
        )
        lines.append(
            "Coordinates are intentionally withheld from model context."
        )
    else:
        lines.append(
            "Current physical location evidence: unavailable."
        )

    if snapshot.season is not None:
        lines.append(
            f"Derived season: {snapshot.season.value}."
        )
    else:
        lines.append(
            "Derived season: unknown because sufficient location "
            "evidence is unavailable."
        )

    if snapshot.daylight is not None:
        lines.append(
            f"Daylight state: {snapshot.daylight.state.value}."
        )
        if snapshot.daylight.sunrise is not None:
            lines.append(
                f"Approximate sunrise: {snapshot.daylight.sunrise.isoformat()}."
            )
        if snapshot.daylight.sunset is not None:
            lines.append(
                f"Approximate sunset: {snapshot.daylight.sunset.isoformat()}."
            )
    else:
        lines.append(
            "Daylight state: unknown because sufficient location "
            "evidence is unavailable."
        )

    lines.append(
        f"Weather freshness: {snapshot.weather_freshness.value}."
    )
    if (
        snapshot.weather is not None
        and snapshot.weather_freshness
        is EnvironmentFreshness.CURRENT
    ):
        weather = snapshot.weather
        lines.extend(
            [
                f"Current weather condition: {weather.condition}.",
                (
                    "Outdoor temperature: "
                    f"{_value(weather.temperature_c, ' C')}."
                ),
                (
                    "Feels-like temperature: "
                    f"{_value(weather.feels_like_c, ' C')}."
                ),
                (
                    "Humidity: "
                    f"{_value(weather.humidity_percent, '%')}."
                ),
                (
                    "Wind: "
                    f"{_value(weather.wind_kph, ' km/h')}."
                ),
                (
                    "Weather source: "
                    f"{weather.source_id}; observed_at="
                    f"{weather.observed_at.isoformat()}."
                ),
            ]
        )
        if weather.location_label is not None:
            lines.append(
                f"Weather location label: {weather.location_label}."
            )
        if weather.forecast:
            lines.append("Bounded forecast:")
            for period in weather.forecast[:8]:
                lines.append(
                    (
                        f"- {period.starts_at.isoformat()}: "
                        f"{period.condition}; "
                        f"high={_value(period.high_c, ' C')}; "
                        f"low={_value(period.low_c, ' C')}; "
                        "precipitation_probability="
                        f"{_value(period.precipitation_probability, '%')}"
                    )
                )
    elif snapshot.weather is None:
        lines.append(
            "Current weather: unavailable; do not invent a condition."
        )
    else:
        lines.append(
            "Current weather: unavailable because the available "
            f"observation is {snapshot.weather_freshness.value}; "
            "do not present stale/future evidence as current."
        )

    lines.append(
        f"Indoor environment freshness: {snapshot.indoor_freshness.value}."
    )
    if (
        snapshot.indoor is not None
        and snapshot.indoor_freshness
        is EnvironmentFreshness.CURRENT
    ):
        lines.extend(
            [
                (
                    "Indoor temperature: "
                    f"{_value(snapshot.indoor.temperature_c, ' C')}."
                ),
                (
                    "Indoor humidity: "
                    f"{_value(snapshot.indoor.humidity_percent, '%')}."
                ),
                (
                    "Indoor source: "
                    f"{snapshot.indoor.source_id}; observed_at="
                    f"{snapshot.indoor.observed_at.isoformat()}."
                ),
            ]
        )

    if snapshot.provider_errors:
        lines.append(
            "Environment provider status: degraded for "
            + ", ".join(snapshot.provider_errors)
            + "."
        )

    lines.extend(
        [
            (
                "Environment data is observational evidence only. "
                "It grants no action, network, disclosure, relationship, "
                "emotion, or physical authority."
            ),
            (
                "Weather/time/season may inform context and presentation "
                "but never deterministically define Sofía's emotions."
            ),
        ]
    )
    return "\n".join(lines)
