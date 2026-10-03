from datetime import datetime, timezone
import json

import pytest

from sofia.config.user_settings import (
    CURRENT_RUNTIME_SETTINGS_SCHEMA_VERSION,
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
        cognitive_secondary_model="huihui_ai/qwen3.5-abliterated:4B",
        cognitive_primary_context_size=16000,
        cognitive_secondary_context_size=8192,
        cognitive_verify_enabled=False,
        cognitive_model_auto_manage=True,
        cognitive_model_idle_unload_seconds=600,
        cognitive_model_keep_alive="4m",
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



def test_model_lifecycle_settings_validate_idle_timeout():
    with pytest.raises(ValueError, match="cognitive_model_idle_unload_seconds"):
        RuntimeUserSettings(
            cognitive_model_idle_unload_seconds=0,
        )


def test_model_lifecycle_settings_validate_keep_alive():
    with pytest.raises(ValueError, match="cognitive_model_keep_alive"):
        RuntimeUserSettings(
            cognitive_model_keep_alive="",
        )



def test_fresh_runtime_settings_enable_dual_cognition_and_residency():
    settings = RuntimeUserSettings()

    assert settings.schema_version == CURRENT_RUNTIME_SETTINGS_SCHEMA_VERSION
    assert settings.cognitive_routing_enabled is True
    assert settings.cognitive_model_auto_manage is True
    assert settings.cognitive_model_auto_install is True
    assert settings.provider_model == settings.cognitive_primary_model


def test_legacy_saved_settings_migrate_to_dual_cognition(tmp_path):
    state = tmp_path / "legacy-sofia.db"
    store = RuntimeUserSettingsStore(state)
    legacy = {
        "provider_model": "qwen3:14b",
        "provider_context_size": 20000,
        "provider_thinking": False,
        "cognitive_routing_enabled": False,
        "cognitive_primary_model": "owner/primary:any",
        "cognitive_secondary_model": "owner/secondary:any",
        "cognitive_primary_context_size": 16000,
        "cognitive_secondary_context_size": 8192,
        "cognitive_verify_enabled": True,
        "cognitive_model_auto_manage": False,
        "cognitive_model_idle_unload_seconds": 1800,
        "cognitive_model_keep_alive": "10m",
        "discord_enabled": False,
        "discord_owner_user_id": None,
        "discord_bot_user_id": None,
        "discord_dm_channel_id": None,
        "home_assistant_enabled": False,
        "home_assistant_url": None,
        "home_assistant_weather_entity": None,
        "home_assistant_indoor_temperature_entity": None,
        "home_assistant_indoor_humidity_entity": None,
        "home_assistant_current_location_entity": None,
        "home_assistant_current_location_subject": None,
        "location_label": None,
        "location_timezone": None,
        "location_latitude": None,
        "location_longitude": None,
        "location_subject": "user",
        "nws_enabled": False,
        "nws_location_subject": "user",
        "nws_user_agent": "SofiaAdaLyra/1.0",
        "refresh_seconds": 300,
        "weather_max_age_seconds": 1800,
        "indoor_max_age_seconds": 900,
        "current_location_max_age_seconds": 900,
    }
    with store._connect() as db, db:
        db.execute(
            "INSERT INTO ui_runtime_settings "
            "(settings_key,value_json,updated_at) VALUES (?,?,?)",
            (
                store._KEY,
                json.dumps(legacy),
                NOW.isoformat(),
            ),
        )

    migrated = store.load()

    assert migrated.schema_version == CURRENT_RUNTIME_SETTINGS_SCHEMA_VERSION
    assert migrated.cognitive_routing_enabled is True
    assert migrated.cognitive_model_auto_manage is True
    assert migrated.cognitive_model_auto_install is True
    assert migrated.cognitive_primary_model == "owner/primary:any"
    assert migrated.cognitive_secondary_model == "owner/secondary:any"
    assert migrated.provider_model == migrated.cognitive_primary_model



def test_loading_legacy_settings_persists_current_schema(tmp_path):
    state = tmp_path / "legacy-persisted.db"
    store = RuntimeUserSettingsStore(state)
    legacy = {
        "provider_model": "qwen3:14b",
        "provider_context_size": 20000,
        "provider_thinking": False,
        "cognitive_routing_enabled": False,
        "cognitive_primary_model": "owner/primary:any",
        "cognitive_secondary_model": "owner/secondary:any",
        "cognitive_primary_context_size": 16000,
        "cognitive_secondary_context_size": 8192,
        "cognitive_verify_enabled": True,
        "cognitive_model_auto_manage": False,
        "cognitive_model_idle_unload_seconds": 1800,
        "cognitive_model_keep_alive": "10m",
        "discord_enabled": False,
        "discord_owner_user_id": None,
        "discord_bot_user_id": None,
        "discord_dm_channel_id": None,
        "home_assistant_enabled": False,
        "home_assistant_url": None,
        "home_assistant_weather_entity": None,
        "home_assistant_indoor_temperature_entity": None,
        "home_assistant_indoor_humidity_entity": None,
        "home_assistant_current_location_entity": None,
        "home_assistant_current_location_subject": None,
        "location_label": None,
        "location_timezone": None,
        "location_latitude": None,
        "location_longitude": None,
        "location_subject": "user",
        "nws_enabled": False,
        "nws_location_subject": "user",
        "nws_user_agent": "SofiaAdaLyra/1.0",
        "refresh_seconds": 300,
        "weather_max_age_seconds": 1800,
        "indoor_max_age_seconds": 900,
        "current_location_max_age_seconds": 900,
    }
    with store._connect() as db, db:
        db.execute(
            "INSERT INTO ui_runtime_settings "
            "(settings_key,value_json,updated_at) VALUES (?,?,?)",
            (store._KEY,json.dumps(legacy),NOW.isoformat()),
        )

    store.load()

    with store._connect() as db:
        raw=db.execute(
            "SELECT value_json FROM ui_runtime_settings WHERE settings_key=?",
            (store._KEY,),
        ).fetchone()[0]
    persisted=json.loads(raw)
    assert persisted["schema_version"]==CURRENT_RUNTIME_SETTINGS_SCHEMA_VERSION
    assert persisted["cognitive_routing_enabled"] is True
    assert persisted["cognitive_model_auto_manage"] is True
    assert persisted["cognitive_model_auto_install"] is True


def test_schema_v2_without_location_migrates_to_central_time(tmp_path):
    import json
    import sqlite3

    state = tmp_path / "sofia.db"
    store = RuntimeUserSettingsStore(state)
    legacy = RuntimeUserSettings()
    payload = json.loads(store._encode(legacy))
    payload["schema_version"] = 2
    payload["location_label"] = None
    payload["location_timezone"] = None

    with sqlite3.connect(state) as db:
        db.execute(
            """
            INSERT OR REPLACE INTO ui_runtime_settings
                (settings_key, value_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (
                "runtime-user-settings",
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                "2026-10-03T12:00:00+00:00",
            ),
        )

    migrated = RuntimeUserSettingsStore(state).load()

    assert migrated.schema_version == 3
    assert migrated.location_label == "Home"
    assert migrated.location_timezone == "America/Chicago"
