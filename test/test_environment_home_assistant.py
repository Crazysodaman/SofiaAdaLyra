from datetime import datetime, timezone

from sofia.environment.config import (
    ConfiguredLocation,
    EnvironmentConfiguration,
)
from sofia.environment.home_assistant import HomeAssistantEnvironmentProvider
from sofia.environment.model import LocationSubject
from sofia.integrations.home_assistant import HomeAssistantAdapter


NOW = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)


class FakeHomeAssistantAdapter(HomeAssistantAdapter):
    def __init__(self, states):
        self._states = states

    def state(self, entity_id):
        return self._states[entity_id]


def test_home_assistant_weather_normalizes_units_and_forecast():
    adapter = FakeHomeAssistantAdapter(
        {
            "weather.home": {
                "state": "rainy",
                "last_updated": "2026-09-25T17:55:00+00:00",
                "attributes": {
                    "friendly_name": "Home weather",
                    "temperature": 68,
                    "apparent_temperature": 66,
                    "temperature_unit": "°F",
                    "humidity": 72,
                    "wind_speed": 10,
                    "wind_speed_unit": "mph",
                    "precipitation": 2.5,
                    "forecast": [
                        {
                            "datetime": "2026-09-26T00:00:00+00:00",
                            "condition": "cloudy",
                            "temperature": 72,
                            "templow": 55,
                            "precipitation_probability": 30,
                        }
                    ],
                },
            }
        }
    )
    provider = HomeAssistantEnvironmentProvider(
        adapter,
        EnvironmentConfiguration(
            home_assistant_weather_entity="weather.home",
        ),
    )
    observation = provider.observe(now=NOW)
    weather = observation.weather
    assert weather is not None
    assert weather.condition == "rainy"
    assert round(weather.temperature_c, 1) == 20.0
    assert round(weather.feels_like_c, 1) == 18.9
    assert round(weather.wind_kph, 1) == 16.1
    assert weather.humidity_percent == 72.0
    assert len(weather.forecast) == 1
    assert round(weather.forecast[0].high_c, 1) == 22.2


def test_home_assistant_indoor_entities_are_explicit_only():
    adapter = FakeHomeAssistantAdapter(
        {
            "sensor.room_temperature": {
                "state": "71.6",
                "last_updated": "2026-09-25T17:58:00+00:00",
                "attributes": {"unit_of_measurement": "°F"},
            },
            "sensor.room_humidity": {
                "state": "44",
                "last_updated": "2026-09-25T17:59:00+00:00",
                "attributes": {"unit_of_measurement": "%"},
            },
        }
    )
    provider = HomeAssistantEnvironmentProvider(
        adapter,
        EnvironmentConfiguration(
            home_assistant_indoor_temperature_entity=(
                "sensor.room_temperature"
            ),
            home_assistant_indoor_humidity_entity=(
                "sensor.room_humidity"
            ),
        ),
    )
    indoor = provider.observe(now=NOW).indoor
    assert indoor is not None
    assert round(indoor.temperature_c, 1) == 22.0
    assert indoor.humidity_percent == 44.0


def test_home_assistant_current_location_requires_explicit_entity_and_coordinates():
    adapter = FakeHomeAssistantAdapter(
        {
            "person.sparks": {
                "state": "home",
                "last_updated": "2026-09-25T17:57:00+00:00",
                "attributes": {
                    "latitude": 32.5,
                    "longitude": -97.1,
                    "gps_accuracy": 18,
                    "time_zone": "America/Denver",
                },
            }
        }
    )
    provider = HomeAssistantEnvironmentProvider(
        adapter,
        EnvironmentConfiguration(
            location=ConfiguredLocation(
                label="Configured area",
                timezone="America/Chicago",
            ),
            home_assistant_current_location_entity="person.sparks",
        ),
    )
    location = provider.observe(now=NOW).current_location
    assert location is not None
    assert location.label == "home"
    assert location.latitude == 32.5
    assert location.longitude == -97.1
    assert location.precision_meters == 18.0
    assert location.timezone == "America/Denver"

def test_home_assistant_missing_timestamp_does_not_become_current_weather():
    adapter = FakeHomeAssistantAdapter(
        {
            "weather.home": {
                "state": "clear",
                "attributes": {
                    "temperature": 20,
                    "temperature_unit": "°C",
                },
            }
        }
    )
    provider = HomeAssistantEnvironmentProvider(
        adapter,
        EnvironmentConfiguration(
            home_assistant_weather_entity="weather.home",
        ),
    )
    assert provider.observe(now=NOW).weather is None


def test_home_assistant_missing_timestamp_does_not_become_current_location():
    adapter = FakeHomeAssistantAdapter(
        {
            "person.sparks": {
                "state": "home",
                "attributes": {
                    "latitude": 32.5,
                    "longitude": -97.1,
                },
            }
        }
    )
    provider = HomeAssistantEnvironmentProvider(
        adapter,
        EnvironmentConfiguration(
            home_assistant_current_location_entity="person.sparks",
            home_assistant_current_location_subject=LocationSubject.USER,
        ),
    )
    assert provider.observe(now=NOW).current_location is None

def test_home_assistant_current_location_preserves_explicit_host_subject():
    adapter = FakeHomeAssistantAdapter(
        {
            "device_tracker.host": {
                "state": "server-room",
                "last_updated": "2026-09-25T17:57:00+00:00",
                "attributes": {
                    "latitude": 32.5,
                    "longitude": -97.1,
                    "time_zone": "America/Chicago",
                },
            }
        }
    )
    provider = HomeAssistantEnvironmentProvider(
        adapter,
        EnvironmentConfiguration(
            home_assistant_current_location_entity="device_tracker.host",
            home_assistant_current_location_subject=LocationSubject.HOST,
        ),
    )
    location = provider.observe(now=NOW).current_location
    assert location is not None
    assert location.subject is LocationSubject.HOST

