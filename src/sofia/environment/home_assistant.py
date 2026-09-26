"""Read-only Home Assistant provider for PKG-ENVIRONMENT.

The caller must explicitly configure entity IDs. Presence or arbitrary entity
state is never mined for location/weather by implication.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sofia.integrations.home_assistant import HomeAssistantAdapter

from .config import EnvironmentConfiguration
from .model import (
    ForecastPeriod,
    IndoorEnvironmentObservation,
    LocationEvidenceKind,
    LocationObservation,
    LocationSubject,
    WeatherObservation,
)
from .provider import EnvironmentProviderObservation


def _aware_timestamp(value: object, *, fallback: datetime) -> datetime:
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = fallback
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed.astimezone(timezone.utc)
    return fallback.astimezone(timezone.utc)


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def _temperature_c(value: object, unit: object) -> float | None:
    number = _number(value)
    if number is None:
        return None
    normalized = str(unit or "°C").strip().lower()
    if normalized in {"°f", "f", "fahrenheit"}:
        return (number - 32.0) * 5.0 / 9.0
    if normalized in {"k", "kelvin"}:
        return number - 273.15
    return number


def _wind_kph(value: object, unit: object) -> float | None:
    number = _number(value)
    if number is None:
        return None
    normalized = str(unit or "km/h").strip().lower()
    if normalized in {"mph", "mi/h"}:
        return number * 1.609344
    if normalized in {"m/s", "mps"}:
        return number * 3.6
    if normalized in {"kn", "kt", "knot", "knots"}:
        return number * 1.852
    return number


def _forecast(
    rows: object,
    *,
    temperature_unit: object,
) -> tuple[ForecastPeriod, ...]:
    if not isinstance(rows, list):
        return ()
    result: list[ForecastPeriod] = []
    for row in rows[:16]:
        if not isinstance(row, dict):
            continue
        raw_start = row.get("datetime")
        if not isinstance(raw_start, str) or not raw_start.strip():
            continue
        try:
            starts = datetime.fromisoformat(
                raw_start.replace("Z", "+00:00")
            )
        except ValueError:
            continue
        if starts.tzinfo is None or starts.utcoffset() is None:
            continue
        condition = str(row.get("condition") or "unknown").strip()
        if not condition:
            condition = "unknown"
        probability = _number(
            row.get("precipitation_probability")
        )
        try:
            period = ForecastPeriod(
                starts_at=starts,
                condition=condition,
                high_c=_temperature_c(
                    row.get("temperature"),
                    temperature_unit,
                ),
                low_c=_temperature_c(
                    row.get("templow"),
                    temperature_unit,
                ),
                precipitation_probability=probability,
            )
        except (TypeError, ValueError):
            continue
        result.append(period)
    return tuple(result)


class HomeAssistantEnvironmentProvider:
    """Normalize explicitly configured Home Assistant entities."""

    def __init__(
        self,
        adapter: HomeAssistantAdapter,
        configuration: EnvironmentConfiguration,
    ) -> None:
        if not isinstance(adapter, HomeAssistantAdapter):
            raise TypeError("adapter must be HomeAssistantAdapter")
        if not isinstance(configuration, EnvironmentConfiguration):
            raise TypeError(
                "configuration must be EnvironmentConfiguration"
            )
        if not configuration.home_assistant_enabled:
            raise ValueError(
                "Home Assistant environment provider has no configured entities"
            )
        self._adapter = adapter
        self._configuration = configuration

    @property
    def name(self) -> str:
        return "home_assistant"

    def _state(
        self,
        entity_id: str | None,
    ) -> dict[str, Any] | None:
        if entity_id is None:
            return None
        data = self._adapter.state(entity_id)
        if not isinstance(data, dict):
            raise RuntimeError(
                "Home Assistant environment entity returned invalid state"
            )
        return data

    def _weather(
        self,
        *,
        now: datetime,
    ) -> WeatherObservation | None:
        entity_id = self._configuration.home_assistant_weather_entity
        state = self._state(entity_id)
        if state is None or entity_id is None:
            return None
        raw_condition = state.get("state")
        if not isinstance(raw_condition, str):
            raise RuntimeError(
                "Home Assistant weather state has no condition"
            )
        condition = raw_condition.strip().lower()
        if not condition or condition in {"unknown", "unavailable"}:
            return None
        attrs = state.get("attributes")
        if not isinstance(attrs, dict):
            attrs = {}

        observed = _aware_timestamp(
            state.get("last_updated") or state.get("last_changed"),
            fallback=now,
        )
        expires = observed + timedelta(
            seconds=self._configuration.weather_max_age_seconds
        )
        location = attrs.get("friendly_name")
        location_label = (
            str(location).strip()
            if location is not None and str(location).strip()
            else None
        )
        temp_unit = (
            attrs.get("temperature_unit")
            or attrs.get("unit_of_measurement")
            or "°C"
        )
        wind_unit = attrs.get("wind_speed_unit") or "km/h"

        return WeatherObservation(
            condition=condition,
            observed_at=observed,
            expires_at=expires,
            source_id=f"home_assistant:{entity_id}",
            location_label=location_label,
            temperature_c=_temperature_c(
                attrs.get("temperature"),
                temp_unit,
            ),
            feels_like_c=_temperature_c(
                attrs.get("apparent_temperature"),
                temp_unit,
            ),
            humidity_percent=_number(attrs.get("humidity")),
            wind_kph=_wind_kph(
                attrs.get("wind_speed"),
                wind_unit,
            ),
            precipitation_mm=_number(
                attrs.get("precipitation")
            ),
            forecast=_forecast(
                attrs.get("forecast"),
                temperature_unit=temp_unit,
            ),
        )

    def _indoor(
        self,
        *,
        now: datetime,
    ) -> IndoorEnvironmentObservation | None:
        temp_entity = (
            self._configuration
            .home_assistant_indoor_temperature_entity
        )
        humidity_entity = (
            self._configuration
            .home_assistant_indoor_humidity_entity
        )
        temp_state = self._state(temp_entity)
        humidity_state = self._state(humidity_entity)
        if temp_state is None and humidity_state is None:
            return None

        timestamps: list[datetime] = []
        temperature_c = None
        humidity = None

        if temp_state is not None:
            attrs = temp_state.get("attributes")
            if not isinstance(attrs, dict):
                attrs = {}
            temperature_c = _temperature_c(
                temp_state.get("state"),
                attrs.get("unit_of_measurement") or "°C",
            )
            timestamps.append(
                _aware_timestamp(
                    temp_state.get("last_updated")
                    or temp_state.get("last_changed"),
                    fallback=now,
                )
            )

        if humidity_state is not None:
            humidity = _number(humidity_state.get("state"))
            timestamps.append(
                _aware_timestamp(
                    humidity_state.get("last_updated")
                    or humidity_state.get("last_changed"),
                    fallback=now,
                )
            )

        if temperature_c is None and humidity is None:
            return None

        observed = min(timestamps) if timestamps else now
        sources = [
            item
            for item in (temp_entity, humidity_entity)
            if item is not None
        ]
        return IndoorEnvironmentObservation(
            observed_at=observed,
            expires_at=observed
            + timedelta(
                seconds=self._configuration.indoor_max_age_seconds
            ),
            source_id=(
                "home_assistant:"
                + ",".join(sources)
            ),
            temperature_c=temperature_c,
            humidity_percent=humidity,
        )

    def _location(
        self,
        *,
        now: datetime,
    ) -> LocationObservation | None:
        entity_id = (
            self._configuration
            .home_assistant_current_location_entity
        )
        state = self._state(entity_id)
        if state is None or entity_id is None:
            return None
        attrs = state.get("attributes")
        if not isinstance(attrs, dict):
            attrs = {}
        latitude = _number(attrs.get("latitude"))
        longitude = _number(attrs.get("longitude"))
        if latitude is None or longitude is None:
            return None

        state_label = state.get("state")
        label = (
            str(state_label).strip()
            if isinstance(state_label, str)
            and state_label.strip()
            and state_label.strip().lower()
            not in {"unknown", "unavailable", "not_home"}
            else "current location"
        )
        observed = _aware_timestamp(
            state.get("last_updated") or state.get("last_changed"),
            fallback=now,
        )
        configured = self._configuration.location
        timezone_name = (
            configured.timezone
            if configured is not None
            else None
        )
        subject = (
            configured.subject
            if configured is not None
            else LocationSubject.USER
        )
        return LocationObservation(
            label=label,
            source_id=f"home_assistant:{entity_id}",
            subject=subject,
            kind=LocationEvidenceKind.CURRENT,
            timezone=timezone_name,
            latitude=latitude,
            longitude=longitude,
            observed_at=observed,
        )

    def observe(
        self,
        *,
        now: datetime,
    ) -> EnvironmentProviderObservation:
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError("environment provider time must be aware")
        return EnvironmentProviderObservation(
            weather=self._weather(now=now),
            indoor=self._indoor(now=now),
            current_location=self._location(now=now),
        )
