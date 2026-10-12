"""Independent Windows SCM host for the Artemis-only Sofia controller.

This is NOT Sofia's cognitive runtime and NOT her Fleet agent. There is no
network listener, database mutation, VM/service control or writer promotion.
"""
from __future__ import annotations

from pathlib import Path
import socket
import sys
from threading import Event

from sofia.ops.artemis_controller import (
    ArtemisControllerConfig,
    ArtemisControllerError,
    controller_run,
)

SERVICE_NAME = "SofiaArtemisController"
SERVICE_DISPLAY_NAME = "Sofía Artemis Independent Controller"
SERVICE_DESCRIPTION = (
    "Artemis-only read-only Hyper-V health controller. "
    "Records independently observed VM metadata, never activates a state writer."
)


if sys.platform == "win32":
    import servicemanager
    import win32service
    import win32serviceutil

    class SofiaArtemisControllerService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args):
            super().__init__(args)
            self._stop = Event()

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self._stop.set()

        def SvcDoRun(self):
            if socket.gethostname().casefold().split(".")[0] != "artemis":
                raise ArtemisControllerError("only Artemis may host controller")
            config_path = win32serviceutil.GetServiceCustomOption(
                self._svc_name_, "ConfigPath", None
            )
            if not config_path:
                raise ArtemisControllerError("controller service ConfigPath missing")
            config = ArtemisControllerConfig.load(Path(config_path))
            try:
                servicemanager.LogInfoMsg(
                    f"{SERVICE_NAME} monitoring independent Hyper-V Sofia VM"
                )
                controller_run(config, stop=self._stop)
            except Exception:
                servicemanager.LogErrorMsg(
                    f"{SERVICE_NAME} stopped: controller host evidence unavailable"
                )
                raise
else:
    class SofiaArtemisControllerService:
        """Importable source contract; cannot be activated outside Windows."""


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("Artemis controller SCM service is Windows-only")
    win32serviceutil.HandleCommandLine(SofiaArtemisControllerService)
