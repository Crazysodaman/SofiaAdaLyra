"""National Weather Service provider for PKG-ENVIRONMENT.

This provider is intentionally narrow: it may contact only api.weather.gov
over HTTPS, and it normalizes NWS point/forecast/station observations into the
shared EnvironmentProviderObservation contract. It does not grant arbitrary
web access or geolocation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from sofia.integrations.http import ServiceHTTPError

from .config import EnvironmentConfiguration
from .model import (
    EnvironmentFreshness,
    ForecastPeriod,
    WeatherObservation,
)
from .provider import EnvironmentProviderObservation


NWS_API_BASE = "https://api.weather.gov"
NWS_API_HOST = "api.weather.gov"


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


def _validated_nws_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("NWS URL/path must be nonempty")
    url = urljoin(NWS_API_BASE + "/", value.strip())
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != NWS_API_HOST
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise ValueError(
            "NWS provider may contact only https://api.weather.gov"
        )
    return url


class _NwsRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        _validated_nws_url(newurl)
        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            newurl,
        )


class NwsApiClient:
    """Small HTTPS client pinned to api.weather.gov."""

    def __init__(
        self,
        user_agent: str,
        *,
        timeout: float = 10.0,
    ) -> None:
        if (
            not isinstance(user_agent, str)
            or not user_agent.strip()
        ):
            raise ValueError("NWS User-Agent is required")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise ValueError("NWS timeout must be positive")
        self.user_agent = user_agent.strip()
        self.timeout = float(timeout)
        self._opener = build_opener(_NwsRedirectHandler())

    def get(self, path_or_url: str) -> dict[str, Any]:
        url = _validated_nws_url(path_or_url)
        request = Request(
            url,
            headers={
                "Accept": "application/geo+json",
                "User-Agent": self.user_agent,
            },
            method="GET",
        )
        try:
            with self._opener.open(
                request,
                timeout=self.timeout,
            ) as response:
                raw = response.read()
        except HTTPError as exc:
            body = exc.read().decode(
                "utf-8",
                errors="replace",
            )
            raise ServiceHTTPError(
                f"NWS HTTP {exc.code}: {body[:500]}"
            ) from exc
        except URLError as exc:
            raise ServiceHTTPError(
                f"NWS request failed: {exc.reason}"
            ) from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ServiceHTTPError(
                "NWS returned non-JSON data"
            ) from exc
        if not isinstance(data, dict):
            raise ServiceHTTPError(
                "NWS returned an invalid JSON document"
            )
        return data


class NwsEnvironmentProvider:
    """Read current NWS station weather plus bounded point forecast."""

    name = "nws"

    def __init__(
        self,
        configuration: EnvironmentConfiguration,
        client: NwsApiClient | None = None,
    ) -> None:
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
        self._configuration = configuration
        self._location = location
        self._client = (
            client
            if client is not None
            else NwsApiClient(configuration.nws_user_agent)
        )

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
            high_c = (
                temperature
                if is_daytime is True
                else None
            )
            low_c = (
                temperature
                if is_daytime is False
                else None
            )
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

    @staticmethod
    def _station_urls(
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
                        _validated_nws_url(candidate)
                    )
                except ValueError:
                    continue
                continue
            props = feature.get("properties")
            if not isinstance(props, dict):
                continue
            station_id = props.get("stationIdentifier")
            if isinstance(station_id, str) and station_id.strip():
                urls.append(
                    _validated_nws_url(
                        "/stations/"
                        + station_id.strip()
                    )
                )
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

        point = self._client.get(
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
                    self._client.get(forecast_url)
                )
            except ServiceHTTPError:
                forecast = ()

        stations_url = point_properties.get(
            "observationStations"
        )
        if not isinstance(stations_url, str) or not stations_url.strip():
            return EnvironmentProviderObservation()

        stations = self._client.get(stations_url)
        candidates: list[WeatherObservation] = []
        last_station_error: ServiceHTTPError | None = None
        station_urls = self._station_urls(stations)
        for station_url in station_urls:
            latest_url = (
                station_url.rstrip("/")
                + "/observations/latest"
            )
            try:
                observation = self._client.get(latest_url)
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
