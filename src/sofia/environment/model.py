"""Typed, immutable environmental observations.

ENVIRONMENT owns observational context, not authority. Location coordinates are
kept as internal evidence; provider-facing projections can expose only bounded
labels and provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import math


class LocationSubject(str, Enum):
    USER = "user"
    SITE = "site"
    HOST = "host"


class LocationEvidenceKind(str, Enum):
    CONFIGURED = "configured"
    CURRENT = "current"


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class DaylightState(str, Enum):
    DAY = "day"
    NIGHT = "night"
    POLAR_DAY = "polar_day"
    POLAR_NIGHT = "polar_night"
    UNKNOWN = "unknown"


class EnvironmentFreshness(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    FUTURE = "future"
    UNKNOWN = "unknown"


def _aware(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


def _text(value: str, label: str, *, limit: int = 160) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"invalid {label}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"invalid {label}")
    return value.strip()


def _finite(value: float | int | None, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be numeric or None")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


@dataclass(frozen=True, slots=True)
class LocationObservation:
    label: str
    source_id: str
    subject: LocationSubject
    kind: LocationEvidenceKind
    timezone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    precision_meters: float | None = None
    observed_at: datetime | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _text(self.label, "location label"))
        object.__setattr__(self, "source_id", _text(self.source_id, "location source", limit=128))
        if not isinstance(self.subject, LocationSubject):
            raise TypeError("location subject must be LocationSubject")
        if not isinstance(self.kind, LocationEvidenceKind):
            raise TypeError("location kind must be LocationEvidenceKind")
        if self.timezone is not None:
            object.__setattr__(self, "timezone", _text(self.timezone, "location timezone", limit=80))
        lat = _finite(self.latitude, "latitude")
        lon = _finite(self.longitude, "longitude")
        if (lat is None) != (lon is None):
            raise ValueError("latitude and longitude must be supplied together")
        if lat is not None and not -90.0 <= lat <= 90.0:
            raise ValueError("latitude must be between -90 and 90")
        if lon is not None and not -180.0 <= lon <= 180.0:
            raise ValueError("longitude must be between -180 and 180")
        if lat is not None:
            object.__setattr__(self, "latitude", lat)
            object.__setattr__(self, "longitude", lon)
        precision = _finite(self.precision_meters, "precision_meters")
        if precision is not None:
            if not 0.0 <= precision <= 40_100_000.0:
                raise ValueError(
                    "precision_meters outside supported bounds"
                )
            if lat is None:
                raise ValueError(
                    "precision_meters requires coordinates"
                )
            object.__setattr__(
                self,
                "precision_meters",
                precision,
            )
        if self.observed_at is not None:
            _aware(self.observed_at, "location observed_at")
        if self.expires_at is not None:
            _aware(self.expires_at, "location expires_at")
        if self.kind is LocationEvidenceKind.CURRENT:
            if self.observed_at is None or self.expires_at is None:
                raise ValueError(
                    "current location evidence requires observed_at and expires_at"
                )
            if self.expires_at < self.observed_at:
                raise ValueError(
                    "location expires_at precedes observed_at"
                )
        elif self.expires_at is not None:
            raise ValueError(
                "configured location evidence must not have expires_at"
            )

    def freshness(
        self,
        *,
        now: datetime,
    ) -> EnvironmentFreshness:
        _aware(now, "location freshness time")
        if self.kind is LocationEvidenceKind.CONFIGURED:
            return EnvironmentFreshness.UNKNOWN
        assert self.observed_at is not None
        assert self.expires_at is not None
        if self.observed_at > now + timedelta(minutes=5):
            return EnvironmentFreshness.FUTURE
        if now <= self.expires_at:
            return EnvironmentFreshness.CURRENT
        return EnvironmentFreshness.STALE


@dataclass(frozen=True, slots=True)
class ForecastPeriod:
    starts_at: datetime
    condition: str
    ends_at: datetime | None = None
    high_c: float | None = None
    low_c: float | None = None
    precipitation_probability: float | None = None

    def __post_init__(self) -> None:
        _aware(self.starts_at, "forecast starts_at")
        object.__setattr__(self, "condition", _text(self.condition, "forecast condition", limit=80))
        if self.ends_at is not None:
            _aware(self.ends_at, "forecast ends_at")
            if self.ends_at < self.starts_at:
                raise ValueError("forecast ends_at precedes starts_at")
        for name in ("high_c", "low_c"):
            value = _finite(getattr(self, name), name)
            if value is not None:
                if not -120.0 <= value <= 80.0:
                    raise ValueError(f"{name} outside supported Celsius bounds")
                object.__setattr__(self, name, value)
        probability = _finite(
            self.precipitation_probability,
            "precipitation_probability",
        )
        if probability is not None:
            if not 0.0 <= probability <= 100.0:
                raise ValueError("precipitation_probability must be 0..100")
            object.__setattr__(self, "precipitation_probability", probability)


@dataclass(frozen=True, slots=True)
class WeatherObservation:
    condition: str
    observed_at: datetime
    expires_at: datetime
    source_id: str
    location_label: str | None = None
    temperature_c: float | None = None
    feels_like_c: float | None = None
    humidity_percent: float | None = None
    wind_kph: float | None = None
    precipitation_mm: float | None = None
    forecast: tuple[ForecastPeriod, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition", _text(self.condition, "weather condition", limit=80))
        _aware(self.observed_at, "weather observed_at")
        _aware(self.expires_at, "weather expires_at")
        if self.expires_at < self.observed_at:
            raise ValueError("weather expires_at precedes observed_at")
        object.__setattr__(self, "source_id", _text(self.source_id, "weather source", limit=128))
        if self.location_label is not None:
            object.__setattr__(
                self,
                "location_label",
                _text(self.location_label, "weather location", limit=120),
            )
        bounds = {
            "temperature_c": (-120.0, 80.0),
            "feels_like_c": (-120.0, 80.0),
            "humidity_percent": (0.0, 100.0),
            "wind_kph": (0.0, 600.0),
            "precipitation_mm": (0.0, 5000.0),
        }
        for name, (minimum, maximum) in bounds.items():
            value = _finite(getattr(self, name), name)
            if value is not None:
                if not minimum <= value <= maximum:
                    raise ValueError(f"{name} outside supported bounds")
                object.__setattr__(self, name, value)
        if not isinstance(self.forecast, tuple):
            raise TypeError("forecast must be a tuple")
        if len(self.forecast) > 16:
            raise ValueError("forecast is bounded to 16 periods")
        if any(not isinstance(item, ForecastPeriod) for item in self.forecast):
            raise TypeError("forecast must contain ForecastPeriod values")

    def freshness(
        self,
        *,
        now: datetime,
        future_tolerance: timedelta = timedelta(minutes=5),
    ) -> EnvironmentFreshness:
        _aware(now, "weather freshness time")
        if self.observed_at > now + future_tolerance:
            return EnvironmentFreshness.FUTURE
        if now <= self.expires_at:
            return EnvironmentFreshness.CURRENT
        return EnvironmentFreshness.STALE


@dataclass(frozen=True, slots=True)
class IndoorEnvironmentObservation:
    observed_at: datetime
    expires_at: datetime
    source_id: str
    temperature_c: float | None = None
    humidity_percent: float | None = None

    def __post_init__(self) -> None:
        _aware(self.observed_at, "indoor observed_at")
        _aware(self.expires_at, "indoor expires_at")
        if self.expires_at < self.observed_at:
            raise ValueError("indoor expires_at precedes observed_at")
        object.__setattr__(self, "source_id", _text(self.source_id, "indoor source", limit=128))
        temp = _finite(self.temperature_c, "indoor temperature_c")
        humidity = _finite(self.humidity_percent, "indoor humidity_percent")
        if temp is not None:
            if not -80.0 <= temp <= 80.0:
                raise ValueError("indoor temperature outside supported bounds")
            object.__setattr__(self, "temperature_c", temp)
        if humidity is not None:
            if not 0.0 <= humidity <= 100.0:
                raise ValueError("indoor humidity must be 0..100")
            object.__setattr__(self, "humidity_percent", humidity)

    def freshness(self, *, now: datetime) -> EnvironmentFreshness:
        _aware(now, "indoor freshness time")
        if self.observed_at > now + timedelta(minutes=5):
            return EnvironmentFreshness.FUTURE
        if now <= self.expires_at:
            return EnvironmentFreshness.CURRENT
        return EnvironmentFreshness.STALE


@dataclass(frozen=True, slots=True)
class DaylightObservation:
    state: DaylightState
    sunrise: datetime | None = None
    sunset: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, DaylightState):
            raise TypeError("daylight state must be DaylightState")
        for name in ("sunrise", "sunset"):
            value = getattr(self, name)
            if value is not None:
                _aware(value, name)


@dataclass(frozen=True, slots=True)
class EnvironmentSnapshot:
    observed_at: datetime
    utc_time: datetime
    host_local_time: datetime
    host_timezone_label: str
    user_local_time: datetime | None = None
    timezone: str | None = None
    configured_location: LocationObservation | None = None
    current_location: LocationObservation | None = None
    current_location_freshness: EnvironmentFreshness = (
        EnvironmentFreshness.UNKNOWN
    )
    season: Season | None = None
    daylight: DaylightObservation | None = None
    weather: WeatherObservation | None = None
    weather_freshness: EnvironmentFreshness = EnvironmentFreshness.UNKNOWN
    indoor: IndoorEnvironmentObservation | None = None
    indoor_freshness: EnvironmentFreshness = EnvironmentFreshness.UNKNOWN
    provider_errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("observed_at", "utc_time", "host_local_time"):
            _aware(getattr(self, name), name)
        object.__setattr__(
            self,
            "host_timezone_label",
            _text(self.host_timezone_label, "host timezone", limit=80),
        )
        if self.user_local_time is not None:
            _aware(self.user_local_time, "user_local_time")
        if self.timezone is not None:
            object.__setattr__(self, "timezone", _text(self.timezone, "timezone", limit=80))
        for name in ("configured_location", "current_location"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, LocationObservation):
                raise TypeError(f"{name} must be LocationObservation or None")
        if (
            self.configured_location is not None
            and self.configured_location.kind is not LocationEvidenceKind.CONFIGURED
        ):
            raise ValueError("configured_location must be configured evidence")
        if (
            self.current_location is not None
            and self.current_location.kind is not LocationEvidenceKind.CURRENT
        ):
            raise ValueError("current_location must be current evidence")
        if not isinstance(
            self.current_location_freshness,
            EnvironmentFreshness,
        ):
            raise TypeError(
                "current_location_freshness must be EnvironmentFreshness"
            )
        if self.season is not None and not isinstance(self.season, Season):
            raise TypeError("season must be Season or None")
        if self.daylight is not None and not isinstance(self.daylight, DaylightObservation):
            raise TypeError("daylight must be DaylightObservation or None")
        if self.weather is not None and not isinstance(self.weather, WeatherObservation):
            raise TypeError("weather must be WeatherObservation or None")
        if self.indoor is not None and not isinstance(self.indoor, IndoorEnvironmentObservation):
            raise TypeError("indoor must be IndoorEnvironmentObservation or None")
        if not isinstance(self.weather_freshness, EnvironmentFreshness):
            raise TypeError("weather_freshness must be EnvironmentFreshness")
        if not isinstance(self.indoor_freshness, EnvironmentFreshness):
            raise TypeError("indoor_freshness must be EnvironmentFreshness")
        if not isinstance(self.provider_errors, tuple):
            raise TypeError("provider_errors must be a tuple")
        if any(not isinstance(item, str) or not item.strip() for item in self.provider_errors):
            raise ValueError("provider_errors must contain nonempty strings")

    @property
    def effective_location(self) -> LocationObservation | None:
        if (
            self.current_location is not None
            and self.current_location_freshness
            is EnvironmentFreshness.CURRENT
            and (
                self.configured_location is None
                or self.current_location.subject
                is self.configured_location.subject
            )
        ):
            return self.current_location
        return self.configured_location
