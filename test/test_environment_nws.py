from datetime import datetime, timedelta, timezone

import pytest

from sofia.environment.config import ConfiguredLocation, EnvironmentConfiguration
from sofia.environment.model import LocationSubject
from sofia.environment.nws import (
    NwsEnvironmentProvider,
    _validated_nws_url,
)


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


class FakeNwsClient:
    def __init__(self, documents):
        self.documents = documents
        self.requests = []

    def get(self, path_or_url):
        self.requests.append(path_or_url)
        return self.documents[path_or_url]


def configuration(*, subject=LocationSubject.USER):
    primary = ConfiguredLocation(
        label="Home",
        timezone="America/Chicago",
        subject=LocationSubject.USER,
        latitude=32.5,
        longitude=-97.1,
    )
    host = ConfiguredLocation(
        label="Artemis",
        timezone="America/Chicago",
        subject=LocationSubject.HOST,
        latitude=32.6,
        longitude=-97.2,
        source_id="config.environment.host",
    )
    return EnvironmentConfiguration(
        location=primary,
        host_location=host,
        nws_enabled=True,
        nws_location_subject=subject,
        nws_user_agent="SofiaAdaLyra-test",
    )


def test_nws_url_is_pinned_to_official_api_host():
    assert (
        _validated_nws_url("/points/32.5,-97.1")
        == "https://api.weather.gov/points/32.5,-97.1"
    )
    with pytest.raises(ValueError, match="only https://api.weather.gov"):
        _validated_nws_url("https://example.com/weather")
    with pytest.raises(ValueError, match="only https://api.weather.gov"):
        _validated_nws_url("http://api.weather.gov/points/32.5,-97.1")


def test_nws_provider_normalizes_station_weather_and_forecast():
    client = FakeNwsClient(
        {
            "/points/32.5000,-97.1000": {
                "properties": {
                    "forecast": "https://api.weather.gov/gridpoints/FWD/1,2/forecast",
                    "observationStations": (
                        "https://api.weather.gov/gridpoints/FWD/1,2/stations"
                    ),
                }
            },
            "https://api.weather.gov/gridpoints/FWD/1,2/forecast": {
                "properties": {
                    "periods": [
                        {
                            "startTime": "2026-09-26T07:00:00-05:00",
                            "endTime": "2026-09-26T19:00:00-05:00",
                            "isDaytime": True,
                            "temperature": 86,
                            "temperatureUnit": "F",
                            "shortForecast": "Mostly Sunny",
                            "probabilityOfPrecipitation": {"value": 10},
                        },
                        {
                            "startTime": "2026-09-26T19:00:00-05:00",
                            "endTime": "2026-09-27T07:00:00-05:00",
                            "isDaytime": False,
                            "temperature": 68,
                            "temperatureUnit": "F",
                            "shortForecast": "Partly Cloudy",
                            "probabilityOfPrecipitation": {"value": 20},
                        },
                    ]
                }
            },
            "https://api.weather.gov/gridpoints/FWD/1,2/stations": {
                "features": [
                    {
                        "id": "https://api.weather.gov/stations/KTEST",
                        "properties": {
                            "stationIdentifier": "KTEST",
                        },
                    }
                ]
            },
            "https://api.weather.gov/stations/KTEST/observations/latest": {
                "properties": {
                    "timestamp": "2026-09-26T11:55:00+00:00",
                    "textDescription": "Clear",
                    "temperature": {
                        "value": 25.0,
                        "unitCode": "wmoUnit:degC",
                    },
                    "heatIndex": {
                        "value": 26.0,
                        "unitCode": "wmoUnit:degC",
                    },
                    "windChill": {"value": None, "unitCode": "wmoUnit:degC"},
                    "relativeHumidity": {
                        "value": 55.0,
                        "unitCode": "wmoUnit:percent",
                    },
                    "windSpeed": {
                        "value": 5.0,
                        "unitCode": "wmoUnit:m_s-1",
                    },
                    "precipitationLastHour": {
                        "value": 0.001,
                        "unitCode": "wmoUnit:m",
                    },
                }
            },
        }
    )

    provider = NwsEnvironmentProvider(
        configuration(),
        client=client,
    )
    observation = provider.observe(now=NOW)
    weather = observation.weather

    assert weather is not None
    assert weather.condition == "Clear"
    assert weather.source_id == "nws:KTEST"
    assert weather.location_label == "Home"
    assert weather.temperature_c == 25.0
    assert weather.feels_like_c == 26.0
    assert weather.humidity_percent == 55.0
    assert round(weather.wind_kph, 1) == 18.0
    assert weather.precipitation_mm == 1.0
    assert weather.observed_at == NOW - timedelta(minutes=5)
    assert len(weather.forecast) == 2
    assert round(weather.forecast[0].high_c, 1) == 30.0
    assert weather.forecast[0].low_c is None
    assert round(weather.forecast[1].low_c, 1) == 20.0
    assert weather.forecast[1].high_c is None
    assert weather.forecast[0].precipitation_probability == 10.0


