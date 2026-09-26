"""Configuration for PKG-ENVIRONMENT.

Configuration may describe a stable user/site location, but configuration is
never promoted to proof of the user's current physical position.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .model import LocationSubject


@dataclass(frozen=True, slots=True)
class ConfiguredLocation:
    label: str
    timezone: str
    subject: LocationSubject = LocationSubject.USER
    latitude: float | None = None
    longitude: float | None = None
    source_id: str = "config.environment"

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("configured location label is required")
        if not isinstance(self.timezone, str) or not self.timezone.strip():
            raise ValueError("configured location timezone is required")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f"unknown environment timezone: {self.timezone}"
            ) from exc
        if not isinstance(self.subject, LocationSubject):
            raise TypeError(
                "configured location subject must be LocationSubject"
            )
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(
                "configured latitude/longitude must be supplied together"
            )
        if self.latitude is not None:
            if isinstance(self.latitude, bool) or isinstance(self.longitude, bool):
                raise TypeError("configured coordinates must be numeric")
            lat = float(self.latitude)
            lon = float(self.longitude)
            if not -90.0 <= lat <= 90.0:
                raise ValueError(
                    "configured latitude must be between -90 and 90"
                )
            if not -180.0 <= lon <= 180.0:
                raise ValueError(
                    "configured longitude must be between -180 and 180"
                )
            object.__setattr__(self, "latitude", lat)
            object.__setattr__(self, "longitude", lon)
        if (
            not isinstance(self.source_id, str)
            or not self.source_id.strip()
            or len(self.source_id) > 128
        ):
            raise ValueError("configured location source_id is invalid")


@dataclass(frozen=True, slots=True)
class EnvironmentConfiguration:
    location: ConfiguredLocation | None = None
    refresh_seconds: int = 300
    weather_max_age_seconds: int = 1800
    indoor_max_age_seconds: int = 900
    current_location_max_age_seconds: int = 900
    home_assistant_weather_entity: str | None = None
    home_assistant_indoor_temperature_entity: str | None = None
    home_assistant_indoor_humidity_entity: str | None = None
    home_assistant_current_location_entity: str | None = None

    def __post_init__(self) -> None:
        if (
            self.location is not None
            and not isinstance(self.location, ConfiguredLocation)
        ):
            raise TypeError(
                "environment location must be ConfiguredLocation or None"
            )
        for name in (
            "refresh_seconds",
            "weather_max_age_seconds",
            "indoor_max_age_seconds",
            "current_location_max_age_seconds",
        ):
            value = getattr(self, name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer")
        for name in (
            "home_assistant_weather_entity",
            "home_assistant_indoor_temperature_entity",
            "home_assistant_indoor_humidity_entity",
            "home_assistant_current_location_entity",
        ):
            value = getattr(self, name)
            if value is not None:
                if (
                    not isinstance(value, str)
                    or not value.strip()
                    or len(value) > 160
                ):
                    raise ValueError(f"invalid {name}")
                object.__setattr__(self, name, value.strip())

    @property
    def home_assistant_enabled(self) -> bool:
        return any(
            (
                self.home_assistant_weather_entity,
                self.home_assistant_indoor_temperature_entity,
                self.home_assistant_indoor_humidity_entity,
                self.home_assistant_current_location_entity,
            )
        )


def _positive_int(
    env: Mapping[str, str],
    name: str,
    default: int,
) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def environment_configuration_from_environ(
    env: Mapping[str, str],
) -> EnvironmentConfiguration:
    label = env.get("SOFIA_ENVIRONMENT_LOCATION_LABEL", "").strip()
    timezone = env.get("SOFIA_ENVIRONMENT_TIMEZONE", "").strip()
    lat_raw = env.get("SOFIA_ENVIRONMENT_LATITUDE", "").strip()
    lon_raw = env.get("SOFIA_ENVIRONMENT_LONGITUDE", "").strip()
    subject_raw = env.get(
        "SOFIA_ENVIRONMENT_LOCATION_SUBJECT",
        "user",
    ).strip().lower()

    location = None
    supplied_location = any((label, timezone, lat_raw, lon_raw))

    if supplied_location:
        if not label or not timezone:
            raise ValueError(
                "SOFIA_ENVIRONMENT_LOCATION_LABEL and "
                "SOFIA_ENVIRONMENT_TIMEZONE are required when "
                "configuring environment location"
            )
        if bool(lat_raw) != bool(lon_raw):
            raise ValueError(
                "SOFIA_ENVIRONMENT_LATITUDE and "
                "SOFIA_ENVIRONMENT_LONGITUDE must be supplied together"
            )
        try:
            subject = LocationSubject(subject_raw)
        except ValueError as exc:
            raise ValueError(
                "SOFIA_ENVIRONMENT_LOCATION_SUBJECT must be "
                "user, site, or host"
            ) from exc

        location = ConfiguredLocation(
            label=label,
            timezone=timezone,
            subject=subject,
            latitude=float(lat_raw) if lat_raw else None,
            longitude=float(lon_raw) if lon_raw else None,
        )

    def optional(name: str) -> str | None:
        value = env.get(name, "").strip()
        return value or None

    return EnvironmentConfiguration(
        location=location,
        refresh_seconds=_positive_int(
            env,
            "SOFIA_ENVIRONMENT_REFRESH_SECONDS",
            300,
        ),
        weather_max_age_seconds=_positive_int(
            env,
            "SOFIA_ENVIRONMENT_WEATHER_MAX_AGE_SECONDS",
            1800,
        ),
        indoor_max_age_seconds=_positive_int(
            env,
            "SOFIA_ENVIRONMENT_INDOOR_MAX_AGE_SECONDS",
            900,
        ),
        current_location_max_age_seconds=_positive_int(
            env,
            "SOFIA_ENVIRONMENT_CURRENT_LOCATION_MAX_AGE_SECONDS",
            900,
        ),
        home_assistant_weather_entity=optional(
            "SOFIA_ENVIRONMENT_HA_WEATHER_ENTITY"
        ),
        home_assistant_indoor_temperature_entity=optional(
            "SOFIA_ENVIRONMENT_HA_INDOOR_TEMPERATURE_ENTITY"
        ),
        home_assistant_indoor_humidity_entity=optional(
            "SOFIA_ENVIRONMENT_HA_INDOOR_HUMIDITY_ENTITY"
        ),
        home_assistant_current_location_entity=optional(
            "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_ENTITY"
        ),
    )
