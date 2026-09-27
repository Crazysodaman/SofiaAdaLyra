"""Standalone Windows tray control process for Sofía."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import os
from pathlib import Path
from queue import Empty, Queue
import socket
import sqlite3
import subprocess
import sys

from sofia.config import create_default_configuration
from sofia.machine.discovery import create_machine_discovery
from sofia.ops.activity import (
    ActivityMode,
    HostActivityObservation,
    HostActivityStore,
    detect_windows_game,
)
from sofia.ops.capability import OpsToolService
from sofia.system.capability import create_local_system_backend
from sofia.system.model import (
    SystemCapabilityName,
    SystemCapabilityRequest,
    SystemCapabilityResultKind,
)

from .control_center import (
    DesktopControlSettingsStore,
    GameMode,
    ServiceAction,
    ServiceKind,
    ServiceTarget,
    TrayCommand,
    TrayStatus,
)
from .service_control import DesktopServiceController
from .windows_tray import WindowsTrayAgent


def _ensure_state(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with sqlite3.connect(path):
            pass


def _local_host_id() -> str:
    try:
        return create_machine_discovery().discover().identity.machine_id
    except Exception:
        return f"hostname:{socket.gethostname()}"


class TrayAgentApplication:
    def __init__(self) -> None:
        self.config = create_default_configuration()
        _ensure_state(self.config.state_path)
        self.settings_store = DesktopControlSettingsStore(self.config.state_path)
        self.activity_store = HostActivityStore(self.config.state_path)
        self.ops = OpsToolService(self.config.state_path)
        self.host_id = _local_host_id()
        self.events: Queue[TrayCommand] = Queue()
        self._chat_process: subprocess.Popen | None = None
        self._settings_process: subprocess.Popen | None = None
        self._last_error: str | None = None
        self._service = DesktopServiceController(
            local_host_id=self.host_id,
            llm_model=self.config.provider.model,
        )
        self._system_backend = create_local_system_backend()
        by_name = {
            cap.name: cap
            for cap in self._system_backend.supported_capabilities
        }
        self._service_capability = by_name[SystemCapabilityName.SERVICE_INSPECT]
        self._process_capability = by_name[SystemCapabilityName.PROCESS_INSPECT]
        self._known_games = frozenset(
            value.strip().casefold()
            for value in os.environ.get("SOFIA_GAME_EXECUTABLES", "").split(",")
            if value.strip()
        )
        self.tray = WindowsTrayAgent(
            events=self.events,
            status_provider=self.status,
        )

    def _service_state(self, service_name: str) -> str:
        try:
            result = self._system_backend.execute(
                SystemCapabilityRequest(
                    self._service_capability,
                    {"name": service_name, "limit": 1},
                )
            )
            if result.kind is not SystemCapabilityResultKind.SUCCESS:
                return result.kind.value
            services = tuple(result.evidence.get("services", ()))
            if not services:
                return "not_found"
            state = getattr(services[0], "state", None)
            return str(state).lower() if state else "unknown"
        except Exception:
            return "unknown"

    def _observe_activity(self) -> None:
        settings = self.settings_store.load()
        if settings.game_mode is not GameMode.AUTO:
            return
        result = self._system_backend.execute(
            SystemCapabilityRequest(
                self._process_capability,
                {"limit": 2048},
            )
        )
        if result.kind is not SystemCapabilityResultKind.SUCCESS:
            return
        processes = tuple(result.evidence.get("processes", ()))
        gaming, game = detect_windows_game(
            processes,
            known_game_executables=self._known_games,
        )
        self.activity_store.record(
            HostActivityObservation(
                host_id=self.host_id,
                mode=ActivityMode.GAMING if gaming else ActivityMode.NORMAL,
                observed_at=datetime.now(timezone.utc),
                source="windows-process-inspection",
                detail=game,
            )
        )

    def status(self) -> TrayStatus:
        settings = self.settings_store.load()
        runtime_state = self._service_state(settings.runtime_service_name)
        llm_state = self._service_state(settings.llm_service_name)
        hosts = self.ops.fleet()
        healthy = sum(1 for host in hosts if host["lifecycle"] == "healthy")
        attention = sum(
            1
            for host in hosts
            if host["lifecycle"] in {"degraded", "quarantined", "offline"}
        )
        if self._last_error is not None:
            attention += 1
        return TrayStatus(
            runtime_host=self.host_id if runtime_state == "running" else None,
            runtime_state=runtime_state,
            llm_host=self.host_id if llm_state == "running" else None,
            llm_state=llm_state,
            llm_model=self.config.provider.model,
            game_mode=settings.game_mode,
            fleet_total=len(hosts),
            fleet_healthy=healthy,
            fleet_attention=attention,
        )

    @staticmethod
    def _spawn_module(module: str) -> subprocess.Popen:
        executable = Path(sys.executable)
        if sys.platform == "win32":
            pythonw = executable.with_name("pythonw.exe")
            if pythonw.is_file():
                executable = pythonw
        creationflags = 0
        if sys.platform == "win32":
            creationflags = (
                getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
        return subprocess.Popen(
            (str(executable), "-m", module),
            cwd=str(Path(__file__).resolve().parents[3]),
            creationflags=creationflags,
            close_fds=True,
        )

    def _open_chat(self) -> None:
        if self._chat_process is None or self._chat_process.poll() is not None:
            self._chat_process = self._spawn_module("sofia.ui")

    def _open_settings(self) -> None:
        if self._settings_process is None or self._settings_process.poll() is not None:
            self._settings_process = self._spawn_module("sofia.ui.settings_window")

    def _set_game_mode(self, value: GameMode) -> None:
        settings = self.settings_store.load()
        updated = replace(settings, game_mode=value)
        now = datetime.now(timezone.utc)
        self.settings_store.save(updated, at=now)
        override = {
            GameMode.AUTO: ActivityMode.AUTO,
            GameMode.ON: ActivityMode.GAMING,
            GameMode.OFF: ActivityMode.NORMAL,
        }[value]
        self.activity_store.set_override(self.host_id, override, at=now)
        if value is GameMode.AUTO:
            self._observe_activity()

    def _service_action(self, kind: ServiceKind, action: ServiceAction) -> None:
        settings = self.settings_store.load()
        service_name = (
            settings.llm_service_name
            if kind is ServiceKind.LLM_ENGINE
            else settings.runtime_service_name
        )
        self._service.execute(
            ServiceTarget(kind, self.host_id, service_name),
            action,
        )

    def handle(self, command: TrayCommand) -> bool:
        try:
            if command is TrayCommand.OPEN_CHAT:
                self._open_chat()
            elif command in (TrayCommand.OPEN_FLEET, TrayCommand.OPEN_SETTINGS):
                self._open_settings()
            elif command is TrayCommand.GAME_AUTO:
                self._set_game_mode(GameMode.AUTO)
            elif command is TrayCommand.GAME_ON:
                self._set_game_mode(GameMode.ON)
            elif command is TrayCommand.GAME_OFF:
                self._set_game_mode(GameMode.OFF)
            elif command is TrayCommand.LLM_START:
                self._service_action(ServiceKind.LLM_ENGINE, ServiceAction.START)
            elif command is TrayCommand.LLM_STOP:
                self._service_action(ServiceKind.LLM_ENGINE, ServiceAction.STOP)
            elif command is TrayCommand.LLM_RESTART:
                self._service_action(ServiceKind.LLM_ENGINE, ServiceAction.RESTART)
            elif command is TrayCommand.LLM_UNLOAD_MODEL:
                self._service_action(ServiceKind.LLM_ENGINE, ServiceAction.UNLOAD_MODEL)
            elif command is TrayCommand.RUNTIME_START:
                self._service_action(ServiceKind.SOFIA_RUNTIME, ServiceAction.START)
            elif command is TrayCommand.RUNTIME_STOP:
                self._service_action(ServiceKind.SOFIA_RUNTIME, ServiceAction.STOP)
            elif command is TrayCommand.RUNTIME_RESTART:
                self._service_action(ServiceKind.SOFIA_RUNTIME, ServiceAction.RESTART)
            elif command is TrayCommand.DIAGNOSTICS:
                self._open_settings()
            elif command is TrayCommand.EXIT_UI:
                return False
            self._last_error = None
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
        return True

    def run(self) -> int:
        try:
            self._observe_activity()
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
        self.tray.start()
        try:
            running = True
            while running:
                try:
                    command = self.events.get(timeout=30)
                except Empty:
                    try:
                        self._observe_activity()
                    except Exception as exc:
                        self._last_error = f"{type(exc).__name__}: {exc}"
                    continue
                running = self.handle(command)
        finally:
            self.tray.stop()
        return 0


def main() -> int:
    return TrayAgentApplication().run()


if __name__ == "__main__":
    raise SystemExit(main())
