"""Native Windows Service Control Manager host for Sofía.

Importing this module does not load pywin32, install a service, alter service
configuration, or start Sofía. pywin32 is loaded only when a caller explicitly
creates/runs the Windows service boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
import os
from pathlib import Path
import subprocess
from typing import Callable, Protocol, Sequence
from uuid import uuid4

from sofia.application import SofiaApplication
from sofia.config import SofiaConfiguration, create_default_configuration
from sofia.run.health import RunHeartbeatStore
from sofia.run.lifecycle import RunLifecycleStore


SERVICE_NAME = "SofiaAdaLyra"
SERVICE_DISPLAY_NAME = "Sofía Ada Lyra"
SERVICE_DESCRIPTION = (
    "Persistent supervised host service for the Sofía Ada Lyra runtime."
)
HEARTBEAT_INTERVAL_MS = 5000


@dataclass(frozen=True, slots=True)
class PyWin32Modules:
    win32event: object
    win32service: object
    win32serviceutil: object
    servicemanager: object


def load_pywin32() -> PyWin32Modules:
    """Load the Windows-only service dependency at the explicit live boundary."""
    try:
        return PyWin32Modules(
            win32event=import_module("win32event"),
            win32service=import_module("win32service"),
            win32serviceutil=import_module("win32serviceutil"),
            servicemanager=import_module("servicemanager"),
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Windows service hosting requires pywin32; install project "
            "dependencies on the Windows service host."
        ) from exc


class _ApplicationLike(Protocol):
    def start(self, session_id: str | None = None): ...
    def shutdown(self) -> None: ...


def create_windows_service_class(
    *,
    modules: PyWin32Modules | None = None,
    configuration_factory: Callable[[], SofiaConfiguration] = create_default_configuration,
    application_factory: Callable[[SofiaConfiguration], _ApplicationLike] = SofiaApplication,
):
    """Return a pywin32 ServiceFramework class without registering or starting it."""
    loaded = modules or load_pywin32()
    win32event = loaded.win32event
    win32service = loaded.win32service
    win32serviceutil = loaded.win32serviceutil
    servicemanager = loaded.servicemanager

    class SofiaWindowsService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args) -> None:
            super().__init__(args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)
            self._application: _ApplicationLike | None = None

        def SvcStop(self) -> None:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self) -> None:
            configuration = configuration_factory()
            application = application_factory(configuration)
            self._application = application
            heartbeat: RunHeartbeatStore | None = None
            lifecycle: RunLifecycleStore | None = None
            heartbeat_session: str | None = None
            heartbeat_pid = os.getpid()
            try:
                application.start()
                lifecycle = RunLifecycleStore(configuration.state_path)
                heartbeat = RunHeartbeatStore(configuration.state_path)
                heartbeat_session = str(uuid4())
                heartbeat.begin(
                    session_id=heartbeat_session,
                    process_id=heartbeat_pid,
                    at=datetime.now(timezone.utc),
                    lifecycle=lifecycle.current(),
                )
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                servicemanager.LogInfoMsg(
                    f"{SERVICE_DISPLAY_NAME} entered RUNNING state."
                )

                wait_timeout = getattr(win32event, "WAIT_TIMEOUT", 258)
                wait_stopped = getattr(win32event, "WAIT_OBJECT_0", 0)
                while True:
                    result = win32event.WaitForSingleObject(
                        self._stop_event,
                        HEARTBEAT_INTERVAL_MS,
                    )
                    if result == wait_stopped:
                        break
                    if result != wait_timeout:
                        raise RuntimeError(
                            f"unexpected Windows service wait result: {result}"
                        )
                    heartbeat.pulse(
                        session_id=heartbeat_session,
                        process_id=heartbeat_pid,
                        at=datetime.now(timezone.utc),
                        lifecycle=lifecycle.current(),
                    )

                application.shutdown()
                heartbeat.close(
                    session_id=heartbeat_session,
                    process_id=heartbeat_pid,
                    at=datetime.now(timezone.utc),
                    lifecycle=lifecycle.current(),
                )
                self.ReportServiceStatus(win32service.SERVICE_STOPPED)
                servicemanager.LogInfoMsg(
                    f"{SERVICE_DISPLAY_NAME} stopped cleanly."
                )
            except Exception as exc:
                # The application/RUN lifecycle records the underlying failure.
                # Report a nonzero service exit so configured SCM failure actions
                # may restart the service even when the Python host did not crash.
                try:
                    self.ReportServiceStatus(
                        win32service.SERVICE_STOPPED,
                        win32ExitCode=1,
                        svcExitCode=1,
                    )
                finally:
                    servicemanager.LogErrorMsg(
                        f"{SERVICE_DISPLAY_NAME} failed: {type(exc).__name__}"
                    )
                raise
            finally:
                self._application = None

    return SofiaWindowsService


# pythonservice.exe imports this exact module attribute after SCM launch.
# Keep the production class importable while preserving the lazy/fail-clear
# behavior on development hosts where pywin32 is not installed.
try:
    _PRODUCTION_PYWIN32 = load_pywin32()
except RuntimeError:
    SofiaWindowsService = None
else:
    SofiaWindowsService = create_windows_service_class(
        modules=_PRODUCTION_PYWIN32,
    )

WINDOWS_SERVICE_CLASS_STRING = (
    "sofia.run.windows_service.SofiaWindowsService"
)


class _Completed(Protocol):
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[..., _Completed]


def _run_sc(
    args: Sequence[str],
    *,
    runner: Runner = subprocess.run,
) -> None:
    completed = runner(
        ["sc.exe", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "unknown sc.exe failure").strip()
        raise RuntimeError(f"Windows service configuration failed: {message}")


def configure_windows_service_recovery(
    *,
    service_name: str = SERVICE_NAME,
    runner: Runner = subprocess.run,
) -> None:
    """Configure bounded SCM restarts for the already installed service.

    This is an explicit administrative setup action. It is never called during
    normal application startup.
    """
    if (
        not isinstance(service_name, str)
        or not service_name.strip()
        or len(service_name.strip()) > 256
    ):
        raise ValueError("service_name must be bounded")
    name = service_name.strip()
    _run_sc(
        (
            "failure",
            name,
            "reset=",
            "86400",
            "actions=",
            "restart/5000/restart/15000/restart/60000",
        ),
        runner=runner,
    )
    _run_sc(
        ("failureflag", name, "1"),
        runner=runner,
    )


def main() -> int:
    """Dispatch pywin32's explicit install/start/stop/remove service CLI."""
    modules = load_pywin32()
    service_class = SofiaWindowsService
    if service_class is None:
        service_class = create_windows_service_class(modules=modules)
        globals()["SofiaWindowsService"] = service_class
    modules.win32serviceutil.HandleCommandLine(
        service_class,
        serviceClassString=WINDOWS_SERVICE_CLASS_STRING,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
