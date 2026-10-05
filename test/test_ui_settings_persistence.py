from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from sofia.config import create_production_configuration
from sofia.config.model import FleetCognitionConfiguration, FleetDiscoveryConfiguration
from sofia.config.user_settings import OutreachSettings, RuntimeUserSettings, RuntimeUserSettingsStore
from sofia.ops.activity import ActivityMode, HostActivityStore
from sofia.safe.secret_store import ProtectedSecretStore
from sofia.ui.control_center import DesktopControlSettings, DesktopControlSettingsStore, GameMode
from sofia.ui import settings_service


def profile(tmp_path):
    path = tmp_path / "selected.db"
    RuntimeUserSettingsStore(path)
    return path


def test_settings_survive_a_new_python_process_and_reach_configuration(tmp_path):
    path = profile(tmp_path)
    runtime = RuntimeUserSettings(
        provider_model="custom:model", provider_temperature=0.25, provider_seed=19, provider_max_output_tokens=512,
        adaptive_theme=False, idle_reflections_enabled=False, habit_learning_enabled=False,
        avatar_routines_enabled=False, avatar_daily_outfit="night.lounge",
        fleet_cognition=FleetCognitionConfiguration(enabled=True, allowed_host_ids=("trusted-node",)),
        fleet_discovery_interval_seconds=90, fleet_discovery_targets=("10.0.0.2",),
        outreach=OutreachSettings(mute=True, max_daily=3),
    )
    desktop = DesktopControlSettings(close_to_tray=False, game_mode=GameMode.ON, runtime_service_name="SelectedRuntime")
    settings_service.save_settings(path, desktop, runtime, host_id="host")
    code = """
import json, sys
from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.ui.control_center import DesktopControlSettingsStore
from sofia.config import create_production_configuration
from pathlib import Path
p=Path(sys.argv[1]); u=RuntimeUserSettingsStore(p).load(); d=DesktopControlSettingsStore(p).load()
c=create_production_configuration(state_path=p)
print(json.dumps({'model': c.provider.model,'seed':c.provider.seed,'temperature':c.provider.temperature,'max_output':c.provider.max_output_tokens,'theme':u.adaptive_theme,'tray':d.close_to_tray,'game':d.game_mode.value,'hosts':c.fleet_cognition.allowed_host_ids,'interval':c.fleet_discovery.interval_seconds,'outfit':u.avatar_daily_outfit,'mute':u.outreach.mute}))
"""
    actual = json.loads(subprocess.check_output([sys.executable, "-c", code, str(path)], text=True))
    assert actual == {"model": "custom:model", "seed": 19, "temperature": 0.25, "max_output": 512, "theme": False, "tray": False, "game": "on", "hosts": ["trusted-node"], "interval": 90, "outfit": "night.lounge", "mute": True}


def test_settings_and_activity_rollback_together_on_database_failure(tmp_path, monkeypatch):
    path = profile(tmp_path)
    initial = RuntimeUserSettings(provider_model="original:model")
    settings_service.save_settings(path, DesktopControlSettings(), initial, host_id="host")
    def fail(*args, **kwargs):
        raise RuntimeError("simulated activity failure")
    monkeypatch.setattr(HostActivityStore, "set_override", fail)
    with pytest.raises(RuntimeError, match="activity failure"):
        settings_service.save_settings(path, DesktopControlSettings(game_mode=GameMode.ON), replace(initial, provider_model="changed:model"), host_id="host")
    assert RuntimeUserSettingsStore(path).load() == initial
    assert DesktopControlSettingsStore(path).load().game_mode is GameMode.AUTO


def test_registry_failure_keeps_saved_preferences(tmp_path, monkeypatch):
    path = profile(tmp_path)
    monkeypatch.setattr(settings_service.sys, "platform", "win32")
    def fail(*args, **kwargs):
        assert kwargs["state_path"] == path
        raise PermissionError("registry denied")
    monkeypatch.setattr(settings_service, "configure_windows_startup", fail)
    message = settings_service.save_settings(path, DesktopControlSettings(start_with_windows=True), RuntimeUserSettings(adaptive_theme=False), host_id="host")
    assert "registry denied" in message
    assert DesktopControlSettingsStore(path).load().start_with_windows
    assert not RuntimeUserSettingsStore(path).load().adaptive_theme


def test_non_windows_save_never_calls_registry(tmp_path, monkeypatch):
    path = profile(tmp_path)
    monkeypatch.setattr(settings_service.sys, "platform", "linux")
    monkeypatch.setattr(settings_service, "configure_windows_startup", lambda *args, **kwargs: pytest.fail("Unexpected registry operation"))
    settings_service.save_settings(path, DesktopControlSettings(), RuntimeUserSettings(), host_id="host")


