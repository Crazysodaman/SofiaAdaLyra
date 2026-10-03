"""Windows Service Control Manager host for the canonical Sofía runtime."""
from __future__ import annotations

from pathlib import Path
import sys

from sofia.application.bootstrap import SofiaApplication
from sofia.config import create_production_configuration
from sofia.config.defaults import production_state_path
from sofia.run.active_release import (
    ActiveReleaseResolver,
    ReleaseEnvironmentManager,
)
from sofia.run.release_process import ReleaseChildProcess
from sofia.run.windows_service_spec import RUNTIME_SERVICE


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
            self._application: SofiaApplication | None = None
            self._release_child: ReleaseChildProcess | None = None

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

        def _run_active_release(self, state_path: Path) -> bool:
            release_root = state_path.parent / "release-runtime"
            active = ActiveReleaseResolver(
                state_path=state_path,
                release_root=release_root,
            ).resolve()
            if active is None:
                return False

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
                child.start()
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
            finally:
                try:
                    child.stop()
                finally:
                    self._release_child = None
            return True

        def _run_bootstrap_runtime(self, state_path: Path) -> None:
            configuration = create_production_configuration(
                state_path=state_path,
            )
            application = SofiaApplication(configuration)
            self._application = application
            try:
                application.start()
                servicemanager.LogInfoMsg(
                    f"{self._svc_name_} started bootstrap runtime against "
                    f"{configuration.state_path}"
                )
                while (
                    win32event.WaitForSingleObject(
                        self._stop_event,
                        1000,
                    )
                    == win32event.WAIT_TIMEOUT
                ):
                    pass
            finally:
                try:
                    application.shutdown()
                finally:
                    self._application = None

        def SvcDoRun(self):
            state_path = self._state_path()
            try:
                if not self._run_active_release(state_path):
                    self._run_bootstrap_runtime(state_path)
            except Exception:
                servicemanager.LogErrorMsg(
                    f"{self._svc_name_} terminated with an unhandled error"
                )
                raise
else:
    class SofiaRuntimeWindowsService:
        """Non-Windows import placeholder; not executable as a service."""


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Windows service host is only available on Windows")
    win32serviceutil.HandleCommandLine(SofiaRuntimeWindowsService)
