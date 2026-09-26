"""Shared environment snapshot assembly and provider freshness."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sofia.runtime.clock import runtime_clock_snapshot

from .astronomy import daylight_for, season_for
from .config import EnvironmentConfiguration
from .model import (
    EnvironmentFreshness,
    EnvironmentSnapshot,
    LocationEvidenceKind,
    LocationObservation,
)
from .provider import (
    EnvironmentProvider,
    EnvironmentProviderObservation,
)


class EnvironmentService:
    """Build one authoritative observation snapshot per cognitive operation."""

    def __init__(
        self,
        configuration: EnvironmentConfiguration | None = None,
        *,
        providers: tuple[EnvironmentProvider, ...] = (),
    ) -> None:
        self.configuration = (
            configuration
            if configuration is not None
            else EnvironmentConfiguration()
        )
        if not isinstance(
            self.configuration,
            EnvironmentConfiguration,
        ):
            raise TypeError(
                "configuration must be EnvironmentConfiguration"
            )
        if not isinstance(providers, tuple):
            raise TypeError("providers must be a tuple")
        for provider in providers:
            name = getattr(provider, "name", None)
            observe = getattr(provider, "observe", None)
            if (
                not isinstance(name, str)
                or not name.strip()
                or not callable(observe)
            ):
                raise TypeError(
                    "providers must expose a nonempty name and "
                    "callable observe(now=...)"
                )
        self._providers = providers
        self._provider_observations: dict[
            str,
            EnvironmentProviderObservation,
        ] = {}
        self._provider_refreshed_at: dict[str, datetime] = {}
        self._provider_errors: dict[str, str] = {}

    @property
    def providers(self) -> tuple[EnvironmentProvider, ...]:
        return self._providers

    def invalidate(self) -> None:
        self._provider_observations.clear()
        self._provider_refreshed_at.clear()
        self._provider_errors.clear()

    def _configured_location(
        self,
    ) -> LocationObservation | None:
        configured = self.configuration.location
        if configured is None:
            return None
        return LocationObservation(
            label=configured.label,
            source_id=configured.source_id,
            subject=configured.subject,
            kind=LocationEvidenceKind.CONFIGURED,
            timezone=configured.timezone,
            latitude=configured.latitude,
            longitude=configured.longitude,
            observed_at=None,
        )

    def _observe_provider(
        self,
        provider: EnvironmentProvider,
        *,
        now: datetime,
    ) -> EnvironmentProviderObservation | None:
        name = provider.name
        refreshed = self._provider_refreshed_at.get(name)
        if (
            refreshed is not None
            and name in self._provider_observations
            and now
            < refreshed
            + timedelta(
                seconds=self.configuration.refresh_seconds
            )
        ):
            return self._provider_observations[name]

        try:
            observation = provider.observe(now=now)
        except Exception as exc:
            self._provider_errors[name] = type(exc).__name__
            return self._provider_observations.get(name)

        if not isinstance(
            observation,
            EnvironmentProviderObservation,
        ):
            self._provider_errors[name] = "InvalidObservation"
            return self._provider_observations.get(name)

        self._provider_observations[name] = observation
        self._provider_refreshed_at[name] = now
        self._provider_errors.pop(name, None)
        return observation

    def snapshot(
        self,
        *,
        now: datetime | None = None,
    ) -> EnvironmentSnapshot:
        clock = runtime_clock_snapshot(now=now)
        current_utc = clock.utc

        configured_location = self._configured_location()
        current_location = None
        weather = None
        indoor = None

        for provider in self._providers:
            observation = self._observe_provider(
                provider,
                now=current_utc,
            )
            if observation is None:
                continue
            if (
                current_location is None
                and observation.current_location is not None
            ):
                current_location = observation.current_location
            if weather is None and observation.weather is not None:
                weather = observation.weather
            if indoor is None and observation.indoor is not None:
                indoor = observation.indoor

        current_location_freshness = (
            current_location.freshness(now=current_utc)
            if current_location is not None
            else EnvironmentFreshness.UNKNOWN
        )
        effective_location = (
            current_location
            if (
                current_location is not None
                and current_location_freshness
                is EnvironmentFreshness.CURRENT
            )
            else configured_location
        )
        if (
            current_location is not None
            and current_location_freshness
            is EnvironmentFreshness.CURRENT
        ):
            # A fresh mobile/current location outranks the configured place.
            # If the provider cannot prove that current location's timezone,
            # do not silently reuse the configured/home timezone.
            timezone_name = current_location.timezone
        else:
            timezone_name = (
                configured_location.timezone
                if configured_location is not None
                else None
            )

        self._provider_errors.pop("timezone", None)
        user_local_time = None
        if timezone_name is not None:
            try:
                zone = ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError:
                self._provider_errors["timezone"] = (
                    "ZoneInfoNotFoundError"
                )
                timezone_name = None
            else:
                user_local_time = current_utc.astimezone(zone)

        season = None
        daylight = None
        if (
            effective_location is not None
            and effective_location.latitude is not None
            and effective_location.longitude is not None
            and timezone_name is not None
        ):
            local_for_calendar = (
                user_local_time
                if user_local_time is not None
                else current_utc
            )
            season = season_for(
                day=local_for_calendar.date(),
                latitude=effective_location.latitude,
            )
            daylight = daylight_for(
                now=current_utc,
                latitude=effective_location.latitude,
                longitude=effective_location.longitude,
                timezone_name=timezone_name,
            )

        weather_freshness = (
            weather.freshness(now=current_utc)
            if weather is not None
            else EnvironmentFreshness.UNKNOWN
        )
        indoor_freshness = (
            indoor.freshness(now=current_utc)
            if indoor is not None
            else EnvironmentFreshness.UNKNOWN
        )

        return EnvironmentSnapshot(
            observed_at=current_utc,
            utc_time=current_utc,
            host_local_time=clock.host_local,
            host_timezone_label=clock.host_timezone_label,
            user_local_time=user_local_time,
            timezone=timezone_name,
            configured_location=configured_location,
            current_location=current_location,
            current_location_freshness=current_location_freshness,
            season=season,
            daylight=daylight,
            weather=weather,
            weather_freshness=weather_freshness,
            indoor=indoor,
            indoor_freshness=indoor_freshness,
            provider_errors=tuple(
                f"{name}:{self._provider_errors[name]}"
                for name in sorted(self._provider_errors)
            ),
        )
