"""B-002 native SCM/systemd effect drivers with simulated OS APIs.

No real services are created here. Disposable installed-host proof is separate.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import os
import shutil
from types import SimpleNamespace

import pytest

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore, install_staged_release,
)
from sofia.platform.ops.platform_installer_native_service import (
    DebianSystemdNativeService, WindowsScmNativeService,
    NativeServiceSpecification, signed_native_service_specification,
)
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.test_ops_platform_installation import SignedReleaseBuilder
from test.test_platform_release_verifier import platform_wheels
from test.test_platform_service_session import provision

pytestmark = pytest.mark.pkg_ops


@pytest.fixture
def native_spec(tmp_path, platform_wheels):
    builder = SignedReleaseBuilder(tmp_path / "builder", platform_wheels)
    staged, manifest, _ = builder.stage(revision=6)
    b1 = PlatformInstallationStore(tmp_path / "b1.db")
    release = tmp_path / "release"
    install_staged_release(staged, release, store=b1, verifier=builder.verifier)
    identity_store, identity, state = provision(tmp_path / "host")
    return signed_native_service_specification(
        destination=release, identity_home=identity_store.home,
        local_state=state, store=b1, verifier=builder.verifier,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
    )


def test_signed_native_spec_is_bound_to_actual_b1_identity_and_binary(native_spec):
    spec = native_spec
    assert spec.manifest_sha256 and len(spec.manifest_sha256) == 64
    assert len(spec.executable_sha256) == 64
    assert spec.executable.is_file() and spec.python_executable.is_file()
    assert spec.command()[0] == str(spec.executable)
    assert spec.command()[-2:] == ("--public-key-sha256", spec.public_key_sha256)
    assert spec.service_name == "aegis-platform.service"


@pytest.mark.skipif(os.name == "nt", reason="POSIX native systemd path semantics")
def test_systemd_register_stop_and_remove_only_exact_new_unit(native_spec, tmp_path, monkeypatch):
    import sofia.platform.ops.platform_installer_native_service as mod
    service = DebianSystemdNativeService(unit_path=tmp_path / "aegis-platform.service")
    monkeypatch.setattr(service, "_require_root", lambda: None)
    monkeypatch.setattr(service, "_require_service_identity", lambda spec: None)
    calls = []

    def systemctl(*args):
        calls.append(args)
        if args[0] == "show":
            if not service.unit_path.exists():
                return "LoadState=not-found\nFragmentPath=\n"
            return ("LoadState=loaded\nFragmentPath=" + str(service.unit_path)
                    + "\nActiveState=active\nSubState=running\nMainPID=2345\n")
        return ""
    monkeypatch.setattr(mod, "_run_systemctl", systemctl)
    registered = service.register(native_spec)
    assert registered["origin"] == "OWNED_CONFIG_VERIFIED"
    assert registered["process_state"] == "RUNNING"
    assert registered["service_health"] == "UNKNOWN"
    assert "User=aegis" in service.unit_path.read_text()
    assert "PrivateTmp=false" in service.unit_path.read_text()
    assert "SOFIA_" not in service.unit_path.read_text()
    removed = service.stop_and_unregister(native_spec)
    assert removed["identity_policy"] == "RETAIN"
    assert not service.unit_path.exists()
    assert ("stop", "aegis-platform.service") in calls
    assert ("disable", "aegis-platform.service") in calls


@pytest.mark.skipif(os.name == "nt", reason="POSIX native systemd path semantics")
def test_systemd_refuses_foreign_existing_unit_without_changing_it(native_spec, tmp_path, monkeypatch):
    import sofia.platform.ops.platform_installer_native_service as mod
    service = DebianSystemdNativeService(unit_path=tmp_path / "aegis-platform.service")
    service.unit_path.write_text("[Service]\nExecStart=/foreign\n")
    before = service.unit_path.read_bytes()
    monkeypatch.setattr(service, "_require_root", lambda: None)
    monkeypatch.setattr(service, "_require_service_identity", lambda spec: None)
    monkeypatch.setattr(mod, "_run_systemctl", lambda *a: "LoadState=loaded\n")
    with pytest.raises(PlatformInstallationDenied, match="adopt"):
        service.register(native_spec)
    assert service.unit_path.read_bytes() == before
    with pytest.raises(PlatformInstallationDenied):
        service.stop_and_unregister(native_spec)
    assert service.unit_path.read_bytes() == before


@pytest.mark.skipif(os.name == "nt", reason="POSIX native systemd path semantics")
def test_systemd_verified_replacement_retains_identity(native_spec, tmp_path, monkeypatch):
    import sofia.platform.ops.platform_installer_native_service as mod
    service = DebianSystemdNativeService(unit_path=tmp_path / "aegis-platform.service")
    monkeypatch.setattr(service, "_require_root", lambda: None)
    monkeypatch.setattr(service, "_require_service_identity", lambda spec: None)
    calls = []

    def ctl(*args):
        calls.append(args)
        if args[0] == "show":
            if service.unit_path.exists():
                return ("LoadState=loaded\nFragmentPath=" + str(service.unit_path)
                        + "\nActiveState=active\nSubState=running\nMainPID=123\n")
            return "LoadState=not-found\n"
        return ""
    monkeypatch.setattr(mod, "_run_systemctl", ctl)
    service.register(native_spec)
    # Simulate a second already signed B1 release at a new immutable location.
    binary = tmp_path / "release-v7" / "assets" / "aegis-platform-service"
    binary.parent.mkdir(parents=True)
    shutil.copyfile(native_spec.executable, binary)
    candidate = replace(native_spec, executable=binary, release_id="signed-v7",
                        revision=7, manifest_sha256="a" * 64)
    receipt = service.replace_verified(native_spec, candidate)
    assert receipt["release_manifest_sha256"] == candidate.manifest_sha256
    assert str(binary) in service.unit_path.read_text()
    assert native_spec.platform_id == candidate.platform_id
    assert ("stop", "aegis-platform.service") in calls
    with pytest.raises(PlatformInstallationDenied, match="identity|Platform UUID"):
        service.replace_verified(candidate, replace(native_spec, platform_id="other-platform"))


class FakeScmError(Exception):
    def __init__(self, winerror):
        super().__init__(winerror)
        self.winerror = winerror


class FakeScm:
    SC_MANAGER_ALL_ACCESS = 1
    SERVICE_ALL_ACCESS = 2
    SERVICE_QUERY_STATUS = 4
    SERVICE_WIN32_OWN_PROCESS = 8
    SERVICE_DEMAND_START = 16
    SERVICE_ERROR_NORMAL = 32
    SERVICE_NO_CHANGE = 0xffffffff
    SERVICE_RUNNING = 4
    SERVICE_STOPPED = 1
    SERVICE_CONTROL_STOP = 1

    def __init__(self):
        self.command = None
        self.state = self.SERVICE_STOPPED
        self.events = []

    def OpenSCManager(self, *args):
        return "manager"

    def OpenService(self, *args):
        if self.command is None:
            raise FakeScmError(1060)
        return "service"

    def CreateService(self, *args):
        assert self.command is None
        assert args[-2] == "NT AUTHORITY\\LocalService"
        self.command = args[7]
        self.events.append("created")
        return "service"

    def StartService(self, *args):
        self.state = self.SERVICE_RUNNING
        self.events.append("started")

    def QueryServiceStatus(self, *args):
        return (0, self.state)

    def QueryServiceConfig(self, *args):
        return (0, 0, 0, self.command, None, 0, None, "LocalService", "Aegis")

    def ControlService(self, *args):
        self.state = self.SERVICE_STOPPED
        self.events.append("stopped")

    def ChangeServiceConfig(self, *args):
        self.command = args[4]
        self.events.append("updated")

    def DeleteService(self, *args):
        self.command = None
        self.events.append("removed")

    def CloseServiceHandle(self, *args):
        pass


def windows_spec(native_spec):
    return replace(native_spec, target=PlatformReleaseTarget.WINDOWS_X86_64)


def test_windows_scm_register_reject_duplicate_and_uninstall(native_spec):
    fake = FakeScm()
    driver = WindowsScmNativeService(service_api=fake, error_type=FakeScmError)
    spec = windows_spec(native_spec)
    registered = driver.register(spec)
    assert registered["process_state"] == "RUNNING"
    assert registered["fully_healthy"] is False
    assert fake.events == ["created", "started"]
    with pytest.raises(PlatformInstallationDenied, match="adoption"):
        driver.register(spec)
    removed = driver.stop_and_unregister(spec)
    assert removed["process_state"] == "REMOVED"
    assert fake.events[-2:] == ["stopped", "removed"]


def test_windows_scm_replace_requires_unchanged_platform_identity(native_spec):
    fake = FakeScm()
    driver = WindowsScmNativeService(service_api=fake, error_type=FakeScmError)
    spec = windows_spec(native_spec)
    driver.register(spec)
    replacement = replace(spec, release_id="signed-v8", revision=8,
                          manifest_sha256="f" * 64)
    result = driver.replace_verified(spec, replacement)
    assert result["process_state"] == "RUNNING"
    assert fake.events[-3:] == ["stopped", "updated", "started"]
    with pytest.raises(PlatformInstallationDenied, match="identity|Platform UUID"):
        driver.replace_verified(replacement, replace(spec, platform_id="forged"))

@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX account lookup")
def test_systemd_refuses_unprovisioned_service_identity_before_unit_write(
        native_spec, tmp_path, monkeypatch):
    import pwd
    import grp
    service = DebianSystemdNativeService(unit_path=tmp_path / "aegis-platform.service")
    monkeypatch.setattr(service, "_require_root", lambda: None)
    monkeypatch.setattr(pwd, "getpwnam", lambda name: (_ for _ in ()).throw(KeyError(name)))
    monkeypatch.setattr(grp, "getgrnam", lambda name: (_ for _ in ()).throw(KeyError(name)))
    with pytest.raises(PlatformInstallationDenied, match="not provisioned"):
        service.register(native_spec)
    assert not service.unit_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="Requires POSIX account lookup")
def test_systemd_refuses_root_or_login_account(native_spec, tmp_path, monkeypatch):
    import pwd
    import grp
    service = DebianSystemdNativeService(unit_path=tmp_path / "aegis-platform.service")
    monkeypatch.setattr(service, "_require_root", lambda: None)
    monkeypatch.setattr(pwd, "getpwnam", lambda name: SimpleNamespace(
        pw_uid=0, pw_gid=0, pw_shell="/bin/bash",
    ))
    monkeypatch.setattr(grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=0))
    with pytest.raises(PlatformInstallationDenied, match="noninteractive"):
        service.register(native_spec)
    assert not service.unit_path.exists()
