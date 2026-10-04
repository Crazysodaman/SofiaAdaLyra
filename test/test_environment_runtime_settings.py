"""Production runtime settings keep Sofía's NWS station explicit."""
from sofia.config.user_settings import RuntimeUserSettings


def test_runtime_weather_defaults_to_kgky_station():
    settings = RuntimeUserSettings()

    assert settings.nws_station_id == "KGKY"
    mapping = settings.environment_mapping()
    assert mapping["SOFIA_ENVIRONMENT_NWS_STATION_ID"] == "KGKY"


def test_runtime_weather_station_is_normalized():
    settings = RuntimeUserSettings(nws_station_id="kgky")

    assert settings.nws_station_id == "KGKY"