def test_protected_secrets_compensate_failed_settings_transaction(tmp_path, monkeypatch):
    path = profile(tmp_path)
    secrets = ProtectedSecretStore(tmp_path / "secrets", protect=lambda value: b"protected:" + value, unprotect=lambda value: value[10:])
    secrets.set("discord-token", "original-token")
    before = (secrets.root / "discord-token.dpapi").read_bytes()
    def fail(*args, **kwargs):
        raise RuntimeError("database write failed")
    monkeypatch.setattr(DesktopControlSettingsStore, "save", fail)
    with pytest.raises(RuntimeError, match="database write"):
        settings_service.save_settings(path, DesktopControlSettings(), RuntimeUserSettings(), host_id="host", secret_changes={"discord-token": "new-token", "home-assistant-token": "another-token"}, secrets=secrets)
    assert (secrets.root / "discord-token.dpapi").read_bytes() == before
    assert not secrets.exists("home-assistant-token")


def test_integration_without_token_does_not_change_any_settings(tmp_path):
    path = profile(tmp_path)
    with pytest.raises(ValueError, match="stored discord-token"):
        settings_service.save_settings(path, DesktopControlSettings(game_mode=GameMode.ON), RuntimeUserSettings(discord_enabled=True, discord_owner_user_id=1, discord_bot_user_id=2), host_id="host")
    assert DesktopControlSettingsStore(path).load().game_mode is GameMode.AUTO


def test_navigation_and_exit_requests_are_consumed_once(tmp_path):
    path = profile(tmp_path)
    store = DesktopControlSettingsStore(path)
    store.request_settings_section("Wardrobe")
    assert DesktopControlSettingsStore(path).consume_settings_section() == "Wardrobe"
    assert store.consume_settings_section() is None
    store.request_tray_exit()
    assert DesktopControlSettingsStore(path).consume_tray_exit()
    assert not store.consume_tray_exit()


@pytest.mark.parametrize("updates", [{"provider_temperature": float("nan")}, {"provider_temperature": float("inf")}, {"provider_seed": True}, {"avatar_routines_enabled": 1}])
def test_invalid_generation_and_runtime_preferences_are_rejected(updates):
    with pytest.raises((ValueError, TypeError)):
        RuntimeUserSettings(**updates)


def test_old_schema_migrates_without_overwriting_user_values(tmp_path):
    path = profile(tmp_path)
    settings = RuntimeUserSettings(provider_model="saved:model", cognitive_model_auto_install=False)
    raw = json.loads(RuntimeUserSettingsStore._encode(settings))
    raw["schema_version"] = 3
    for name in ("provider_temperature", "provider_seed", "adaptive_theme", "avatar_routines_enabled", "avatar_daily_outfit", "idle_reflections_enabled", "habit_learning_enabled", "fleet_cognition", "fleet_bootstrap", "outreach"):
        raw.pop(name)
    import sqlite3
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO ui_runtime_settings VALUES (?,?,?)", ("runtime-user-settings", json.dumps(raw), datetime.now(timezone.utc).isoformat()))
    migrated = RuntimeUserSettingsStore(path).load()
    assert migrated.provider_model == "saved:model"
    assert not migrated.cognitive_model_auto_install
    assert RuntimeUserSettingsStore(path).load() == migrated


def test_saved_outreach_policy_reaches_sender_and_operational_notices(tmp_path, monkeypatch):
    from sofia.application.act_service import SofiaActService, configure_act_delivery_from_environment, notification_destination_from_environment
    path = profile(tmp_path)
    outreach = OutreachSettings(enabled=True, mute=True, notification_service="mobile_app_owner", quiet_start_local=21, quiet_end_local=9, max_daily=2, social_max_daily=2, operational_max_daily=4)
    RuntimeUserSettingsStore(path).save(RuntimeUserSettings(home_assistant_url="http://localhost:8123", outreach=outreach))
    from importlib import import_module
    monkeypatch.setattr(import_module("sofia.safe.secret_store").ProtectedSecretStore, "get", lambda self, key: "protected-test-token")
    service = SofiaActService(path)
    assert configure_act_delivery_from_environment(service)
    assert service.policy.mute
    assert service.policy.quiet_start_local == 21
    assert service.policy.timezone_name == "America/Chicago"
    assert service.policy.social_max_daily == 2
    assert service.policy.operational_max_daily == 4
    assert notification_destination_from_environment(state_path=path) == "mobile_app_owner"