def test_nws_provider_can_target_configured_runtime_host_location():
    client = FakeNwsClient(
        {
            "/points/32.6000,-97.2000": {
                "properties": {
                    "observationStations": (
                        "https://api.weather.gov/gridpoints/FWD/3,4/stations"
                    ),
                }
            },
            "https://api.weather.gov/gridpoints/FWD/3,4/stations": {
                "features": [
                    {
                        "id": "https://api.weather.gov/stations/KHOST",
                    }
                ]
            },
            "https://api.weather.gov/stations/KHOST/observations/latest": {
                "properties": {
                    "timestamp": "2026-09-26T11:55:00+00:00",
                    "textDescription": "Cloudy",
                    "temperature": {
                        "value": 20.0,
                        "unitCode": "wmoUnit:degC",
                    },
                }
            },
        }
    )

    provider = NwsEnvironmentProvider(
        configuration(subject=LocationSubject.HOST),
        client=client,
    )
    weather = provider.observe(now=NOW).weather

    assert weather is not None
    assert weather.location_label == "Artemis"
    assert client.requests[0] == "/points/32.6000,-97.2000"


def test_nws_provider_rejects_naive_now():
    provider = NwsEnvironmentProvider(
        configuration(),
        client=FakeNwsClient({}),
    )
    with pytest.raises(ValueError, match="time must be aware"):
        provider.observe(now=datetime(2026, 9, 26, 12, 0))

def test_nws_provider_prefers_current_station_over_stale_nearest_station():
    client = FakeNwsClient(
        {
            "/points/32.5000,-97.1000": {
                "properties": {
                    "observationStations": (
                        "https://api.weather.gov/gridpoints/FWD/1,2/stations"
                    ),
                }
            },
            "https://api.weather.gov/gridpoints/FWD/1,2/stations": {
                "features": [
                    {"id": "https://api.weather.gov/stations/KSTALE"},
                    {"id": "https://api.weather.gov/stations/KFRESH"},
                ]
            },
            "https://api.weather.gov/stations/KSTALE/observations/latest": {
                "properties": {
                    "timestamp": "2026-09-26T10:00:00+00:00",
                    "textDescription": "Old",
                    "temperature": {
                        "value": 19.0,
                        "unitCode": "wmoUnit:degC",
                    },
                }
            },
            "https://api.weather.gov/stations/KFRESH/observations/latest": {
                "properties": {
                    "timestamp": "2026-09-26T11:50:00+00:00",
                    "textDescription": "Fresh",
                    "temperature": {
                        "value": 24.0,
                        "unitCode": "wmoUnit:degC",
                    },
                }
            },
        }
    )

    weather = NwsEnvironmentProvider(
        configuration(),
        client=client,
    ).observe(now=NOW).weather

    assert weather is not None
    assert weather.condition == "Fresh"
    assert weather.source_id == "nws:KFRESH"

