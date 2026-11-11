"""SCM/systemd origin observation refuses foreign services and fake health."""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.platform.ops.platform_installer_native_preflight import (
    inspect_debian_systemd_service, inspect_windows_scm_service,
)

pytestmark = pytest.mark.pkg_ops


def _systemd_response(*, load="loaded", fragment="", active="active", result=0):
    output = (
        f"LoadState={load}\nFragmentPath={fragment}\n"
        f"ActiveState={active}\nSubState=running\nMainPID=1234\n"
    )
    return lambda *args, **kwargs: SimpleNamespace(returncode=result, stdout=output)


def test_systemd_native_service_is_not_adopted_from_name_or_status(tmp_path):
    unit = tmp_path / "aegis-platform.service"
    unit.write_text("[Unit]\nDescription=Aegis managed test\n", encoding="utf-8")
    digest = sha256(unit.read_bytes()).hexdigest()
    observed = inspect_debian_systemd_service(
        expected_unit_sha256=digest, unit_path=unit,
        runner=_systemd_response(fragment=str(unit)),
    )
    assert observed.origin == "MATCHES_CONFIG_UNVERIFIED"
    assert observed.process_state == "ACTIVE"
    assert observed.health == "UNKNOWN"
    assert observed.executable_verified is False
    assert observed.to_payload()["authorized"] is False
    assert observed.to_payload()["executed"] is False


@pytest.mark.parametrize("defect", ["foreign-path", "bad-hash", "absent", "ambiguous"])
def test_systemd_refuses_foreign_or_inconsistent_origin(tmp_path, defect):
    unit = tmp_path / "aegis-platform.service"
    if defect != "absent":
        unit.write_text("managed unit")
    digest = sha256(b"managed unit").hexdigest()
    fragment = str(unit)
    load = "loaded"
    runner = None
    if defect == "foreign-path":
        fragment = "/lib/systemd/system/aegis-platform.service"
    if defect == "bad-hash":
        digest = "a" * 64
    if defect == "absent":
        load = "not-found"
    if defect == "ambiguous":
        runner = lambda *a, **k: SimpleNamespace(
            returncode=0, stdout="LoadState=loaded\nLoadState=loaded\n",
        )
    observed = inspect_debian_systemd_service(
        expected_unit_sha256=digest, unit_path=unit,
        runner=runner or _systemd_response(load=load, fragment=fragment),
    )
    assert observed.origin in ("ABSENT", "FOREIGN", "UNKNOWN")
    assert observed.executable_verified is False


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink privileges differ")
def test_systemd_refuses_redirected_unit_even_with_matching_contents(tmp_path):
    actual = tmp_path / "actual.service"
    actual.write_text("matching contents")
    redirect = tmp_path / "aegis-platform.service"
    redirect.symlink_to(actual)
    observed = inspect_debian_systemd_service(
        expected_unit_sha256=sha256(actual.read_bytes()).hexdigest(),
        unit_path=redirect, runner=_systemd_response(fragment=str(redirect)),
    )
    assert observed.origin == "UNKNOWN"


class _WinError(Exception):
    def __init__(self, winerror):
        super().__init__(winerror)
        self.winerror = winerror


class _FakeScm:
    SC_MANAGER_CONNECT = 1
    SERVICE_QUERY_CONFIG = 2
    SERVICE_QUERY_STATUS = 4
    SERVICE_RUNNING = 4
    SERVICE_STOPPED = 1
    SERVICE_WIN32_OWN_PROCESS = 0x10
    SERVICE_AUTO_START = 2
    SERVICE_DEMAND_START = 3

    def __init__(self, command, existing=True):
        self.command = command
        self.existing = existing
        self.closed = []
        self.service_type = self.SERVICE_WIN32_OWN_PROCESS
        self.start_type = self.SERVICE_AUTO_START
        self.account = "LocalService"

    def OpenSCManager(self, *args):
        return "manager"

    def OpenService(self, *args):
        if not self.existing:
            raise _WinError(1060)
        return "service"

    def QueryServiceConfig(self, *args):
        return [self.service_type, self.start_type, 0, self.command,
                None, 0, None, self.account, "Aegis"]

    def QueryServiceStatus(self, *args):
        return [0, self.SERVICE_RUNNING]

    def CloseServiceHandle(self, handle):
        self.closed.append(handle)


@pytest.mark.parametrize("existing,expected,origin", [
    (True, "signed-command", "MATCHES_CONFIG_UNVERIFIED"),
    (True, "foreign-command", "FOREIGN"),
    (False, "signed-command", "ABSENT"),
])
def test_windows_scm_refuses_unowned_service_even_if_running(existing, expected, origin):
    api = _FakeScm("signed-command", existing=existing)
    observed = inspect_windows_scm_service(
        expected_binary_command=expected, win32service_module=api,
        pywintypes_module=SimpleNamespace(error=_WinError),
    )
    assert observed.origin == origin
    assert observed.health == "UNKNOWN"
    assert observed.executable_verified is False
    assert api.closed == (["service", "manager"] if existing else ["manager"])

@pytest.mark.parametrize("attribute, forged", [
    ("service_type", 999),
    ("start_type", _FakeScm.SERVICE_DEMAND_START),
    ("account", "LocalSystem"),
])
def test_windows_preflight_rejects_foreign_service_configuration(attribute, forged):
    api = _FakeScm("signed-command")
    setattr(api, attribute, forged)
    observed = inspect_windows_scm_service(
        expected_binary_command="signed-command", win32service_module=api,
        pywintypes_module=SimpleNamespace(error=_WinError),
    )
    assert observed.origin == "FOREIGN"
    assert observed.health == "UNKNOWN"
    assert observed.to_payload()["authorized"] is False
    assert api.closed == ["service", "manager"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode and hardlink semantics")
def test_debian_preflight_rejects_hardlinked_native_unit(tmp_path):
    unit = tmp_path / "aegis-platform.service"
    unit.write_bytes(b"[Service]\\nExecStart=/safe\\n")
    peer = tmp_path / "unit-copy"
    os.link(unit, peer)
    observed = inspect_debian_systemd_service(
        expected_unit_sha256=sha256(unit.read_bytes()).hexdigest(),
        unit_path=unit, runner=_systemd_response(fragment=str(unit)),
    )
    assert observed.origin == "UNKNOWN"
    assert not observed.executable_verified

