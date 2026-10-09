"""Standalone Windows tray control process for Sofía."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from queue import Empty, Queue
import socket
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

from sofia.config import create_production_configuration
from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.config.model import ModelLifecycleConfiguration
from sofia.cognition.activity import (
    CognitiveActivityState,
    CognitiveModelActivityStore,
)
from sofia.cognition.model_lifecycle import (
    CognitiveModelRole,
    ModelLifecycleManager,
)
from sofia.cognition.matrix import MatrixTraceStore
from sofia.integrations.ollama import OllamaAdapter
from sofia.machine.discovery import create_machine_discovery
from sofia.ops.activity import (
    ActivityMode,
    HostActivityObservation,
    HostActivityStore,
    detect_windows_game,
)
from sofia.ops.capability import OpsToolService
from sofia.system.capability import create_local_system_backend
from sofia.safe.operator_stop import OperatorStopStore
from sofia.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)
from sofia.state.component_schema import verify_production_component_schemas
from sofia.ui.notifications import DesktopNotificationStore
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
from .process_lock import TrayProcessAlreadyRunning, TrayProcessLock
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
    def __init__(self, *, state_path: Path | None = None) -> None:
        self.config = create_production_configuration(state_path=state_path) if state_path is not None else create_production_configuration()
        _ensure_state(self.config.state_path)
        verify_production_component_schemas(self.config.state_path)
        self.settings_store = DesktopControlSettingsStore(self.config.state_path)
        self.settings_store.enforce_canonical_local_chat(
            at=datetime.now(timezone.utc),
        )
        self.activity_store = HostActivityStore(self.config.state_path)
        self.ops = OpsToolService(self.config.state_path)
        self.host_id = _local_host_id()
        self.events: Queue[TrayCommand] = Queue()
        self._chat_process: subprocess.Popen | None = None
        self._settings_process: subprocess.Popen | None = None
        self._last_error: str | None = None
        self._execution_approvals = ExecutionApprovalVerifier(
            self.config.state_path
        )
        self._operator_stop = OperatorStopStore(
            self.config.state_path
        )
        self._notifications = DesktopNotificationStore(
            self.config.state_path
        )
        self._matrix_trace_store = MatrixTraceStore(
            self.config.state_path
        )
        self._cognitive_activity_store = CognitiveModelActivityStore(
            self.config.state_path
        )
        self._service = DesktopServiceController(
            local_host_id=self.host_id,
            approval_verifier=self._execution_approvals,
            remote=None,
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

    def _current_model_selection(self) -> CognitiveModelSelection:
        configuration = create_production_configuration(
            state_path=self.config.state_path,
        )
        return CognitiveModelSelection.from_configuration(configuration)

    def _current_model_lifecycle_policy(
        self,
    ) -> ModelLifecycleConfiguration:
        configuration = create_production_configuration(
            state_path=self.config.state_path,
        )
        return configuration.model_lifecycle

    @staticmethod
    def _current_model_statuses(
        selection: CognitiveModelSelection,
        policy: ModelLifecycleConfiguration,
    ):
        return ModelLifecycleManager(
            selection=selection,
            policy=policy,
            backend=OllamaAdapter(),
        ).statuses()

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
            detail = result.error or "no diagnostic detail"
            raise RuntimeError(
                f"process.inspect {result.kind.value}: {detail}"
            )
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
        selection = self._current_model_selection()
        lifecycle_policy = self._current_model_lifecycle_policy()
        lifecycle_statuses = self._current_model_statuses(
            selection,
            lifecycle_policy,
        )
        lifecycle_by_role = {
            item.role: item.state.value
            for item in lifecycle_statuses
        }
        try:
            matrix_trace = self._matrix_trace_store.latest()
            execution_trace = self._matrix_trace_store.latest_with_execution()
        except Exception:
            matrix_trace = None
            execution_trace = None
        activity_store = getattr(
            self,
            "_cognitive_activity_store",
            None,
        )
        try:
            primary_activity = (
                None
                if activity_store is None
                else activity_store.get("primary")
            )
            secondary_activity = (
                None
                if activity_store is None
                else activity_store.get("secondary")
            )
        except Exception:
            primary_activity = None
            secondary_activity = None
        runtime_state = self._service_state(
            settings.runtime_service_name
        )
        runtime_host = (
            self.host_id if runtime_state == "running" else None
        )
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

        execution = (
            None
            if execution_trace is None
            else execution_trace.cognition_execution
        )
        last_model = None
        last_host = None
        last_route = None
        last_primary_host = None
        last_secondary_host = None
        if execution is not None:
            last_route = execution.actual_route
            for step in execution.successful_steps:
                host = step.host or self.host_id
                if step.role == "primary":
                    last_primary_host = host
                elif step.role == "secondary":
                    last_secondary_host = host
            last_step = execution.last_successful_step
            if last_step is not None:
                last_model = last_step.model
                last_host = last_step.host or self.host_id

        primary_residency = lifecycle_by_role.get(
            CognitiveModelRole.PRIMARY
        )
        secondary_residency = lifecycle_by_role.get(
            CognitiveModelRole.SECONDARY
        )
        if (
            primary_activity is not None
            and primary_activity.model == selection.primary.model
            and primary_activity.state is CognitiveActivityState.BUSY
        ):
            primary_residency = "busy"
        if (
            secondary_activity is not None
            and selection.secondary is not None
            and secondary_activity.model == selection.secondary.model
            and secondary_activity.state is CognitiveActivityState.BUSY
        ):
            secondary_residency = "busy"

        fleet_enabled = bool(
            getattr(
                getattr(
                    getattr(self, "config", None),
                    "fleet_cognition",
                    None,
                ),
                "enabled",
                False,
            )
        )
        local_resident_states = {"ready", "busy"}
        primary_host = None
        if (
            primary_activity is not None
            and primary_activity.state is CognitiveActivityState.BUSY
            and primary_activity.host is not None
        ):
            primary_host = primary_activity.host
        elif (
            primary_residency in local_resident_states
            and llm_state == "running"
            and (
                primary_residency != "busy"
                or not fleet_enabled
            )
        ):
            primary_host = self.host_id

        secondary_host = None
        if (
            secondary_activity is not None
            and secondary_activity.state is CognitiveActivityState.BUSY
            and secondary_activity.host is not None
        ):
            secondary_host = secondary_activity.host
        elif (
            secondary_residency in local_resident_states
            and llm_state == "running"
            and (
                secondary_residency != "busy"
                or not fleet_enabled
            )
        ):
            secondary_host = self.host_id

        matrix_intent = None
        matrix_domains = ()
        matrix_validation = None
        if matrix_trace is not None:
            matrix_intent = matrix_trace.turn.intent.value
            matrix_domains = tuple(
                item.domain.value
                for item in matrix_trace.turn.domains
                if item.relevance.value > 0
            )
            if matrix_trace.response_validation is not None:
                matrix_validation = (
                    matrix_trace.response_validation.disposition.value
                )

        return TrayStatus(
            runtime_host=runtime_host,
            runtime_state=runtime_state,
            llm_host=self.host_id if llm_state == "running" else None,
            llm_state=llm_state,
            llm_model=selection.primary.model,
            game_mode=settings.game_mode,
            fleet_total=len(hosts),
            fleet_healthy=healthy,
            fleet_attention=attention,
            llm_secondary_model=(
                None
                if selection.secondary is None
                else selection.secondary.model
            ),
            cognitive_routing_enabled=selection.routing_enabled,
            llm_primary_residency=primary_residency,
            llm_secondary_residency=secondary_residency,
            cognitive_auto_manage=lifecycle_policy.enabled,
            cognitive_idle_unload_seconds=(
                lifecycle_policy.idle_unload_seconds
            ),
            cognitive_residency_mode=lifecycle_policy.residency_mode,
            llm_primary_host=primary_host,
            llm_secondary_host=secondary_host,
            cognitive_last_route=last_route,
            cognitive_last_model=last_model,
            cognitive_last_host=last_host,
            cognitive_last_primary_host=last_primary_host,
            cognitive_last_secondary_host=last_secondary_host,
            matrix_last_intent=matrix_intent,
            matrix_last_domains=matrix_domains,
            matrix_last_validation=matrix_validation,
        )

    def _spawn_module(self, module: str, *arguments: str) -> subprocess.Popen:
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
            (str(executable), "-m", module, "--state-path", str(self.config.state_path.resolve()), *arguments),
            cwd=str(Path(__file__).resolve().parents[3]),
            creationflags=creationflags,
            close_fds=True,
        )

    def _open_chat(self) -> None:
        if self._chat_process is None or self._chat_process.poll() is not None:
            self._chat_process = self._spawn_module("sofia.ui")

    def _open_settings(self, section: str = "General") -> None:
        if self._settings_process is None or self._settings_process.poll() is not None:
            self._settings_process = self._spawn_module("sofia.ui.settings_window", "--section", section)
        else:
            self.settings_store.request_settings_section(section)

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

    def _execute_approved_local_service_action(
        self,
        target: ServiceTarget,
        action: ServiceAction,
        *,
        llm_model: str | None = None,
        llm_keep_alive: str | None = None,
    ) -> None:
        model_kwargs = {"llm_model": llm_model}
        if llm_keep_alive is not None:
            model_kwargs["llm_keep_alive"] = llm_keep_alive
        capability, parameters = self._service.approval_spec(
            target,
            action,
            **model_kwargs,
        )
        now = datetime.now(timezone.utc)
        approval = ExecutionApproval(
            approval_id=str(uuid4()),
            capability=capability,
            request_fingerprint=execution_fingerprint(
                capability,
                parameters,
            ),
            approved_by="Sparks",
            approved_at=now,
            expires_at=now + timedelta(seconds=60),
        )
        self._execution_approvals.record(approval)
        execute_kwargs = {
            "approval_id": approval.approval_id,
            "llm_model": llm_model,
        }
        if llm_keep_alive is not None:
            execute_kwargs["llm_keep_alive"] = llm_keep_alive
        self._service.execute(
            target,
            action,
            **execute_kwargs,
        )

    def _service_action(
        self,
        kind: ServiceKind,
        action: ServiceAction,
        *,
        model_role: CognitiveModelRole | None = None,
    ) -> None:
        if self._operator_stop.current().active:
            raise PermissionError("operator stop is active")
        settings = self.settings_store.load()
        service_name = (
            settings.llm_service_name
            if kind is ServiceKind.LLM_ENGINE
            else settings.runtime_service_name
        )
        target = ServiceTarget(kind, self.host_id, service_name)

        if action is ServiceAction.INSTALL_MODEL:
            if model_role is None:
                raise ValueError("model role required for install")
            selection = self._current_model_selection()
            provider = (
                selection.primary
                if model_role is CognitiveModelRole.PRIMARY
                else selection.secondary
            )
            if provider is None:
                raise ValueError(
                    f"{model_role.value} model is not configured"
                )
            self._execute_approved_local_service_action(
                target,
                action,
                llm_model=provider.model,
            )
            return

        if action is ServiceAction.LOAD_MODEL:
            if model_role is None:
                raise ValueError("model role required for load")
            selection = self._current_model_selection()
            policy = self._current_model_lifecycle_policy()
            provider = (
                selection.primary
                if model_role is CognitiveModelRole.PRIMARY
                else selection.secondary
            )
            if provider is None:
                raise ValueError(
                    f"{model_role.value} model is not configured"
                )
            self._execute_approved_local_service_action(
                target,
                action,
                llm_model=provider.model,
                llm_keep_alive=policy.keep_alive,
            )
            return

        if action is ServiceAction.UNLOAD_MODEL:
            selection = self._current_model_selection()
            for model_name in selection.model_names:
                self._execute_approved_local_service_action(
                    target,
                    action,
                    llm_model=model_name,
                )
            return

        self._execute_approved_local_service_action(
            target,
            action,
        )

    def handle(self, command: TrayCommand) -> bool:
        try:
            if command is TrayCommand.OPEN_CHAT:
                self._open_chat()
            elif command is TrayCommand.OPEN_FLEET:
                self._open_settings("Fleet")
            elif command is TrayCommand.OPEN_SETTINGS:
                self._open_settings()
            elif command is TrayCommand.OPEN_WARDROBE:
                self._open_settings("Wardrobe")
            elif command is TrayCommand.OPEN_MOOD:
                self._open_settings("Mood & Emotion")
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
            elif command is TrayCommand.LLM_INSTALL_PRIMARY:
                self._service_action(
                    ServiceKind.LLM_ENGINE,
                    ServiceAction.INSTALL_MODEL,
                    model_role=CognitiveModelRole.PRIMARY,
                )
            elif command is TrayCommand.LLM_INSTALL_SECONDARY:
                self._service_action(
                    ServiceKind.LLM_ENGINE,
                    ServiceAction.INSTALL_MODEL,
                    model_role=CognitiveModelRole.SECONDARY,
                )
            elif command is TrayCommand.LLM_LOAD_PRIMARY:
                self._service_action(
                    ServiceKind.LLM_ENGINE,
                    ServiceAction.LOAD_MODEL,
                    model_role=CognitiveModelRole.PRIMARY,
                )
            elif command is TrayCommand.LLM_LOAD_SECONDARY:
                self._service_action(
                    ServiceKind.LLM_ENGINE,
                    ServiceAction.LOAD_MODEL,
                    model_role=CognitiveModelRole.SECONDARY,
                )
            elif command is TrayCommand.LLM_UNLOAD_MODEL:
                self._service_action(ServiceKind.LLM_ENGINE, ServiceAction.UNLOAD_MODEL)
            elif command is TrayCommand.RUNTIME_START:
                self._service_action(ServiceKind.SOFIA_RUNTIME, ServiceAction.START)
            elif command is TrayCommand.RUNTIME_STOP:
                self._service_action(ServiceKind.SOFIA_RUNTIME, ServiceAction.STOP)
            elif command is TrayCommand.RUNTIME_RESTART:
                self._service_action(ServiceKind.SOFIA_RUNTIME, ServiceAction.RESTART)
            elif command is TrayCommand.DIAGNOSTICS:
                self._open_settings("Advanced")
            elif command is TrayCommand.EXIT_UI:
                return False
            self._last_error = None
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
        return True

    def run(self) -> int:
        self.settings_store.consume_tray_exit()  # Retire requests addressed to a previous tray process.
        next_observation = time.monotonic() + 30
        try:
            self._observe_activity()
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
        self.tray.start()
        try:
            running = True
            while running:
                if self.settings_store.consume_tray_exit():
                    break
                try:
                    command = self.events.get(timeout=1)
                except Empty:
                    notification = self._notifications.claim_next(
                        now=datetime.now(timezone.utc)
                    )
                    if notification is not None:
                        try:
                            self.tray.notify(
                                title=notification.title,
                                content=notification.content,
                            )
                            self._notifications.mark_displayed(
                                notification.notification_id,
                                now=datetime.now(timezone.utc),
                            )
                        except Exception as exc:
                            self._last_error = (
                                f"{type(exc).__name__}: {exc}"
                            )
                    if time.monotonic() < next_observation:
                        continue
                    next_observation = time.monotonic() + 30
                    try:
                        self._observe_activity()
                    except Exception as exc:
                        self._last_error = f"{type(exc).__name__}: {exc}"
                    continue
                running = self.handle(command)
        finally:
            self.tray.stop()
        return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Sofía tray")
    parser.add_argument("--state-path", type=Path)
    args = parser.parse_args(argv)
    application = TrayAgentApplication(state_path=args.state_path)
    try:
        with TrayProcessLock(application.config.state_path):
            return application.run()
    except TrayProcessAlreadyRunning:
        print("Sofía tray agent is already running.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
