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
    host_location: ConfiguredLocation | None = None
    refresh_seconds: int = 300
    weather_max_age_seconds: int = 1800
    indoor_max_age_seconds: int = 900
    current_location_max_age_seconds: int = 900
    home_assistant_weather_entity: str | None = None
    home_assistant_indoor_temperature_entity: str | None = None
    home_assistant_indoor_humidity_entity: str | None = None
    home_assistant_current_location_entity: str | None = None
    home_assistant_current_location_subject: LocationSubject | None = None
    nws_enabled: bool = False
    nws_location_subject: LocationSubject = LocationSubject.USER
    nws_user_agent: str = "SofiaAdaLyra/1.0"

    def __post_init__(self) -> None:
        if (
            self.location is not None
            and not isinstance(self.location, ConfiguredLocation)
        ):
            raise TypeError(
                "environment location must be ConfiguredLocation or None"
            )
        if (
            self.host_location is not None
            and not isinstance(self.host_location, ConfiguredLocation)
        ):
            raise TypeError(
                "environment host_location must be ConfiguredLocation or None"
            )
        if (
            self.host_location is not None
            and self.host_location.subject is not LocationSubject.HOST
        ):
            raise ValueError(
                "environment host_location must have subject=host"
            )
        if (
            self.host_location is not None
            and self.location is not None
            and self.location.subject is LocationSubject.HOST
        ):
            raise ValueError(
                "configure host location once, not in both location and host_location"
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

        if (
            self.home_assistant_current_location_subject is not None
            and not isinstance(
                self.home_assistant_current_location_subject,
                LocationSubject,
            )
        ):
            raise TypeError(
                "home_assistant_current_location_subject must be "
                "LocationSubject or None"
            )
        configured_subjects = {
            candidate.subject
            for candidate in (self.location, self.host_location)
            if candidate is not None
        }
        if (
            self.home_assistant_current_location_entity is not None
            and self.home_assistant_current_location_subject is None
            and len(configured_subjects) != 1
        ):
            raise ValueError(
                "Home Assistant current-location entity requires an "
                "explicit location subject unless exactly one configured "
                "location subject exists"
            )

        if type(self.nws_enabled) is not bool:
            raise TypeError("nws_enabled must be a bool")
        if not isinstance(self.nws_location_subject, LocationSubject):
            raise TypeError(
                "nws_location_subject must be LocationSubject"
            )
        if (
            not isinstance(self.nws_user_agent, str)
            or not self.nws_user_agent.strip()
            or len(self.nws_user_agent) > 200
        ):
            raise ValueError("nws_user_agent must be a nonempty string")
        object.__setattr__(
            self,
            "nws_user_agent",
            self.nws_user_agent.strip(),
        )

    def configured_location_for(
        self,
        subject: LocationSubject,
    ) -> ConfiguredLocation | None:
        if not isinstance(subject, LocationSubject):
            raise TypeError("subject must be LocationSubject")
        for candidate in (self.location, self.host_location):
            if candidate is not None and candidate.subject is subject:
                return candidate
        return None

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


def _boolean(
    env: Mapping[str, str],
    name: str,
    default: bool = False,
) -> bool:
    raw = env.get(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"{name} must be one of true/false, yes/no, on/off, or 1/0"
    )


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

    host_label = env.get(
        "SOFIA_ENVIRONMENT_HOST_LOCATION_LABEL",
        "",
    ).strip()
    host_timezone = env.get(
        "SOFIA_ENVIRONMENT_HOST_TIMEZONE",
        "",
    ).strip()
    host_lat_raw = env.get(
        "SOFIA_ENVIRONMENT_HOST_LATITUDE",
        "",
    ).strip()
    host_lon_raw = env.get(
        "SOFIA_ENVIRONMENT_HOST_LONGITUDE",
        "",
    ).strip()
    host_supplied = any(
        (host_label, host_timezone, host_lat_raw, host_lon_raw)
    )
    host_location = None
    if host_supplied:
        if not host_label or not host_timezone:
            raise ValueError(
                "SOFIA_ENVIRONMENT_HOST_LOCATION_LABEL and "
                "SOFIA_ENVIRONMENT_HOST_TIMEZONE are required when "
                "configuring runtime host location"
            )
        if bool(host_lat_raw) != bool(host_lon_raw):
            raise ValueError(
                "SOFIA_ENVIRONMENT_HOST_LATITUDE and "
                "SOFIA_ENVIRONMENT_HOST_LONGITUDE must be supplied together"
            )
        host_location = ConfiguredLocation(
            label=host_label,
            timezone=host_timezone,
            subject=LocationSubject.HOST,
            latitude=float(host_lat_raw) if host_lat_raw else None,
            longitude=float(host_lon_raw) if host_lon_raw else None,
            source_id="config.environment.host",
        )

    def optional(name: str) -> str | None:
        value = env.get(name, "").strip()
        return value or None

    ha_location_entity = optional(
        "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_ENTITY"
    )
    ha_subject_raw = env.get(
        "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_SUBJECT",
        "",
    ).strip().lower()
    ha_location_subject = None
    if ha_subject_raw:
        try:
            ha_location_subject = LocationSubject(ha_subject_raw)
        except ValueError as exc:
            raise ValueError(
                "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_SUBJECT must be "
                "user, site, or host"
            ) from exc

    nws_enabled = _boolean(
        env,
        "SOFIA_ENVIRONMENT_NWS_ENABLED",
        False,
    )
    nws_subject_raw = env.get(
        "SOFIA_ENVIRONMENT_NWS_LOCATION_SUBJECT",
        "user",
    ).strip().lower()
    try:
        nws_location_subject = LocationSubject(nws_subject_raw)
    except ValueError as exc:
        raise ValueError(
            "SOFIA_ENVIRONMENT_NWS_LOCATION_SUBJECT must be "
            "user, site, or host"
        ) from exc
    nws_user_agent = env.get(
        "SOFIA_ENVIRONMENT_NWS_USER_AGENT",
        "SofiaAdaLyra/1.0",
    ).strip()

    return EnvironmentConfiguration(
        location=location,
        host_location=host_location,
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
        home_assistant_current_location_entity=ha_location_entity,
        home_assistant_current_location_subject=ha_location_subject,
        nws_enabled=nws_enabled,
        nws_location_subject=nws_location_subject,
        nws_user_agent=nws_user_agent,
    )
