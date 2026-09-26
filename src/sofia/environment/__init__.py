"""PKG-ENVIRONMENT public surface without eager runtime imports.

Configuration imports this package while SofiaConfiguration itself is being
defined, so runtime-dependent services are resolved lazily to avoid a
config -> environment -> runtime -> config import cycle.
"""
from __future__ import annotations

from .config import (
    ConfiguredLocation,
    EnvironmentConfiguration,
    environment_configuration_from_environ,
)
from .model import (
    DaylightObservation,
    DaylightState,
    EnvironmentFreshness,
    EnvironmentSnapshot,
    ForecastPeriod,
    IndoorEnvironmentObservation,
    LocationEvidenceKind,
    LocationObservation,
    LocationSubject,
    Season,
    WeatherObservation,
)
from .query import EnvironmentQueryAnswer, EnvironmentQueryResolver

__all__ = [
    "ConfiguredLocation",
    "DaylightObservation",
    "DaylightState",
    "EnvironmentConfiguration",
    "EnvironmentFreshness",
    "EnvironmentQueryAnswer",
    "EnvironmentQueryResolver",
    "EnvironmentService",
    "EnvironmentSnapshot",
    "ForecastPeriod",
    "IndoorEnvironmentObservation",
    "LocationEvidenceKind",
    "LocationObservation",
    "LocationSubject",
    "NwsEnvironmentProvider",
    "Season",
    "WeatherObservation",
    "environment_configuration_from_environ",
]


def __getattr__(name: str):
    if name == "EnvironmentService":
        from .service import EnvironmentService

        globals()[name] = EnvironmentService
        return EnvironmentService
    if name == "NwsEnvironmentProvider":
        from .nws import NwsEnvironmentProvider

        globals()[name] = NwsEnvironmentProvider
        return NwsEnvironmentProvider
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )
