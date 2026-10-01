"""Tray/master-settings control contracts for the Sofía desktop client.

This module is renderer-neutral. Native Windows tray code consumes these typed
actions; it does not invent service names, hosts, or authority.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3


class GameMode(str, Enum):
    AUTO = "auto"
    ON = "on"
    OFF = "off"


class ServiceAction(str, Enum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    INSTALL_MODEL = "install_model"
    LOAD_MODEL = "load_model"
    UNLOAD_MODEL = "unload_model"


class ServiceKind(str, Enum):
    SOFIA_RUNTIME = "sofia_runtime"
    LLM_ENGINE = "llm_engine"


class RemoteChatMode(str, Enum):
    LOCAL = "local"
    FLEET_AUTO = "fleet_auto"
    PINNED_ENDPOINT = "pinned_endpoint"


@dataclass(frozen=True)
class ServiceTarget:
    kind: ServiceKind
    host_id: str
    service_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ServiceKind):
            raise TypeError("ServiceKind required")
        if not isinstance(self.host_id, str) or not self.host_id.strip():
            raise ValueError("host_id required")
        if not isinstance(self.service_name, str) or not self.service_name.strip():
            raise ValueError("service_name required")


@dataclass(frozen=True)
class TrayStatus:
    runtime_host: str | None
    runtime_state: str
    llm_host: str | None
    llm_state: str
    llm_model: str | None
    game_mode: GameMode
    fleet_total: int
    fleet_healthy: int
    fleet_attention: int
    llm_secondary_model: str | None = None
    cognitive_routing_enabled: bool = False
    llm_primary_residency: str | None = None
    llm_secondary_residency: str | None = None
    cognitive_auto_manage: bool = False
    cognitive_idle_unload_seconds: int | None = None

    @property
    def configured_llm_models(self) -> tuple[str, ...]:
        values = (
            self.llm_model,
            self.llm_secondary_model
            if self.cognitive_routing_enabled
            else None,
        )
        return tuple(dict.fromkeys(value for value in values if value))


@dataclass(frozen=True)
class DesktopControlSettings:
    close_to_tray: bool = True
    start_with_windows: bool = False
    game_mode: GameMode = GameMode.AUTO
    remote_chat_mode: RemoteChatMode = RemoteChatMode.LOCAL
    pinned_chat_endpoint: str | None = None
    runtime_service_name: str = "SofiaAdaLyra"
    llm_service_name: str = "Ollama"

    def __post_init__(self) -> None:
        if not isinstance(self.close_to_tray, bool) or not isinstance(self.start_with_windows, bool):
            raise TypeError("desktop toggles must be boolean")
        if not isinstance(self.game_mode, GameMode):
            raise TypeError("game_mode must be GameMode")
        if not isinstance(self.remote_chat_mode, RemoteChatMode):
            raise TypeError("remote_chat_mode must be RemoteChatMode")
        if self.remote_chat_mode is RemoteChatMode.PINNED_ENDPOINT:
            if not isinstance(self.pinned_chat_endpoint, str) or not self.pinned_chat_endpoint.strip():
                raise ValueError("pinned endpoint mode requires pinned_chat_endpoint")
        for value, label in (
            (self.runtime_service_name, "runtime_service_name"),
            (self.llm_service_name, "llm_service_name"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} required")


class DesktopControlSettingsStore:
    """Small durable settings record in Sofía's existing state database."""

    _KEY = "desktop-control"

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ui_control_settings (
                        settings_key TEXT PRIMARY KEY,
                        close_to_tray INTEGER NOT NULL,
                        start_with_windows INTEGER NOT NULL,
                        game_mode TEXT NOT NULL,
                        remote_chat_mode TEXT NOT NULL,
                        pinned_chat_endpoint TEXT,
                        runtime_service_name TEXT NOT NULL,
                        llm_service_name TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def load(self) -> DesktopControlSettings:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT close_to_tray,start_with_windows,game_mode,remote_chat_mode,
                       pinned_chat_endpoint,runtime_service_name,llm_service_name
                FROM ui_control_settings WHERE settings_key=?
                """,
                (self._KEY,),
            ).fetchone()
        if row is None:
            return DesktopControlSettings()
        return DesktopControlSettings(
            close_to_tray=bool(row[0]),
            start_with_windows=bool(row[1]),
            game_mode=GameMode(row[2]),
            remote_chat_mode=RemoteChatMode(row[3]),
            pinned_chat_endpoint=row[4],
            runtime_service_name=row[5],
            llm_service_name=row[6],
        )

    def save(self, settings: DesktopControlSettings, *, at: datetime) -> None:
        if not isinstance(settings, DesktopControlSettings):
            raise TypeError("DesktopControlSettings required")
        if settings.remote_chat_mode is not RemoteChatMode.LOCAL:
            raise ValueError(
                "desktop chat authority is local-only until shared state "
                "mobility/fencing is implemented"
            )
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("timezone-aware timestamp required")
        moment = at.astimezone(timezone.utc)
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    INSERT INTO ui_control_settings
                    VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(settings_key) DO UPDATE SET
                        close_to_tray=excluded.close_to_tray,
                        start_with_windows=excluded.start_with_windows,
                        game_mode=excluded.game_mode,
                        remote_chat_mode=excluded.remote_chat_mode,
                        pinned_chat_endpoint=excluded.pinned_chat_endpoint,
                        runtime_service_name=excluded.runtime_service_name,
                        llm_service_name=excluded.llm_service_name,
                        updated_at=excluded.updated_at
                    """,
                    (
                        self._KEY,
                        int(settings.close_to_tray),
                        int(settings.start_with_windows),
                        settings.game_mode.value,
                        settings.remote_chat_mode.value,
                        settings.pinned_chat_endpoint,
                        settings.runtime_service_name,
                        settings.llm_service_name,
                        moment.isoformat(),
                    ),
                )


class TrayCommand(str, Enum):
    OPEN_CHAT = "open_chat"
    OPEN_FLEET = "open_fleet"
    OPEN_SETTINGS = "open_settings"
    GAME_AUTO = "game_auto"
    GAME_ON = "game_on"
    GAME_OFF = "game_off"
    LLM_START = "llm_start"
    LLM_STOP = "llm_stop"
    LLM_RESTART = "llm_restart"
    LLM_INSTALL_PRIMARY = "llm_install_primary"
    LLM_INSTALL_SECONDARY = "llm_install_secondary"
    LLM_LOAD_PRIMARY = "llm_load_primary"
    LLM_LOAD_SECONDARY = "llm_load_secondary"
    LLM_UNLOAD_MODEL = "llm_unload_model"
    RUNTIME_START = "runtime_start"
    RUNTIME_STOP = "runtime_stop"
    RUNTIME_RESTART = "runtime_restart"
    DIAGNOSTICS = "diagnostics"
    EXIT_UI = "exit_ui"


def tray_menu_labels(status: TrayStatus) -> tuple[tuple[TrayCommand, str], ...]:
    """Stable quick-control menu; renderer may group/submenu these entries."""
    model_count = len(status.configured_llm_models)
    unload_label = (
        "Unload configured model"
        if model_count <= 1
        else f"Unload {model_count} configured models"
    )
    return (
        (TrayCommand.OPEN_CHAT, "Open Sofía"),
        (TrayCommand.OPEN_FLEET, f"Fleet: {status.fleet_healthy}/{status.fleet_total} healthy"),
        (TrayCommand.GAME_AUTO, "Game Mode: Auto"),
        (TrayCommand.GAME_ON, "Game Mode: On"),
        (TrayCommand.GAME_OFF, "Game Mode: Off"),
        (TrayCommand.LLM_START, "Start LLM service"),
        (TrayCommand.LLM_STOP, "Stop LLM service"),
        (TrayCommand.LLM_RESTART, "Restart LLM service"),
        (TrayCommand.LLM_INSTALL_PRIMARY, "Install primary model"),
        (TrayCommand.LLM_INSTALL_SECONDARY, "Install secondary model"),
        (TrayCommand.LLM_LOAD_PRIMARY, "Load primary model"),
        (TrayCommand.LLM_LOAD_SECONDARY, "Load secondary model"),
        (TrayCommand.LLM_UNLOAD_MODEL, unload_label),
        (TrayCommand.RUNTIME_START, "Start Sofía runtime"),
        (TrayCommand.RUNTIME_STOP, "Stop Sofía runtime"),
        (TrayCommand.RUNTIME_RESTART, "Restart Sofía runtime"),
        (TrayCommand.OPEN_SETTINGS, "Settings…"),
        (TrayCommand.DIAGNOSTICS, "Diagnostics"),
        (TrayCommand.EXIT_UI, "Exit UI"),
    )


MASTER_SETTINGS_SECTIONS = (
    "General",
    "Sofía",
    "Chat",
    "ACT",
    "Fleet",
    "Workloads",
    "Models",
    "Integrations",
    "Environment",
    "Avatar",
    "Memory",
    "EVOLVE",
    "Safety & Authority",
    "Advanced",
)


def tray_command_requires_confirmation(command: TrayCommand) -> bool:
    if not isinstance(command, TrayCommand):
        raise TypeError("TrayCommand required")
    return command in {
        TrayCommand.RUNTIME_STOP,
        TrayCommand.RUNTIME_RESTART,
    }


def tray_command_enabled(command: TrayCommand, status: TrayStatus) -> bool:
    if not isinstance(command, TrayCommand):
        raise TypeError("TrayCommand required")
    if not isinstance(status, TrayStatus):
        raise TypeError("TrayStatus required")
    if command in {
        TrayCommand.LLM_START,
        TrayCommand.LLM_STOP,
        TrayCommand.LLM_RESTART,
    }:
        return status.llm_state != "not_found"
    if command is TrayCommand.LLM_INSTALL_PRIMARY:
        return status.llm_primary_residency == "unavailable"
    if command is TrayCommand.LLM_INSTALL_SECONDARY:
        return (
            status.cognitive_routing_enabled
            and status.llm_secondary_residency == "unavailable"
        )
    if command is TrayCommand.LLM_LOAD_PRIMARY:
        return status.llm_primary_residency == "unloaded"
    if command is TrayCommand.LLM_LOAD_SECONDARY:
        return (
            status.cognitive_routing_enabled
            and status.llm_secondary_residency == "unloaded"
        )
    if command is TrayCommand.RUNTIME_START:
        return status.runtime_state != "running"
    if command in {
        TrayCommand.RUNTIME_STOP,
        TrayCommand.RUNTIME_RESTART,
    }:
        return status.runtime_state == "running"
    return True
