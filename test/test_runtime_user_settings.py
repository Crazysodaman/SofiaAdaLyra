from datetime import datetime, timezone

import pytest

from sofia.config.user_settings import (
    RuntimeUserSettings,
    RuntimeUserSettingsStore,
)
from sofia.environment.model import LocationSubject


NOW = datetime(2026, 9, 28, 20, 0, tzinfo=timezone.utc)


def test_runtime_user_settings_round_trip(tmp_path):
    state = tmp_path / "sofia.db"
    store = RuntimeUserSettingsStore(state)
    settings = RuntimeUserSettings(
        provider_model="qwen3:14b",
        provider_context_size=32768,
        provider_thinking=True,
        cognitive_routing_enabled=True,
        cognitive_primary_model="qwen3.5:9b",
        cognitive_secondary_model="huihui_ai/qwen3.5-abliterated:4b",
        cognitive_primary_context_size=16000,
        cognitive_secondary_context_size=8192,
        cognitive_verify_enabled=False,
        discord_enabled=True,
        discord_owner_user_id=123456789012345678,
        discord_bot_user_id=987654321098765432,
        discord_dm_channel_id=223456789012345678,
        home_assistant_enabled=True,
        home_assistant_url="http://home-assistant.local:8123",
        home_assistant_weather_entity="weather.home",
        home_assistant_current_location_subject=LocationSubject.USER,
        location_label="Home",
        location_timezone="America/Chicago",
        location_latitude=32.5,
        location_longitude=-97.1,
        location_subject=LocationSubject.USER,
        nws_enabled=True,
        nws_location_subject=LocationSubject.USER,
        nws_user_agent="SofiaAdaLyra/1.0 test@example.invalid",
        refresh_seconds=120,
        weather_max_age_seconds=900,
        indoor_max_age_seconds=600,
        current_location_max_age_seconds=300,
    )

    store.save(settings, at=NOW)

    assert store.load() == settings


def test_environment_mapping_contains_only_enabled_integrations():
    settings = RuntimeUserSettings(
        location_label="Home",
        location_timezone="America/Chicago",
        location_latitude=32.5,
        location_longitude=-97.1,
        nws_enabled=True,
        home_assistant_enabled=False,
        home_assistant_weather_entity="weather.home",
    )

    mapping = settings.environment_mapping()

    assert mapping["SOFIA_ENVIRONMENT_LOCATION_LABEL"] == "Home"
    assert mapping["SOFIA_ENVIRONMENT_TIMEZONE"] == "America/Chicago"
    assert mapping["SOFIA_ENVIRONMENT_NWS_ENABLED"] == "1"
    assert "SOFIA_ENVIRONMENT_HA_WEATHER_ENTITY" not in mapping


def test_enabled_discord_requires_owner_and_bot_ids():
    with pytest.raises(ValueError, match="owner and bot IDs"):
        RuntimeUserSettings(
            discord_enabled=True,
            discord_owner_user_id=123456789012345678,
        )


def test_enabled_discord_allows_channel_autodiscovery():
    settings = RuntimeUserSettings(
        discord_enabled=True,
        discord_owner_user_id=123456789012345678,
        discord_bot_user_id=987654321098765432,
        discord_dm_channel_id=None,
    )

    assert settings.discord_dm_channel_id is None


def test_enabled_home_assistant_requires_entity():
    with pytest.raises(ValueError, match="at least one entity"):
        RuntimeUserSettings(
            home_assistant_enabled=True,
            home_assistant_url="http://home-assistant.local:8123",
        )


def test_location_requires_coordinate_pair():
    with pytest.raises(ValueError, match="latitude and longitude"):
        RuntimeUserSettings(
            location_label="Home",
            location_timezone="America/Chicago",
            location_latitude=32.5,
        )



def test_routing_settings_validate_context_sizes():
    with pytest.raises(ValueError, match="cognitive_secondary_context_size"):
        RuntimeUserSettings(
            cognitive_secondary_context_size=0,
        )
