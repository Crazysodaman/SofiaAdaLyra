import pytest

from sofia.environment.config import environment_configuration_from_environ
from sofia.environment.model import LocationSubject


def test_empty_environment_configuration_is_safe_and_offline():
    config = environment_configuration_from_environ({})
    assert config.location is None
    assert not config.home_assistant_enabled
    assert config.refresh_seconds == 300


def test_explicit_location_configuration_preserves_subject_and_coordinates():
    config = environment_configuration_from_environ(
        {
            "SOFIA_ENVIRONMENT_LOCATION_LABEL": "Home area",
            "SOFIA_ENVIRONMENT_TIMEZONE": "America/Chicago",
            "SOFIA_ENVIRONMENT_LATITUDE": "32.5",
            "SOFIA_ENVIRONMENT_LONGITUDE": "-97.1",
            "SOFIA_ENVIRONMENT_LOCATION_SUBJECT": "user",
        }
    )
    assert config.location is not None
    assert config.location.label == "Home area"
    assert config.location.timezone == "America/Chicago"
    assert config.location.subject is LocationSubject.USER
    assert config.location.latitude == 32.5
    assert config.location.longitude == -97.1


def test_partial_location_configuration_fails_closed():
    with pytest.raises(ValueError, match="LOCATION_LABEL"):
        environment_configuration_from_environ(
            {"SOFIA_ENVIRONMENT_TIMEZONE": "America/Chicago"}
        )
    with pytest.raises(ValueError, match="must be supplied together"):
        environment_configuration_from_environ(
            {
                "SOFIA_ENVIRONMENT_LOCATION_LABEL": "Home area",
                "SOFIA_ENVIRONMENT_TIMEZONE": "America/Chicago",
                "SOFIA_ENVIRONMENT_LATITUDE": "32.5",
            }
        )


def test_home_assistant_entities_do_not_require_general_web_configuration():
    config = environment_configuration_from_environ(
        {
            "SOFIA_ENVIRONMENT_HA_WEATHER_ENTITY": "weather.home",
            "SOFIA_ENVIRONMENT_HA_INDOOR_TEMPERATURE_ENTITY": "sensor.room_temperature",
        }
    )
    assert config.home_assistant_enabled
    assert config.home_assistant_weather_entity == "weather.home"


def test_invalid_timezone_is_rejected():
    with pytest.raises(ValueError, match="unknown environment timezone"):
        environment_configuration_from_environ(
            {
                "SOFIA_ENVIRONMENT_LOCATION_LABEL": "Nowhere",
                "SOFIA_ENVIRONMENT_TIMEZONE": "Mars/Olympus_Mons",
            }
        )

def test_ha_current_location_requires_explicit_subject_without_configured_location():
    with pytest.raises(ValueError, match="explicit location subject"):
        environment_configuration_from_environ(
            {
                "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_ENTITY": "device_tracker.host",
            }
        )


def test_ha_current_location_subject_can_be_explicit_host():
    config = environment_configuration_from_environ(
        {
            "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_ENTITY": "device_tracker.host",
            "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_SUBJECT": "host",
        }
    )
    assert config.home_assistant_current_location_subject is LocationSubject.HOST

