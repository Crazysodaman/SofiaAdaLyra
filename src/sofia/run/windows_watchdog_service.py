"""Native Windows service host for the independent PKG-RUN watchdog.

This process is intentionally separate from Sofía's application service. It
reads durable RUN lifecycle/heartbeat evidence and controls the Sofía Windows
service only through Service Control Manager operations.

Importing this module installs, starts, stops, or reconfigures nothing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from sofia.config import SofiaConfiguration, create_default_configuration
from sofia.run.health import RunHeartbeatStore
from sofia.run.lifecycle import RunLifecycleStore
from sofia.run.watchdog import (
    HostServiceController,
    HostServiceObservation,
    HostServiceState,
    IndependentRunWatchdog,
    WatchdogPolicy,
)
from sofia.run.windows_service import (
    PyWin32Modules,
    SERVICE_NAME,
    load_pywin32,
)


WATCHDOG_SERVICE_NAME = "SofiaAdaLyraWatchdog"
WATCHDOG_DISPLAY_NAME = "Sofía Ada Lyra Watchdog"
WATCHDOG_DESCRIPTION = (
    "Independent watchdog for the Sofía Ada Lyra Windows runtime service."
)
WATCHDOG_INTERVAL_MS = 5000


class WindowsScmServiceController(HostServiceController):
    """Narrow SCM adapter used only by the independent watchdog."""

    def __init__(
        self,
        *,
        service_name: str = SERVICE_NAME,
        modules: PyWin32Modules | None = None,
    ) -> None:
        if (
            not isinstance(service_name, str)
            or not service_name.strip()
            or len(service_name.strip()) > 256
        ):
            raise ValueError("service_name must be bounded")
        self.service_name = service_name.strip()
        self.modules = modules or load_pywin32()

    def observe(self) -> HostServiceObservation:
        try:
            status = self.modules.win32serviceutil.QueryServiceStatus(
                self.service_name
            )
        except Exception as exc:
            return HostServiceObservation(
                HostServiceState.UNKNOWN,
                detail=f"SCM query failed: {type(exc).__name__}",
            )

        try:
            state_code = int(status[1])
        except (TypeError, ValueError, IndexError):
            return HostServiceObservation(
                HostServiceState.UNKNOWN,
                detail="SCM returned malformed service status",
            )

        service = self.modules.win32service
        mapping = {
            service.SERVICE_STOPPED: HostServiceState.STOPPED,
            service.SERVICE_START_PENDING: HostServiceState.START_PENDING,
            service.SERVICE_RUNNING: HostServiceState.RUNNING,
            service.SERVICE_STOP_PENDING: HostServiceState.STOP_PENDING,
        }
        state = mapping.get(state_code, HostServiceState.UNKNOWN)
        return HostServiceObservation(
            state,
            detail=f"scm_state={state_code}",
        )

    def start(self) -> None:
        self.modules.win32serviceutil.StartService(self.service_name)

    def restart(self) -> None:
        self.modules.win32serviceutil.RestartService(self.service_name)

    def stop(self) -> None:
        self.modules.win32serviceutil.StopService(self.service_name)


def create_windows_watchdog_service_class(
    *,
    modules: PyWin32Modules | None = None,
    configuration_factory: Callable[[], SofiaConfiguration] = create_default_configuration,
    policy: WatchdogPolicy = WatchdogPolicy(),
    controller_factory: Callable[..., HostServiceController] = WindowsScmServiceController,
    watchdog_factory: Callable[..., IndependentRunWatchdog] = IndependentRunWatchdog,
):
    """Return a pywin32 ServiceFramework class without registering it."""
    if not isinstance(policy, WatchdogPolicy):
        raise TypeError("WatchdogPolicy required")
    loaded = modules or load_pywin32()
    win32event = loaded.win32event
    win32service = loaded.win32service
    win32serviceutil = loaded.win32serviceutil
    servicemanager = loaded.servicemanager

    class SofiaWindowsWatchdogService(win32serviceutil.ServiceFramework):
        _svc_name_ = WATCHDOG_SERVICE_NAME
        _svc_display_name_ = WATCHDOG_DISPLAY_NAME
        _svc_description_ = WATCHDOG_DESCRIPTION

        def __init__(self, args) -> None:
            super().__init__(args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self) -> None:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self) -> None:
            try:
                configuration = configuration_factory()
                lifecycle = RunLifecycleStore(configuration.state_path)
                heartbeat = RunHeartbeatStore(configuration.state_path)
                controller = controller_factory(
                    service_name=SERVICE_NAME,
                    modules=loaded,
                )
                watchdog = watchdog_factory(
                    state_path=configuration.state_path,
                    heartbeat_store=heartbeat,
                    lifecycle_store=lifecycle,
                    controller=controller,
                    policy=policy,
                )

                self.ReportServiceStatus(win32service.SERVICE_RUNNING)
                servicemanager.LogInfoMsg(
                    f"{WATCHDOG_DISPLAY_NAME} entered RUNNING state."
                )

                wait_timeout = getattr(win32event, "WAIT_TIMEOUT", 258)
                wait_stopped = getattr(win32event, "WAIT_OBJECT_0", 0)
                while True:
                    result = win32event.WaitForSingleObject(
                        self._stop_event,
                        WATCHDOG_INTERVAL_MS,
                    )
                    if result == wait_stopped:
                        break
                    if result != wait_timeout:
                        raise RuntimeError(
                            f"unexpected watchdog wait result: {result}"
                        )

                    outcome = watchdog.reconcile(
                        now=datetime.now(timezone.utc),
                        desired_running=True,
                    )
                    if outcome.action in {
                        "restarted",
                        "started",
                        "fenced_stopped",
                        "recovery_blocked",
                        "unknown_service",
                    }:
                        servicemanager.LogInfoMsg(
                            f"{WATCHDOG_DISPLAY_NAME}: "
                            f"{outcome.action}: {outcome.detail}"
                        )

                self.ReportServiceStatus(win32service.SERVICE_STOPPED)
                servicemanager.LogInfoMsg(
                    f"{WATCHDOG_DISPLAY_NAME} stopped cleanly."
                )
            except Exception as exc:
                try:
                    self.ReportServiceStatus(
                        win32service.SERVICE_STOPPED,
                        win32ExitCode=1,
                        svcExitCode=1,
                    )
                finally:
                    servicemanager.LogErrorMsg(
                        f"{WATCHDOG_DISPLAY_NAME} failed: "
                        f"{type(exc).__name__}"
                    )
                raise

    return SofiaWindowsWatchdogService


def main() -> int:
    """Dispatch pywin32's explicit watchdog service CLI."""
    modules = load_pywin32()
    service_class = create_windows_watchdog_service_class(modules=modules)
    modules.win32serviceutil.HandleCommandLine(service_class)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
