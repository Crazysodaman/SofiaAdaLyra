from datetime import datetime, timezone
import sqlite3

from sofia.ui import (
    DesktopControlSettings,
    DesktopControlSettingsStore,
    GameMode,
    MASTER_SETTINGS_SECTIONS,
    RemoteChatMode,
    TrayCommand,
    TrayStatus,
    tray_menu_labels,
)


NOW = datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc)


def _state(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    return path


def test_control_settings_default_to_close_to_tray_game_auto_and_fleet_remote(tmp_path):
    store = DesktopControlSettingsStore(_state(tmp_path))
    settings = store.load()
    assert settings.close_to_tray is True
    assert settings.game_mode is GameMode.AUTO
    assert settings.remote_chat_mode is RemoteChatMode.FLEET_AUTO


def test_control_settings_round_trip_manual_game_mode_and_pinned_remote(tmp_path):
    store = DesktopControlSettingsStore(_state(tmp_path))
    settings = DesktopControlSettings(
        close_to_tray=True,
        start_with_windows=True,
        game_mode=GameMode.ON,
        remote_chat_mode=RemoteChatMode.PINNED_ENDPOINT,
        pinned_chat_endpoint="https://artemis.example.invalid:7443",
        runtime_service_name="SofiaAdaLyra",
        llm_service_name="Ollama",
    )
    store.save(settings, at=NOW)
    assert store.load() == settings


def test_tray_has_separate_llm_runtime_game_and_settings_controls():
    menu = dict(
        tray_menu_labels(
            TrayStatus(
                runtime_host="artemis",
                runtime_state="running",
                llm_host="artemis",
                llm_state="running",
                llm_model="qwen3:14b",
                game_mode=GameMode.AUTO,
                fleet_total=5,
                fleet_healthy=5,
                fleet_attention=0,
            )
        )
    )
    assert TrayCommand.GAME_ON in menu
    assert TrayCommand.GAME_OFF in menu
    assert TrayCommand.LLM_STOP in menu
    assert TrayCommand.RUNTIME_STOP in menu
    assert TrayCommand.OPEN_SETTINGS in menu
    assert menu[TrayCommand.LLM_STOP] == "Stop qwen3:14b"


def test_master_settings_has_expected_command_center_sections():
    expected = {
        "General", "Chat", "ACT", "Fleet", "Workloads", "Models",
        "Integrations", "Environment", "Avatar", "Memory", "EVOLVE",
        "Safety & Authority", "Advanced",
    }
    assert expected.issubset(set(MASTER_SETTINGS_SECTIONS))
