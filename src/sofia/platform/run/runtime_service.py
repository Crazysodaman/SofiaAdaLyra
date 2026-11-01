"""Windows Service Control Manager host for the canonical Sofía runtime."""
from __future__ import annotations

from pathlib import Path
import os
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version

from sofia.platform.config.defaults import production_state_path
from sofia.platform.run.active_release import (
    ActiveReleaseError,
    ActiveReleaseResolver,
    ReleaseEnvironmentManager,
)
from sofia.platform.run.release_process import ReleaseChildProcess
from sofia.platform.run.windows_service_spec import RUNTIME_SERVICE
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.core.mentor.windows_service_settings import (
    load_custom_service_settings, MentorServiceSettingsError,
)
from sofia.platform.run.update_restart import (
    ActiveReleaseChangeMonitor,
    UpdateRestartAction,
    configured_update_restart_mode,
    queue_update_restart_request,
)


def runtime_start_allowed(state_path: Path) -> bool:
    """Fail closed when durable owner intent requires the runtime offline."""
    if not isinstance(state_path, Path):
        raise TypeError("state_path must be a Path")
    return not OperatorStopStore(state_path).current().active


def runtime_package_identity() -> str:
    """Return a bounded non-path identity suitable for service diagnostics."""
    try:
        installed = version("sofia-ada-lyra")
    except PackageNotFoundError:
        installed = "source-checkout"
    return f"sofia-ada-lyra/{installed}"[:120]


