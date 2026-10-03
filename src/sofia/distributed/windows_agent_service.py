"""Windows SCM host for Sofía's pinned mTLS Fleet agent."""
from __future__ import annotations

from pathlib import Path
import sys

from sofia.distributed.agent import RemoteAgentServer
from sofia.distributed.agent_main import configuration_from_file, create_agent_server


SERVICE_NAME = "SofiaAdaLyraFleetAgent"
SERVICE_DISPLAY_NAME = "Sofía Ada Lyra Fleet Agent"
SERVICE_DESCRIPTION = (
    "Pinned mTLS Sofía Fleet agent for authenticated remote capability and "
    "inference requests."
)


if sys.platform == "win32":
    import servicemanager
    import win32service
    import win32serviceutil

    class SofiaFleetAgentWindowsService(
        win32serviceutil.ServiceFramework
    ):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args):
            super().__init__(args)
            self._server: RemoteAgentServer | None = None

        def SvcStop(self):
            self.ReportServiceStatus(
                win32service.SERVICE_STOP_PENDING
            )
            server = self._server
            if server is not None:
                server.close()

        def SvcDoRun(self):
            config_path = win32serviceutil.GetServiceCustomOption(
                self._svc_name_,
                "ConfigPath",
                None,
            )
            if not config_path:
                raise RuntimeError(
                    "Fleet agent service has no ConfigPath"
                )
            config = configuration_from_file(Path(config_path))
            server = create_agent_server(config)
            self._server = server
            try:
                servicemanager.LogInfoMsg(
                    f"{self._svc_name_} listening on "
                    f"{config.listen_host}:{config.listen_port}"
                )
                server.serve_forever()
            except Exception:
                servicemanager.LogErrorMsg(
                    f"{self._svc_name_} terminated with an unhandled error"
                )
                raise
            finally:
                if self._server is server:
                    self._server = None
else:
    class SofiaFleetAgentWindowsService:
        """Non-Windows import placeholder for CI."""


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit(
            "Fleet agent Windows service is only available on Windows"
        )
    win32serviceutil.HandleCommandLine(
        SofiaFleetAgentWindowsService
    )
