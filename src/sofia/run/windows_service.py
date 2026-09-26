"""Native Windows Service Control Manager host for Sofía.

Importing this module does not load pywin32, install a service, alter service
configuration, or start Sofía. pywin32 is loaded only when a caller explicitly
creates/runs the Windows service boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
import subprocess
from typing import Callable, Protocol, Sequence

from sofia.application import SofiaApplication
from sofia.config import SofiaConfiguration, create_default_configuration


SERVICE_NAME = "SofiaAdaLyra"
SERVICE_DISPLAY_NAME = "Sofía Ada Lyra"
SERVICE_DESCRIPTION = (
    "Persistent supervised host service for the Sofía Ada Lyra runtime."
)


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
            application = application_factory(configuration_factory())
            self._application = application
            try:
                application.start()
                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                servicemanager.LogInfoMsg(
                    f"{SERVICE_DISPLAY_NAME} entered RUNNING state."
                )
                win32event.WaitForSingleObject(
                    self._stop_event,
                    win32event.INFINITE,
                )
                application.shutdown()
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
    service_class = create_windows_service_class(modules=modules)
    modules.win32serviceutil.HandleCommandLine(service_class)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
