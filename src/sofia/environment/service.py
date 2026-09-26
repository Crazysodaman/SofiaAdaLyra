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
            int,
            EnvironmentProviderObservation,
        ] = {}
        self._provider_refreshed_at: dict[int, datetime] = {}
        self._provider_errors: dict[str, str] = {}

    @property
    def providers(self) -> tuple[EnvironmentProvider, ...]:
        return self._providers

    def invalidate(self) -> None:
        self._provider_observations.clear()
        self._provider_refreshed_at.clear()
        self._provider_errors.clear()

    @staticmethod
    def _configured_location(
        configured,
    ) -> LocationObservation | None:
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
        cache_key = id(provider)
        refreshed = self._provider_refreshed_at.get(cache_key)
        if (
            refreshed is not None
            and cache_key in self._provider_observations
            and now
            < refreshed
            + timedelta(
                seconds=self.configuration.refresh_seconds
            )
        ):
            return self._provider_observations[cache_key]

        try:
            observation = provider.observe(now=now)
        except Exception as exc:
            self._provider_errors[name] = type(exc).__name__
            return self._provider_observations.get(cache_key)

        if not isinstance(
            observation,
            EnvironmentProviderObservation,
        ):
            self._provider_errors[name] = "InvalidObservation"
            return self._provider_observations.get(cache_key)

        self._provider_observations[cache_key] = observation
        self._provider_refreshed_at[cache_key] = now
        self._provider_errors.pop(name, None)
        return observation

    @staticmethod
    def _freshness_rank(value: EnvironmentFreshness) -> int:
        return {
            EnvironmentFreshness.CURRENT: 3,
            EnvironmentFreshness.STALE: 2,
            EnvironmentFreshness.FUTURE: 1,
            EnvironmentFreshness.UNKNOWN: 0,
        }[value]

    @classmethod
    def _prefer_observation(
        cls,
        current,
        candidate,
        *,
        now: datetime,
    ):
        """Prefer fresher evidence instead of provider-registration order."""
        if candidate is None:
            return current
        if current is None:
            return candidate

        current_freshness = current.freshness(now=now)
        candidate_freshness = candidate.freshness(now=now)
        current_rank = cls._freshness_rank(current_freshness)
        candidate_rank = cls._freshness_rank(candidate_freshness)

        if candidate_rank != current_rank:
            return candidate if candidate_rank > current_rank else current

        current_observed = getattr(current, "observed_at", None)
        candidate_observed = getattr(candidate, "observed_at", None)
        if (
            isinstance(current_observed, datetime)
            and isinstance(candidate_observed, datetime)
            and candidate_observed > current_observed
        ):
            return candidate
        return current

    def snapshot(
        self,
        *,
        now: datetime | None = None,
        refresh_providers: bool = True,
    ) -> EnvironmentSnapshot:
        if type(refresh_providers) is not bool:
            raise TypeError("refresh_providers must be a bool")

        clock = runtime_clock_snapshot(now=now)
        current_utc = clock.utc

        configured_location = self._configured_location(
            self.configuration.location
        )
        host_location = self._configured_location(
            self.configuration.host_location
        )
        current_location = None
        weather = None
        indoor = None

        observations: list[EnvironmentProviderObservation] = []
        if refresh_providers:
            for provider in self._providers:
                observation = self._observe_provider(
                    provider,
                    now=current_utc,
                )
                if observation is not None:
                    observations.append(observation)
        else:
            observations.extend(
                self._provider_observations.values()
            )

        for observation in observations:
            current_location = self._prefer_observation(
                current_location,
                observation.current_location,
                now=current_utc,
            )
            weather = self._prefer_observation(
                weather,
                observation.weather,
                now=current_utc,
            )
            indoor = self._prefer_observation(
                indoor,
                observation.indoor,
                now=current_utc,
            )

        current_location_freshness = (
            current_location.freshness(now=current_utc)
            if current_location is not None
            else EnvironmentFreshness.UNKNOWN
        )
        current_overrides_configured = (
            current_location is not None
            and current_location_freshness
            is EnvironmentFreshness.CURRENT
            and (
                configured_location is None
                or current_location.subject
                is configured_location.subject
            )
        )
        effective_location = (
            current_location
            if current_overrides_configured
            else configured_location
        )
        if current_overrides_configured:
            # A fresh current observation may replace a configured place only
            # for the same subject. A host/site tracker must never hijack the
            # user's configured timezone/location (or vice versa).
            # If the current observation cannot prove its timezone, do not
            # silently reuse the configured/home timezone.
            assert current_location is not None
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
            host_location=host_location,
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
