from pathlib import Path

import pytest

from sofia.distributed import windows_agent_service_admin as admin
from sofia.distributed.windows_agent_service import (
    SERVICE_NAME,
    SofiaFleetAgentWindowsService,
)


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


class FakeUtil:
    def __init__(self, *, existing=False):
        self.existing = existing
        self.installs = []
        self.updates = []
        self.options = {}
        self.statuses = {}

    def InstallService(self, *args, **kwargs):
        if self.existing:
            raise ExistingServiceError("exists")
        self.installs.append((args, kwargs))

    def ChangeServiceConfig(self, *args, **kwargs):
        self.updates.append((args, kwargs))

    def SetServiceCustomOption(self, name, key, value):
        self.options[(name, key)] = value

    def GetServiceCustomOption(self, name, key, default=None):
        return self.options.get((name, key), default)

    def QueryServiceStatus(self, name):
        return (0, self.statuses[name], 0, 0, 0, 0, 0)


def valid_config(tmp_path: Path) -> Path:
    certs = tmp_path / "certs"
    state = tmp_path / "state"
    certs.mkdir()
    state.mkdir()
    for name in ("server.pem", "server-key.pem", "ca.pem"):
        (certs / name).write_text("test", encoding="utf-8")
    config = tmp_path / "agent.json"
    config.write_text(
        """{
          "node_id":"11111111-1111-4111-8111-111111111111",
          "node_name":"test-node",
          "listen_host":"127.0.0.1",
          "listen_port":7443,
          "server_certificate":"certs/server.pem",
          "server_private_key":"certs/server-key.pem",
          "client_ca_file":"certs/ca.pem",
          "expected_client_public_key_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "ledger_path":"state/agent.db"
        }""",
        encoding="utf-8",
    )
    return config


def test_agent_service_module_is_importable_without_windows():
    assert SERVICE_NAME == "SofiaAdaLyraFleetAgent"
    assert SofiaFleetAgentWindowsService is not None


def test_install_binds_exact_config_and_delayed_auto(
    monkeypatch,
    tmp_path,
):
    config = valid_config(tmp_path)
    util = FakeUtil()
    recovery = []
    monkeypatch.setattr(
        admin,
        "_require_windows",
        lambda: (FakeWin32Service, util),
    )
    monkeypatch.setattr(admin, "_configure_recovery", lambda: recovery.append(True))

    admin.install_or_update(config)

    assert len(util.installs) == 1
    args, kwargs = util.installs[0]
    assert args[0] == admin.CLASS_STRING
    assert args[1] == SERVICE_NAME
    assert kwargs["startType"] == FakeWin32Service.SERVICE_AUTO_START
    assert kwargs["delayedstart"] is True
    assert util.options[(SERVICE_NAME, "ConfigPath")] == str(config.resolve())
    assert recovery == [True]


def test_existing_agent_service_updates_in_place(
    monkeypatch,
    tmp_path,
):
    config = valid_config(tmp_path)
    util = FakeUtil(existing=True)
    monkeypatch.setattr(
        admin,
        "_require_windows",
        lambda: (FakeWin32Service, util),
    )
    monkeypatch.setattr(admin, "_configure_recovery", lambda: None)

    admin.install_or_update(config)

    assert len(util.updates) == 1


def test_status_detects_exact_registration(
    monkeypatch,
    tmp_path,
):
    config = valid_config(tmp_path)
    util = FakeUtil()
    util.statuses[SERVICE_NAME] = FakeWin32Service.SERVICE_RUNNING
    util.options[(SERVICE_NAME, "ConfigPath")] = str(config.resolve())
    monkeypatch.setattr(
        admin,
        "_require_windows",
        lambda: (FakeWin32Service, util),
    )
    monkeypatch.setattr(
        admin,
        "_python_class_string",
        lambda: admin.CLASS_STRING,
    )

    result = admin.status(expected_config_path=config)

    assert result.installed is True
    assert result.state == "running"
    assert result.valid is True
