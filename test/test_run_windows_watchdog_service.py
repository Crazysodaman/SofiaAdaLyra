from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

from sofia.run.watchdog import (
    HostServiceObservation,
    HostServiceState,
    WatchdogResult,
)
from sofia.run.windows_service import PyWin32Modules
import sofia.run.windows_watchdog_service as windows_watchdog_service
from sofia.run.windows_watchdog_service import (
    WATCHDOG_SERVICE_NAME,
    WINDOWS_WATCHDOG_SERVICE_CLASS_STRING,
    WindowsScmServiceController,
    create_windows_watchdog_service_class,
)


TARGET = "SofiaAdaLyra"


class FakeServiceFramework:
    statuses = []

    def __init__(self, args) -> None:
        self.args = args

    def ReportServiceStatus(self, status, **kwargs) -> None:
        type(self).statuses.append((status, kwargs))


class FakeEvent:
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 258

    def __init__(self, results=None) -> None:
        self.results = list(results or [self.WAIT_OBJECT_0])
        self.set_calls = 0
        self.wait_calls = 0

    def CreateEvent(self, *_args):
        return object()

    def SetEvent(self, _event):
        self.set_calls += 1

    def WaitForSingleObject(self, _event, _timeout):
        self.wait_calls += 1
        return self.results.pop(0)


class FakeManager:
    def __init__(self) -> None:
        self.info = []
        self.errors = []

    def LogInfoMsg(self, message):
        self.info.append(message)

    def LogErrorMsg(self, message):
        self.errors.append(message)


class FakeUtil:
    ServiceFramework = FakeServiceFramework

    def __init__(self, state_code) -> None:
        self.state_code = state_code
        self.starts = []
        self.restarts = []
        self.stops = []

    def QueryServiceStatus(self, name):
        return (0, self.state_code, 0, 0, 0, 0, 0)

    def StartService(self, name):
        self.starts.append(name)

    def RestartService(self, name):
        self.restarts.append(name)

    def StopService(self, name):
        self.stops.append(name)


def modules(*, state_code=4, wait_results=None):
    event = FakeEvent(wait_results)
    service = SimpleNamespace(
        SERVICE_STOPPED=1,
        SERVICE_START_PENDING=2,
        SERVICE_STOP_PENDING=3,
        SERVICE_RUNNING=4,
    )
    util = FakeUtil(state_code)
    manager = FakeManager()
    return PyWin32Modules(event, service, util, manager), event, util, manager


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1, HostServiceState.STOPPED),
        (2, HostServiceState.START_PENDING),
        (3, HostServiceState.STOP_PENDING),
        (4, HostServiceState.RUNNING),
        (99, HostServiceState.UNKNOWN),
    ],
)
def test_scm_controller_maps_service_states(code, expected):
    loaded, _event, _util, _manager = modules(state_code=code)
    controller = WindowsScmServiceController(
        service_name=TARGET,
        modules=loaded,
    )

    assert controller.observe().state is expected


def test_scm_controller_uses_exact_target_service():
    loaded, _event, util, _manager = modules()
    controller = WindowsScmServiceController(
        service_name=TARGET,
        modules=loaded,
    )

    controller.start()
    controller.restart()
    controller.stop()

    assert util.starts == [TARGET]
    assert util.restarts == [TARGET]
    assert util.stops == [TARGET]


def test_scm_query_failure_becomes_unknown_state():
    loaded, _event, util, _manager = modules()

    def broken(_name):
        raise RuntimeError("SCM unavailable")

    util.QueryServiceStatus = broken
    controller = WindowsScmServiceController(
        service_name=TARGET,
        modules=loaded,
    )

    observation = controller.observe()

    assert observation.state is HostServiceState.UNKNOWN
    assert "RuntimeError" in observation.detail


