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
    tray_command_enabled,
    tray_command_requires_confirmation,
    tray_menu_labels,
)


NOW = datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc)


def _state(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    return path


def test_control_settings_default_to_close_to_tray_game_auto_and_local_chat(tmp_path):
    store = DesktopControlSettingsStore(_state(tmp_path))
    settings = store.load()
    assert settings.close_to_tray is True
    assert settings.game_mode is GameMode.AUTO
    assert settings.remote_chat_mode is RemoteChatMode.LOCAL


def test_control_settings_round_trip_manual_game_mode_and_local_chat(tmp_path):
    store = DesktopControlSettingsStore(_state(tmp_path))
    settings = DesktopControlSettings(
        close_to_tray=True,
        start_with_windows=True,
        game_mode=GameMode.ON,
        remote_chat_mode=RemoteChatMode.LOCAL,
        runtime_service_name="SofiaAdaLyra",
        llm_service_name="Ollama",
    )
    store.save(settings, at=NOW)
    assert store.load() == settings


def test_control_settings_reject_split_remote_chat_authority(tmp_path):
    store = DesktopControlSettingsStore(_state(tmp_path))
    settings = DesktopControlSettings(
        remote_chat_mode=RemoteChatMode.PINNED_ENDPOINT,
        pinned_chat_endpoint="https://artemis.example.invalid:7443",
    )
    import pytest
    with pytest.raises(ValueError, match="local-only"):
        store.save(settings, at=NOW)


def test_tray_has_separate_llm_runtime_game_and_settings_controls():
    menu = dict(
        tray_menu_labels(
            TrayStatus(
                runtime_host="artemis",
                runtime_state="running",
                llm_host="artemis",
                llm_state="running",
                llm_model="owner-primary:model",
                game_mode=GameMode.AUTO,
                fleet_total=5,
                fleet_healthy=5,
                fleet_attention=0,
                llm_secondary_model="vendor/open:4b",
                cognitive_routing_enabled=True,
            )
        )
    )
    assert TrayCommand.GAME_ON in menu
    assert TrayCommand.GAME_OFF in menu
    assert TrayCommand.LLM_STOP in menu
    assert TrayCommand.RUNTIME_STOP in menu
    assert TrayCommand.OPEN_SETTINGS in menu
    assert menu[TrayCommand.LLM_STOP] == "Stop LLM service"


def test_master_settings_has_expected_command_center_sections():
    expected = {
        "General", "Chat", "ACT", "Fleet", "Workloads", "Models",
        "Integrations", "Environment", "Avatar", "Memory", "EVOLVE",
        "Safety & Authority", "Advanced",
    }
    assert expected.issubset(set(MASTER_SETTINGS_SECTIONS))


def _tray_status(*, runtime_state="running", llm_state="running"):
    return TrayStatus(
        runtime_host="venus" if runtime_state == "running" else None,
        runtime_state=runtime_state,
        llm_host="venus" if llm_state == "running" else None,
        llm_state=llm_state,
        llm_model="owner-primary:model",
        game_mode=GameMode.AUTO,
        fleet_total=1,
        fleet_healthy=1,
        fleet_attention=0,
    )


def test_runtime_stop_and_restart_require_confirmation():
    assert tray_command_requires_confirmation(TrayCommand.RUNTIME_STOP) is True
    assert tray_command_requires_confirmation(TrayCommand.RUNTIME_RESTART) is True
    assert tray_command_requires_confirmation(TrayCommand.RUNTIME_START) is False


def test_runtime_controls_follow_observed_service_state():
    running = _tray_status(runtime_state="running")
    stopped = _tray_status(runtime_state="stopped")

    assert tray_command_enabled(TrayCommand.RUNTIME_START, running) is False
    assert tray_command_enabled(TrayCommand.RUNTIME_STOP, running) is True
    assert tray_command_enabled(TrayCommand.RUNTIME_RESTART, running) is True

    assert tray_command_enabled(TrayCommand.RUNTIME_START, stopped) is True
    assert tray_command_enabled(TrayCommand.RUNTIME_STOP, stopped) is False
    assert tray_command_enabled(TrayCommand.RUNTIME_RESTART, stopped) is False


def test_missing_ollama_service_disables_service_actions_but_not_unload():
    missing = _tray_status(llm_state="not_found")

    assert tray_command_enabled(TrayCommand.LLM_START, missing) is False
    assert tray_command_enabled(TrayCommand.LLM_STOP, missing) is False
    assert tray_command_enabled(TrayCommand.LLM_RESTART, missing) is False
    assert tray_command_enabled(TrayCommand.LLM_UNLOAD_MODEL, missing) is True



def test_tray_status_reports_arbitrary_dual_model_roles_without_name_logic():
    status = TrayStatus(
        runtime_host="venus",
        runtime_state="running",
        llm_host="venus",
        llm_state="running",
        llm_model="owner-primary:anything",
        game_mode=GameMode.AUTO,
        fleet_total=1,
        fleet_healthy=1,
        fleet_attention=0,
        llm_secondary_model="owner-secondary:anything",
        cognitive_routing_enabled=True,
    )

    assert status.configured_llm_models == (
        "owner-primary:anything",
        "owner-secondary:anything",
    )
    menu = dict(tray_menu_labels(status))
    assert (
        menu[TrayCommand.LLM_UNLOAD_MODEL]
        == "Unload 2 configured models"
    )
