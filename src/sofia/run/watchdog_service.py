"""Windows Service Control Manager host for the independent RUN watchdog."""
from __future__ import annotations

from pathlib import Path
import socket
import sys
from threading import Event

from sofia.config.defaults import production_state_path
from sofia.run.host import RunSupervisorHost
from sofia.run.windows_service_spec import WATCHDOG_SERVICE, RUNTIME_SERVICE


if sys.platform == "win32":
    import servicemanager
    import win32service
    import win32serviceutil

    class SofiaWatchdogWindowsService(win32serviceutil.ServiceFramework):
        _svc_name_ = WATCHDOG_SERVICE.name
        _svc_display_name_ = WATCHDOG_SERVICE.display_name
        _svc_description_ = WATCHDOG_SERVICE.description

        def __init__(self, args):
            super().__init__(args)
            self._stop_event = Event()

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self._stop_event.set()

        def SvcDoRun(self):
            state_value = win32serviceutil.GetServiceCustomOption(
                self._svc_name_,
                "StatePath",
                str(production_state_path()),
            )
            runtime_service = win32serviceutil.GetServiceCustomOption(
                self._svc_name_,
                "RuntimeServiceName",
                RUNTIME_SERVICE.name,
            )
            host = RunSupervisorHost(
                state_path=Path(state_value),
                service_name=runtime_service,
                owner_id=f"run-watchdog:{socket.gethostname()}",
            )
            try:
                servicemanager.LogInfoMsg(
                    f"{self._svc_name_} supervising {runtime_service}"
                )
                host.run(stop_event=self._stop_event)
            except Exception:
                servicemanager.LogErrorMsg(
                    f"{self._svc_name_} terminated with an unhandled error"
                )
                raise
else:
    class SofiaWatchdogWindowsService:
        """Non-Windows import placeholder; not executable as a service."""


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Windows service host is only available on Windows")
    win32serviceutil.HandleCommandLine(SofiaWatchdogWindowsService)