def configuration(tmp_path: Path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    return SimpleNamespace(state_path=path)


class FakeWatchdog:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.calls = []

    def reconcile(self, *, now, desired_running):
        self.calls.append((now, desired_running))
        health = SimpleNamespace(state=SimpleNamespace(value="healthy"))
        return WatchdogResult(
            action="healthy",
            service=HostServiceObservation(HostServiceState.RUNNING),
            health=health,
        )


def test_watchdog_service_reconciles_outside_sofia_application(tmp_path):
    loaded, event, _util, manager = modules(
        wait_results=[FakeEvent.WAIT_TIMEOUT, FakeEvent.WAIT_OBJECT_0]
    )
    config = configuration(tmp_path)
    built = []

    def factory(**kwargs):
        instance = FakeWatchdog(**kwargs)
        built.append(instance)
        return instance

    Service = create_windows_watchdog_service_class(
        modules=loaded,
        configuration_factory=lambda: config,
        watchdog_factory=factory,
    )
    Service.statuses = []
    instance = Service(["service"])

    instance.SvcDoRun()

    assert len(built) == 1
    assert len(built[0].calls) == 1
    assert built[0].calls[0][1] is True
    assert event.wait_calls == 2
    assert any(status == 4 for status, _ in Service.statuses)
    assert Service.statuses[-1][0] == 1
    assert manager.errors == []


def test_stopping_watchdog_does_not_stop_target_service(tmp_path):
    loaded, event, util, _manager = modules()
    config = configuration(tmp_path)
    Service = create_windows_watchdog_service_class(
        modules=loaded,
        configuration_factory=lambda: config,
        watchdog_factory=lambda **kwargs: FakeWatchdog(**kwargs),
    )
    Service.statuses = []
    instance = Service(["service"])

    instance.SvcStop()

    assert event.set_calls == 1
    assert util.stops == []
    assert Service.statuses[-1][0] == 3


def test_watchdog_failure_reports_nonzero_service_stop(tmp_path):
    loaded, _event, _util, manager = modules(
        wait_results=[FakeEvent.WAIT_TIMEOUT]
    )
    config = configuration(tmp_path)

    class BrokenWatchdog(FakeWatchdog):
        def reconcile(self, *, now, desired_running):
            raise RuntimeError("watchdog tick failed")

    Service = create_windows_watchdog_service_class(
        modules=loaded,
        configuration_factory=lambda: config,
        watchdog_factory=lambda **kwargs: BrokenWatchdog(**kwargs),
    )
    Service.statuses = []
    instance = Service(["service"])

    with pytest.raises(RuntimeError, match="watchdog tick failed"):
        instance.SvcDoRun()

    assert Service.statuses[-1] == (
        1,
        {"win32ExitCode": 1, "svcExitCode": 1},
    )
    assert manager.errors[-1].endswith("RuntimeError")


def test_watchdog_service_identity_is_separate_from_runtime_service(tmp_path):
    loaded, _event, _util, _manager = modules()
    Service = create_windows_watchdog_service_class(
        modules=loaded,
        configuration_factory=lambda: configuration(tmp_path),
        watchdog_factory=lambda **kwargs: FakeWatchdog(**kwargs),
    )

    assert Service._svc_name_ == WATCHDOG_SERVICE_NAME
    assert Service._svc_name_ != TARGET



def test_watchdog_cli_pins_importable_production_class_string(monkeypatch):
    loaded, _event, _util, _manager = modules()
    calls = []

    def handle(cls, **kwargs):
        calls.append((cls, kwargs))

    loaded.win32serviceutil.HandleCommandLine = handle
    sentinel = object()
    monkeypatch.setattr(
        windows_watchdog_service,
        "load_pywin32",
        lambda: loaded,
    )
    monkeypatch.setattr(
        windows_watchdog_service,
        "SofiaWindowsWatchdogService",
        sentinel,
    )

    assert windows_watchdog_service.main() == 0
    assert calls == [
        (
            sentinel,
            {
                "serviceClassString":
                WINDOWS_WATCHDOG_SERVICE_CLASS_STRING
            },
        )
    ]
