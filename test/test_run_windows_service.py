from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

import sofia.run.windows_service as windows_service
from sofia.run.windows_service import (
    PyWin32Modules,
    SERVICE_NAME,
    WINDOWS_SERVICE_CLASS_STRING,
    configure_windows_service_recovery,
    create_windows_service_class,
)


class FakeServiceFramework:
    statuses = []

    def __init__(self, args) -> None:
        self.args = args

    def ReportServiceStatus(self, status, **kwargs) -> None:
        type(self).statuses.append((status, kwargs))


class FakeWin32Event:
    INFINITE = -1
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 258

    def __init__(self) -> None:
        self.set_calls = 0
        self.wait_calls = 0

    def CreateEvent(self, *_args):
        return object()

    def SetEvent(self, _event):
        self.set_calls += 1

    def WaitForSingleObject(self, _event, timeout):
        self.wait_calls += 1
        return self.WAIT_OBJECT_0


class FakeServiceManager:
    def __init__(self) -> None:
        self.info = []
        self.errors = []

    def LogInfoMsg(self, message):
        self.info.append(message)

    def LogErrorMsg(self, message):
        self.errors.append(message)


class FakeApplication:
    def __init__(self, configuration, *, fail_start=False) -> None:
        self.configuration = configuration
        self.fail_start = fail_start
        self.started = 0
        self.stopped = 0

    def start(self, session_id=None):
        self.started += 1
        if self.fail_start:
            raise RuntimeError("boom")

    def shutdown(self):
        self.stopped += 1




