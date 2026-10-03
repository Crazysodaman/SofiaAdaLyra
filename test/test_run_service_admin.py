from pathlib import Path

import pytest

from sofia.run import service_admin
from sofia.run.runtime_service import SofiaRuntimeWindowsService
from sofia.run.watchdog_service import SofiaWatchdogWindowsService
from sofia.run.windows_service_spec import RUNTIME_SERVICE, WATCHDOG_SERVICE


class ExistingServiceError(RuntimeError):
    winerror = 1073


class FakeWin32Service:
    SERVICE_AUTO_START = 2
    SERVICE_STOPPED = 1
    SERVICE_START_PENDING = 2
    SERVICE_STOP_PENDING = 3
    SERVICE_RUNNING = 4
    SERVICE_CONTINUE_PENDING = 5
    SERVICE_PAUSE_PENDING = 6
    SERVICE_PAUSED = 7


class FakeServiceUtil:
    def __init__(self, *, existing=False):
        self.existing = existing
        self.installs = []
        self.updates = []
        self.options = {}
        self.statuses = {}
        self.removed = []
        self.stopped = []

    def InstallService(self, *args, **kwargs):
        if self.existing:
            raise ExistingServiceError("already exists")
        self.installs.append((args, kwargs))

    def ChangeServiceConfig(self, *args, **kwargs):
        self.updates.append((args, kwargs))

    def SetServiceCustomOption(self, name, key, value):
        self.options[(name, key)] = value

    def GetServiceCustomOption(self, name, key, default=None):
        return self.options.get((name, key), default)

    def QueryServiceStatus(self, name):
        if name not in self.statuses:
            exc = RuntimeError("missing")
            exc.winerror = 1060
            raise exc
        return (0, self.statuses[name], 0, 0, 0, 0, 0)

    def StopService(self, name):
        self.stopped.append(name)

    def RemoveService(self, name):
        self.removed.append(name)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    path.write_bytes(b"sqlite-placeholder")
    return path


def test_install_service_binds_canonical_state_and_recovery(
    monkeypatch,
    state,
):
    util = FakeServiceUtil()
    recovery = []
    monkeypatch.setattr(
        service_admin,
        "_require_windows",
        lambda: (FakeWin32Service, util),
    )
    monkeypatch.setattr(
        service_admin,
        "_configure_recovery",
        recovery.append,
    )

    service_admin.install_or_update_service(
        RUNTIME_SERVICE,
        state_path=state,
    )

    assert len(util.installs) == 1
    args, kwargs = util.installs[0]
    assert args[:3] == (
        RUNTIME_SERVICE.class_string,
        RUNTIME_SERVICE.name,
        RUNTIME_SERVICE.display_name,
    )
    assert kwargs["startType"] == FakeWin32Service.SERVICE_AUTO_START
    assert kwargs["delayedstart"] is True
    assert util.options[
        (RUNTIME_SERVICE.name, "StatePath")
    ] == str(state.resolve())
    assert recovery == [RUNTIME_SERVICE.name]


def test_existing_service_is_updated_in_place(
    monkeypatch,
    state,
):
    util = FakeServiceUtil(existing=True)
    monkeypatch.setattr(
        service_admin,
        "_require_windows",
        lambda: (FakeWin32Service, util),
    )
    monkeypatch.setattr(
        service_admin,
        "_configure_recovery",
        lambda _name: None,
    )

    service_admin.install_or_update_service(
        WATCHDOG_SERVICE,
        state_path=state,
        runtime_service_name=RUNTIME_SERVICE.name,
    )

    assert len(util.updates) == 1
    assert util.options[
        (WATCHDOG_SERVICE.name, "RuntimeServiceName")
    ] == RUNTIME_SERVICE.name


def test_service_status_requires_expected_registration(
    monkeypatch,
    state,
):
    util = FakeServiceUtil()
    util.statuses[RUNTIME_SERVICE.name] = FakeWin32Service.SERVICE_RUNNING
    util.options[(RUNTIME_SERVICE.name, "StatePath")] = str(state.resolve())
    monkeypatch.setattr(
        service_admin,
        "_require_windows",
        lambda: (FakeWin32Service, util),
    )
    monkeypatch.setattr(
        service_admin,
        "_python_class_string",
        lambda _name: RUNTIME_SERVICE.class_string,
    )

    result = service_admin.service_status(
        RUNTIME_SERVICE,
        expected_state_path=state,
    )

    assert result.installed is True
    assert result.state == "running"
    assert result.valid is True


def test_service_status_rejects_wrong_state_database(
    monkeypatch,
    state,
    tmp_path,
):
    util = FakeServiceUtil()
    util.statuses[RUNTIME_SERVICE.name] = FakeWin32Service.SERVICE_STOPPED
    util.options[(RUNTIME_SERVICE.name, "StatePath")] = str(
        tmp_path / "wrong.db"
    )
    monkeypatch.setattr(
        service_admin,
        "_require_windows",
        lambda: (FakeWin32Service, util),
    )
    monkeypatch.setattr(
        service_admin,
        "_python_class_string",
        lambda _name: RUNTIME_SERVICE.class_string,
    )

    result = service_admin.service_status(
        RUNTIME_SERVICE,
        expected_state_path=state,
    )

    assert result.valid is False
    assert "StatePath mismatch" in result.detail


def test_non_windows_service_modules_remain_importable_for_ci():
    assert SofiaRuntimeWindowsService is not None
    assert SofiaWatchdogWindowsService is not None
