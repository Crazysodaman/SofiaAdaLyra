"""Provider-neutral observation contracts for PKG-ENVIRONMENT."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from .model import (
    IndoorEnvironmentObservation,
    LocationObservation,
    WeatherObservation,
)


@dataclass(frozen=True, slots=True)
class EnvironmentProviderObservation:
    weather: WeatherObservation | None = None
    indoor: IndoorEnvironmentObservation | None = None
    current_location: LocationObservation | None = None

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
