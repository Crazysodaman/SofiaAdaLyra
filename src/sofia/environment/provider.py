"""Provider-neutral observation contracts for PKG-ENVIRONMENT."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from .model import (
    IndoorEnvironmentObservation,
    LocationEvidenceKind,
    LocationObservation,
    WeatherObservation,
    MobileDeviceObservation,
)


@dataclass(frozen=True, slots=True)
class EnvironmentProviderObservation:
    weather: WeatherObservation | None = None
    indoor: IndoorEnvironmentObservation | None = None
    current_location: LocationObservation | None = None
    mobile: MobileDeviceObservation | None = None

    def __post_init__(self) -> None:
        if self.weather is not None and not isinstance(
            self.weather,
            WeatherObservation,
        ):
            raise TypeError("weather must be WeatherObservation or None")
        if self.indoor is not None and not isinstance(
            self.indoor,
            IndoorEnvironmentObservation,
        ):
            raise TypeError(
                "indoor must be IndoorEnvironmentObservation or None"
            )
        if self.current_location is not None and not isinstance(
            self.current_location,
            LocationObservation,
        ):
            raise TypeError(
                "current_location must be LocationObservation or None"
            )
        if (
            self.current_location is not None
            and self.current_location.kind
            is not LocationEvidenceKind.CURRENT
        ):
            raise ValueError(
                "provider current_location must be current evidence"
            )
        if self.mobile is not None and not isinstance(
            self.mobile, MobileDeviceObservation
        ):
            raise TypeError("mobile must be MobileDeviceObservation or None")


@runtime_checkable
class EnvironmentProvider(Protocol):
    @property
    def name(self) -> str:
        ...

    def observe(
        self,
        *,
        now: datetime,
    ) -> EnvironmentProviderObservation:
        ...


def source_timestamp(value: object) -> datetime | None:
    """Return only source-backed timestamps; never manufacture freshness."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def source_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result