def configuration(tmp_path: Path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    from sofia.run.lifecycle import RunLifecycleStore
    lifecycle = RunLifecycleStore(path)
    lifecycle.begin_start(at=windows_service.datetime.now(windows_service.timezone.utc))
    lifecycle.mark_recovering(at=windows_service.datetime.now(windows_service.timezone.utc))
    lifecycle.mark_ready(at=windows_service.datetime.now(windows_service.timezone.utc))
    return SimpleNamespace(state_path=path)


def modules():
    event = FakeWin32Event()
    service = SimpleNamespace(
        SERVICE_STOP_PENDING=3,
        SERVICE_RUNNING=4,
        SERVICE_STOPPED=1,
    )
    util = SimpleNamespace(ServiceFramework=FakeServiceFramework)
    manager = FakeServiceManager()
    return PyWin32Modules(event, service, util, manager), event, manager


def test_service_class_runs_application_until_stop_signal(tmp_path):
    loaded, event, manager = modules()
    apps = []
    config = configuration(tmp_path)
    Service = create_windows_service_class(
        modules=loaded,
        configuration_factory=lambda: config,
        application_factory=lambda config: apps.append(FakeApplication(config)) or apps[-1],
    )
    Service.statuses = []

    instance = Service(["service"])
    instance.SvcDoRun()

    assert len(apps) == 1
    assert apps[0].started == 1
    assert apps[0].stopped == 1
    assert event.wait_calls == 1
    from sofia.run.health import RunHeartbeatStore
    heartbeat = RunHeartbeatStore(config.state_path).current()
    assert heartbeat is not None
    assert heartbeat.closed_at is not None
    assert any(status == 4 for status, _ in Service.statuses)
    assert Service.statuses[-1][0] == 1
    assert manager.errors == []


def test_service_stop_sets_external_event(tmp_path):
    loaded, event, _manager = modules()
    config = configuration(tmp_path)
    Service = create_windows_service_class(
        modules=loaded,
        configuration_factory=lambda: config,
        application_factory=lambda config: FakeApplication(config),
    )
    Service.statuses = []
    instance = Service(["service"])

    instance.SvcStop()

    assert event.set_calls == 1
    assert Service.statuses[-1][0] == 3


def test_start_failure_reports_nonzero_service_stop(tmp_path):
    loaded, _event, manager = modules()
    config = configuration(tmp_path)
    Service = create_windows_service_class(
        modules=loaded,
        configuration_factory=lambda: config,
        application_factory=lambda config: FakeApplication(config, fail_start=True),
    )
    Service.statuses = []
    instance = Service(["service"])

    with pytest.raises(RuntimeError, match="boom"):
        instance.SvcDoRun()

    assert Service.statuses[-1] == (1, {"win32ExitCode": 1, "svcExitCode": 1})
    assert manager.errors[-1].endswith("RuntimeError")


def test_recovery_configuration_is_explicit_and_bounded():
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    configure_windows_service_recovery(runner=runner)

    assert calls[0][0] == [
        "sc.exe",
        "failure",
        SERVICE_NAME,
        "reset=",
        "86400",
        "actions=",
        "restart/5000/restart/15000/restart/60000",
    ]
    assert calls[1][0] == [
        "sc.exe",
        "failureflag",
        SERVICE_NAME,
        "1",
    ]


def test_recovery_configuration_surfaces_sc_failure():
    def runner(args, **kwargs):
        return SimpleNamespace(returncode=5, stdout="", stderr="Access is denied.")

    with pytest.raises(RuntimeError, match="Access is denied"):
        configure_windows_service_recovery(runner=runner)


def test_import_boundary_reports_missing_pywin32(monkeypatch):
    def missing(_name):
        raise ModuleNotFoundError("missing")

    monkeypatch.setattr(windows_service, "import_module", missing)

    with pytest.raises(RuntimeError, match="pywin32"):
        windows_service.load_pywin32()



def test_service_cli_pins_importable_production_class_string(monkeypatch):
    loaded, _event, _manager = modules()
    calls = []

    def handle(cls, **kwargs):
        calls.append((cls, kwargs))

    loaded.win32serviceutil.HandleCommandLine = handle
    sentinel = object()
    monkeypatch.setattr(windows_service, "load_pywin32", lambda: loaded)
    monkeypatch.setattr(windows_service, "SofiaWindowsService", sentinel)

    assert windows_service.main() == 0
    assert calls == [
        (
            sentinel,
            {"serviceClassString": WINDOWS_SERVICE_CLASS_STRING},
        )
    ]



def test_fenced_lifecycle_refuses_service_start_cleanly(tmp_path):
    loaded, _event, manager = modules()
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    from sofia.run.lifecycle import RunLifecycleStore
    lifecycle = RunLifecycleStore(path)
    lifecycle.mark_fenced(
        at=windows_service.datetime.now(windows_service.timezone.utc),
        detail="operator fence",
        owner_id="canary",
        epoch=1,
    )

    apps = []
    config = SimpleNamespace(state_path=path)
    Service = create_windows_service_class(
        modules=loaded,
        configuration_factory=lambda: config,
        application_factory=lambda config: apps.append(FakeApplication(config)) or apps[-1],
    )
    Service.statuses = []

    instance = Service(["service"])
    instance.SvcDoRun()

    assert apps == []
    assert Service.statuses[-1] == (1, {})
    assert manager.errors == []
    assert any("fenced" in message.lower() for message in manager.info)



def test_fence_asserted_during_start_is_clean_stop(tmp_path):
    loaded, _event, manager = modules()
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    from sofia.run.lifecycle import RunLifecycleStore

    config = SimpleNamespace(state_path=path)

    class FenceDuringStartApplication(FakeApplication):
        def start(self, session_id=None):
            self.started += 1
            RunLifecycleStore(path).mark_fenced(
                at=windows_service.datetime.now(windows_service.timezone.utc),
                detail="operator fence during startup",
                owner_id="canary",
                epoch=1,
            )
            raise RuntimeError("startup interrupted by fence")

    Service = create_windows_service_class(
        modules=loaded,
        configuration_factory=lambda: config,
        application_factory=lambda config: FenceDuringStartApplication(config),
    )
    Service.statuses = []

    instance = Service(["service"])
    instance.SvcDoRun()

    assert Service.statuses[-1] == (1, {})
    assert manager.errors == []
    assert any(
        "became fenced" in message.lower()
        for message in manager.info
    )


def test_cli_start_refuses_fenced_lifecycle_before_scm(monkeypatch, tmp_path, capsys):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    from sofia.run.lifecycle import RunLifecycleStore
    lifecycle = RunLifecycleStore(path)
    lifecycle.mark_fenced(
        at=windows_service.datetime.now(windows_service.timezone.utc),
        detail="operator fence",
        owner_id="canary",
        epoch=1,
    )
    config = SimpleNamespace(state_path=path)

    monkeypatch.setattr(
        windows_service,
        "create_default_configuration",
        lambda: config,
    )
    monkeypatch.setattr(
        windows_service.sys,
        "argv",
        ["windows_service.py", "start"],
    )

    def should_not_load():
        raise AssertionError("pywin32 should not be loaded for fenced CLI start")

    monkeypatch.setattr(windows_service, "load_pywin32", should_not_load)

    assert windows_service.main() == 2
    assert "start refused" in capsys.readouterr().out.lower()