if sys.platform == "win32":
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    class SofiaRuntimeWindowsService(win32serviceutil.ServiceFramework):
        _svc_name_ = RUNTIME_SERVICE.name
        _svc_display_name_ = RUNTIME_SERVICE.display_name
        _svc_description_ = RUNTIME_SERVICE.description

        def __init__(self, args):
            super().__init__(args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._release_child: ReleaseChildProcess | None = None

        def _stop_requested(self) -> bool:
            return (
                win32event.WaitForSingleObject(self._stop_event, 0)
                != win32event.WAIT_TIMEOUT
            )

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)

        def _state_path(self) -> Path:
            state_value = win32serviceutil.GetServiceCustomOption(
                self._svc_name_,
                "StatePath",
                str(production_state_path()),
            )
            return Path(state_value)

        def _run_active_release(self, state_path: Path) -> str:
            release_root = state_path.parent / "release-runtime"
            resolver = ActiveReleaseResolver(
                state_path=state_path,
                release_root=release_root,
            )
            active = resolver.resolve()
            if active is None:
                return "no_release"
            monitor = ActiveReleaseChangeMonitor(active)

            environment = ReleaseEnvironmentManager(
                release_root=release_root,
            ).ensure(active)
            child = ReleaseChildProcess(
                environment=environment,
                state_path=state_path,
                control_root=release_root / "control",
            )
            self._release_child = child
            try:
                if not child.start(should_stop=self._stop_requested):
                    return "stopped"
                servicemanager.LogInfoMsg(
                    f"{self._svc_name_} started active release "
                    f"{active.release_id} manifest={active.manifest_sha256}"
                )
                while (
                    win32event.WaitForSingleObject(
                        self._stop_event,
                        1000,
                    )
                    == win32event.WAIT_TIMEOUT
                ):
                    if not child.running():
                        raise RuntimeError(
                            "active Sofía release child exited unexpectedly"
                        )
                    try:
                        observed = resolver.resolve()
                    except ActiveReleaseError as exc:
                        servicemanager.LogWarningMsg(
                            f"{self._svc_name_} update projection is not "
                            f"ready yet: {exc}"
                        )
                        continue
                    action = monitor.evaluate(
                        observed,
                        mode=configured_update_restart_mode(state_path),
                    )
                    if action is UpdateRestartAction.AUTOMATIC_RESTART:
                        servicemanager.LogInfoMsg(
                            f"{self._svc_name_} detected activated release "
                            f"{observed.release_id}; restarting runtime"
                        )
                        return "restart"
                    if action is UpdateRestartAction.ASK_OWNER:
                        queue_update_restart_request(
                            state_path,
                            observed,
                            now=datetime.now(timezone.utc),
                        )
                        servicemanager.LogInfoMsg(
                            f"{self._svc_name_} asked for restart to activate "
                            f"release {observed.release_id}"
                        )
            finally:
                try:
                    child.stop()
                finally:
                    self._release_child = None
            return "stopped"

        def _run_bootstrap_runtime(self, state_path: Path) -> str:
            resolver = ActiveReleaseResolver(
                state_path=state_path,
                release_root=state_path.parent / "release-runtime",
            )
            monitor = ActiveReleaseChangeMonitor(None)
            child = ReleaseChildProcess(
                environment=None,
                state_path=state_path,
                control_root=state_path.parent / "release-runtime" / "control",
                python_path=Path(sys.executable),
                runtime_label="bootstrap",
            )
            self._release_child = child
            try:
                if not child.start(should_stop=self._stop_requested):
                    return "stopped"
                servicemanager.LogInfoMsg(
                    f"{self._svc_name_} started bootstrap runtime "
                    f"package={runtime_package_identity()}"
                )
                while (
                    win32event.WaitForSingleObject(
                        self._stop_event,
                        1000,
                    )
                    == win32event.WAIT_TIMEOUT
                ):
                    try:
                        observed = resolver.resolve()
                    except ActiveReleaseError as exc:
                        servicemanager.LogWarningMsg(
                            f"{self._svc_name_} update projection is not "
                            f"ready yet: {exc}"
                        )
                        continue
                    action = monitor.evaluate(
                        observed,
                        mode=configured_update_restart_mode(state_path),
                    )
                    if action is UpdateRestartAction.AUTOMATIC_RESTART:
                        servicemanager.LogInfoMsg(
                            f"{self._svc_name_} detected first activated release "
                            f"{observed.release_id}; restarting runtime"
                        )
                        return "restart"
                    if action is UpdateRestartAction.ASK_OWNER:
                        queue_update_restart_request(
                            state_path,
                            observed,
                            now=datetime.now(timezone.utc),
                        )
            finally:
                try:
                    child.stop()
                finally:
                    self._release_child = None
            return "stopped"

        def SvcDoRun(self):
            state_path = self._state_path()
            if not runtime_start_allowed(state_path):
                servicemanager.LogWarningMsg(
                    f"{self._svc_name_} start refused by persisted owner STOP"
                )
                return
            phase = "service_start"
            # Read existing SCM custom options once at startup. The service
            # host (and a separately launched active-release child) receives
            # the same narrowly scoped MENTOR settings via its environment.
            # Invalid optional settings must not disrupt the canonical brain.
            try:
                options = load_custom_service_settings()
                os.environ.update(options.environment())
                if options.enabled:
                    servicemanager.LogInfoMsg(
                        f"{self._svc_name_} optional local MENTOR QA is enabled"
                    )
            except MentorServiceSettingsError:
                os.environ["SOFIA_MENTOR_BEHAVIOR_ENABLED"] = "false"
                os.environ.pop("SOFIA_MENTOR_SOURCE_ROOT", None)
                servicemanager.LogWarningMsg(
                    f"{self._svc_name_} invalid optional MENTOR settings; QA disabled"
                )
            try:
                while True:
                    phase = "active_release"
                    result = self._run_active_release(state_path)
                    if result == "no_release":
                        phase = "bootstrap_runtime"
                        result = self._run_bootstrap_runtime(state_path)
                    if result != "restart":
                        break
            except Exception as exc:
                chain = []
                current = exc
                while current is not None and len(chain) < 6:
                    chain.append(type(current).__name__)
                    current = current.__cause__ or current.__context__
                servicemanager.LogErrorMsg(
                    f"{self._svc_name_} terminated with an unhandled error; "
                    f"startup_phase={phase}; "
                    f"cause_types={' <- '.join(chain)}"
                )
                raise
else:
    class SofiaRuntimeWindowsService:
        """Non-Windows import placeholder; not executable as a service."""


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Windows service host is only available on Windows")
    win32serviceutil.HandleCommandLine(SofiaRuntimeWindowsService)
