"""National Weather Service normalization for PKG-ENVIRONMENT.

Network transport belongs to INTEGRATE. This provider consumes the narrow
NwsAdapter and converts NWS point/forecast/station data into the shared
EnvironmentProviderObservation contract.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sofia.integrations.http import ServiceHTTPError
from sofia.integrations.nws import NwsAdapter

from .config import EnvironmentConfiguration
from .model import (
    EnvironmentFreshness,
    ForecastPeriod,
    WeatherObservation,
)
from .provider import EnvironmentProviderObservation


def _aware_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _temperature_c(value: object, unit: object) -> float | None:
    number = _number(value)
    if number is None:
        return None
    normalized = str(unit or "").strip().lower()
    if normalized in {"f", "degf", "wmounit:degf", "°f"}:
        return (number - 32.0) * 5.0 / 9.0
    if normalized in {"k", "kelvin", "wmounit:k"}:
        return number - 273.15
    return number


def _quantitative_value(
    raw: object,
) -> tuple[float | None, str | None]:
    if not isinstance(raw, dict):
        return None, None
    value = _number(raw.get("value"))
    unit = raw.get("unitCode")
    unit_text = str(unit).strip() if unit is not None else None
    return value, unit_text


def _temperature_qv(raw: object) -> float | None:
    value, unit = _quantitative_value(raw)
    return _temperature_c(value, unit)


def _wind_kph(raw: object) -> float | None:
    value, unit = _quantitative_value(raw)
    if value is None:
        return None
    normalized = str(unit or "").strip().lower()
    if normalized in {"wmounit:m_s-1", "m/s", "mps"}:
        return value * 3.6
    if normalized in {"wmounit:kt", "kt", "kn", "knot", "knots"}:
        return value * 1.852
    if normalized in {"wmounit:mi_h-1", "mph", "mi/h"}:
        return value * 1.609344
    return value


def _precipitation_mm(raw: object) -> float | None:
    value, unit = _quantitative_value(raw)
    if value is None:
        return None
    normalized = str(unit or "").strip().lower()
    if normalized in {"wmounit:m", "m", "meter", "metre"}:
        return value * 1000.0
    if normalized in {"wmounit:cm", "cm"}:
        return value * 10.0
    return value


class NwsEnvironmentProvider:
    """Read current NWS station weather plus bounded point forecast."""

    name = "nws"

    def __init__(
        self,
        adapter: NwsAdapter,
        configuration: EnvironmentConfiguration,
    ) -> None:
        if not isinstance(adapter, NwsAdapter):
            raise TypeError("adapter must be NwsAdapter")
        if not isinstance(
            configuration,
            EnvironmentConfiguration,
        ):
            raise TypeError(
                "configuration must be EnvironmentConfiguration"
            )
        if not configuration.nws_enabled:
            raise ValueError(
                "NWS environment provider is not enabled"
            )
        location = configuration.configured_location_for(
            configuration.nws_location_subject
        )
        if (
            location is None
            or location.latitude is None
            or location.longitude is None
        ):
            raise ValueError(
                "NWS requires configured coordinates for its selected "
                "location subject"
            )
        self._adapter = adapter
        self._configuration = configuration
        self._location = location

    @staticmethod
    def _properties(document: object) -> dict[str, Any]:
        if not isinstance(document, dict):
            return {}
        properties = document.get("properties")
        return properties if isinstance(properties, dict) else {}

    @staticmethod
    def _forecast_periods(
        document: object,
    ) -> tuple[ForecastPeriod, ...]:
        properties = NwsEnvironmentProvider._properties(document)
        rows = properties.get("periods")
        if not isinstance(rows, list):
            return ()

        result: list[ForecastPeriod] = []
        for row in rows[:16]:
            if not isinstance(row, dict):
                continue
            starts = _aware_timestamp(row.get("startTime"))
            if starts is None:
                continue
            ends = _aware_timestamp(row.get("endTime"))
            condition = str(
                row.get("shortForecast")
                or row.get("name")
                or "unknown"
            ).strip()
            if not condition:
                condition = "unknown"
            temperature = _temperature_c(
                row.get("temperature"),
                row.get("temperatureUnit"),
            )
            is_daytime = row.get("isDaytime")
            high_c = temperature if is_daytime is True else None
            low_c = temperature if is_daytime is False else None
            probability = None
            raw_probability = row.get(
                "probabilityOfPrecipitation"
            )
            if isinstance(raw_probability, dict):
                probability = _number(
                    raw_probability.get("value")
                )
            try:
                result.append(
                    ForecastPeriod(
                        starts_at=starts,
                        ends_at=ends,
                        condition=condition,
                        high_c=high_c,
                        low_c=low_c,
                        precipitation_probability=probability,
                    )
                )
            except (TypeError, ValueError):
                continue
        return tuple(result)

    def _station_urls(
        self,
        document: object,
    ) -> tuple[str, ...]:
        if not isinstance(document, dict):
            return ()
        features = document.get("features")
        if not isinstance(features, list):
            return ()
        urls: list[str] = []
        for feature in features[:5]:
            if not isinstance(feature, dict):
                continue
            candidate = feature.get("id") or feature.get("@id")
            if isinstance(candidate, str) and candidate.strip():
                try:
                    urls.append(
                        self._adapter.normalize_url(candidate)
                    )
                except ValueError:
                    continue
                continue
            props = feature.get("properties")
            if not isinstance(props, dict):
                continue
            station_id = props.get("stationIdentifier")
            if isinstance(station_id, str) and station_id.strip():
                try:
                    urls.append(
                        self._adapter.normalize_url(
                            "/stations/"
                            + station_id.strip()
                        )
                    )
                except ValueError:
                    continue
        return tuple(dict.fromkeys(urls))

    def _weather_from_observation(
        self,
        document: object,
        *,
        station_url: str,
        forecast: tuple[ForecastPeriod, ...],
    ) -> WeatherObservation | None:
        properties = self._properties(document)
        observed = _aware_timestamp(
            properties.get("timestamp")
        )
        if observed is None:
            return None

        condition = str(
            properties.get("textDescription")
            or "unknown"
        ).strip()
        if not condition:
            condition = "unknown"

        feels_like = _temperature_qv(
            properties.get("heatIndex")
        )
        if feels_like is None:
            feels_like = _temperature_qv(
                properties.get("windChill")
            )

        humidity, _ = _quantitative_value(
            properties.get("relativeHumidity")
        )
        station_id = station_url.rstrip("/").split("/")[-1]

        try:
            return WeatherObservation(
                condition=condition,
                observed_at=observed,
                expires_at=observed
                + timedelta(
                    seconds=self._configuration.weather_max_age_seconds
                ),
                source_id=f"nws:{station_id}",
                location_label=self._location.label,
                temperature_c=_temperature_qv(
                    properties.get("temperature")
                ),
                feels_like_c=feels_like,
                humidity_percent=humidity,
                wind_kph=_wind_kph(
                    properties.get("windSpeed")
                ),
                precipitation_mm=_precipitation_mm(
                    properties.get("precipitationLastHour")
                ),
                forecast=forecast,
            )
        except (TypeError, ValueError):
            return None

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

        point = self._adapter.get(
            "/points/"
            f"{self._location.latitude:.4f},"
            f"{self._location.longitude:.4f}"
        )
        point_properties = self._properties(point)

        forecast: tuple[ForecastPeriod, ...] = ()
        forecast_url = point_properties.get("forecast")
        if isinstance(forecast_url, str) and forecast_url.strip():
            try:
                forecast = self._forecast_periods(
                    self._adapter.get(forecast_url)
                )
            except ServiceHTTPError:
                forecast = ()

        stations_url = point_properties.get(
            "observationStations"
        )
        if not isinstance(stations_url, str) or not stations_url.strip():
            return EnvironmentProviderObservation()

        stations = self._adapter.get(stations_url)
        candidates: list[WeatherObservation] = []
        last_station_error: ServiceHTTPError | None = None
        station_urls = self._station_urls(stations)
        for station_url in station_urls:
            latest_url = (
                station_url.rstrip("/")
                + "/observations/latest"
            )
            try:
                observation = self._adapter.get(latest_url)
            except ServiceHTTPError as exc:
                last_station_error = exc
                continue
            weather = self._weather_from_observation(
                observation,
                station_url=station_url,
                forecast=forecast,
            )
            if weather is not None:
                candidates.append(weather)

        if not candidates:
            if station_urls and last_station_error is not None:
                raise last_station_error
            return EnvironmentProviderObservation()

        current = tuple(
            weather
            for weather in candidates
            if weather.freshness(now=now)
            is EnvironmentFreshness.CURRENT
        )
        selected = max(
            current or tuple(candidates),
            key=lambda weather: weather.observed_at,
        )
        return EnvironmentProviderObservation(
            weather=selected
        )
