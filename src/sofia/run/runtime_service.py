"""Windows Service Control Manager host for the canonical Sofía runtime."""
from __future__ import annotations

from pathlib import Path
import sys

from sofia.application.bootstrap import SofiaApplication
from sofia.config import create_production_configuration
from sofia.config.defaults import production_state_path
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

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self):
            state_value = win32serviceutil.GetServiceCustomOption(
                self._svc_name_,
                "StatePath",
                str(production_state_path()),
            )
            configuration = create_production_configuration(
                state_path=Path(state_value),
            )
            application = SofiaApplication(configuration)
            self._application = application
            try:
                application.start()
                servicemanager.LogInfoMsg(
                    f"{self._svc_name_} started against {configuration.state_path}"
                )
                while (
                    win32event.WaitForSingleObject(self._stop_event, 1000)
                    == win32event.WAIT_TIMEOUT
                ):
                    pass
            except Exception:
                servicemanager.LogErrorMsg(
                    f"{self._svc_name_} terminated with an unhandled error"
                )
                raise
            finally:
                try:
                    application.shutdown()
                finally:
                    self._application = None
else:
    class SofiaRuntimeWindowsService:
        """Non-Windows import placeholder; not executable as a service."""


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Windows service host is only available on Windows")
    win32serviceutil.HandleCommandLine(SofiaRuntimeWindowsService)
