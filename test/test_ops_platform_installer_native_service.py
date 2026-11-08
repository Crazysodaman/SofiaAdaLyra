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



@pytest.mark.skipif(os.name == "nt", reason="Debian systemd native service path semantics")
def test_systemd_strict_sandbox_allows_only_verified_platform_state_wal_path(native_spec, tmp_path):
    service = DebianSystemdNativeService(
        unit_path=tmp_path / "aegis-platform.service",
    )
    unit = service._unit(native_spec).decode("ascii")
    assert "ProtectSystem=strict\n" in unit
    assert "ProtectHome=true\n" in unit
    # SQLite WAL, SHM and the canonical process/lease locks need writes
    # in this ONE B1-provisioned, service-owned local-state directory.
    allowed = "ReadWritePaths=" + str(native_spec.local_state.parent)
    assert unit.splitlines().count(allowed) == 1
    assert len([line for line in unit.splitlines()
                if line.startswith("ReadWritePaths=")]) == 1
    assert not any(line in unit for line in (
        "ReadWritePaths=/\n", "ReadWritePaths=/opt\n",
        "ReadWritePaths=/var\n", "ReadWritePaths=/home\n",
    ))
    assert "RuntimeDirectoryMode=0700\n" in unit
    assert "User=aegis\nGroup=aegis\n" in unit


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


@pytest.mark.skipif(os.name == "nt", reason="Debian UID/GID and POSIX file modes")
def test_systemd_refuses_inaccessible_intermediate_python_runtime_directory(
        native_spec, tmp_path, monkeypatch):
    """Owner-readable Python leaf is useless behind a foreign 0700 parent."""
    import pwd
    import grp
    import stat
    from types import SimpleNamespace
    import sofia.platform.ops.platform_installer_native_service as mod

    driver = DebianSystemdNativeService(
        unit_path=tmp_path / "aegis-platform.service",
    )
    monkeypatch.setattr(driver, "_require_root", lambda: None)
    monkeypatch.setattr(mod, "_check_spec", lambda *args: None)
    monkeypatch.setattr(
        pwd, "getpwnam", lambda name: SimpleNamespace(
            pw_uid=40411, pw_gid=40412, pw_shell="/usr/sbin/nologin",
        ),
    )
    monkeypatch.setattr(
        grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=40412),
    )

    release_root = native_spec.executable.parent.parent
    python_parent = native_spec.python_executable.parent.parent
    assert release_root in python_parent.parents
    original_stat = Path.stat

    def synthetic_ownership(path, *, follow_symlinks=True):
        actual = original_stat(path, follow_symlinks=follow_symlinks)
        if (path == release_root or release_root in path.parents
                or path == native_spec.identity_home
                or path == native_spec.local_state):
            is_file = path in (
                native_spec.executable,
                native_spec.python_executable,
                native_spec.local_state,
            )
            return SimpleNamespace(
                st_uid=0 if path == python_parent else 40411,
                st_gid=40412,
                st_mode=(stat.S_IFREG if is_file else stat.S_IFDIR) | 0o700,
            )
        return actual

    monkeypatch.setattr(Path, "stat", synthetic_ownership)
    with pytest.raises(PlatformInstallationDenied, match="wrong service UID"):
        driver.register(native_spec)
    assert not driver.unit_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="Debian UID/GID and POSIX file modes")
def test_systemd_rejects_runtime_parent_without_owner_traverse(
        native_spec, tmp_path, monkeypatch):
    """Signed runtime archive extraction must not publish a nontraversable dir."""
    import pwd
    import grp
    import stat
    from types import SimpleNamespace
    import sofia.platform.ops.platform_installer_native_service as mod

    driver = DebianSystemdNativeService(
        unit_path=tmp_path / "aegis-platform.service",
    )
    monkeypatch.setattr(driver, "_require_root", lambda: None)
    monkeypatch.setattr(mod, "_check_spec", lambda *args: None)
    monkeypatch.setattr(
        pwd, "getpwnam", lambda name: SimpleNamespace(
            pw_uid=40411, pw_gid=40412, pw_shell="/usr/sbin/nologin",
        ),
    )
    monkeypatch.setattr(
        grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=40412),
    )
    release_root = native_spec.executable.parent.parent
    python_parent = native_spec.python_executable.parent.parent
    original_stat = Path.stat

    def synthetic_ownership(path, *, follow_symlinks=True):
        actual = original_stat(path, follow_symlinks=follow_symlinks)
        if (path == release_root or release_root in path.parents
                or path == native_spec.identity_home
                or path == native_spec.local_state):
            is_file = path in (
                native_spec.executable,
                native_spec.python_executable,
                native_spec.local_state,
            )
            mode = (stat.S_IFREG if is_file else stat.S_IFDIR) | 0o700
            if path == python_parent:
                mode = stat.S_IFDIR | 0o600
            return SimpleNamespace(st_uid=40411, st_gid=40412, st_mode=mode)
        return actual

    monkeypatch.setattr(Path, "stat", synthetic_ownership)
    with pytest.raises(PlatformInstallationDenied, match="owner-traversable"):
        driver.register(native_spec)
    assert not driver.unit_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX kernel UID/GID/file-mode assumptions")
@pytest.mark.parametrize("failure", ("wrong-uid", "not-writable"))
def test_systemd_refuses_nonwritable_or_foreign_sqlite_parent(
        native_spec, tmp_path, monkeypatch, failure):
    """Never write a systemd unit when the B1 WAL directory cannot be used."""
    import grp
    import pwd
    import stat
    from types import SimpleNamespace
    import sofia.platform.ops.platform_installer_native_service as mod

    service = DebianSystemdNativeService(
        unit_path=tmp_path / "aegis-platform.service",
    )
    monkeypatch.setattr(service, "_require_root", lambda: None)
    monkeypatch.setattr(mod, "_check_spec", lambda *args: None)
    monkeypatch.setattr(
        pwd, "getpwnam", lambda name: SimpleNamespace(
            pw_uid=40411, pw_gid=40412, pw_shell="/usr/sbin/nologin",
        ),
    )
    monkeypatch.setattr(
        grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=40412),
    )
    release_root = native_spec.executable.parent.parent
    state_directory = native_spec.local_state.parent
    original_stat = Path.stat

    def synthetic_stat(path, *, follow_symlinks=True):
        actual = original_stat(path, follow_symlinks=follow_symlinks)
        if (path == release_root or release_root in path.parents
                or path == native_spec.identity_home
                or path == native_spec.local_state
                or path == state_directory):
            file = path in (
                native_spec.executable, native_spec.python_executable,
                native_spec.local_state,
            )
            owner_uid = 0 if path == state_directory and failure == "wrong-uid" else 40411
            mode = (stat.S_IFREG if file else stat.S_IFDIR) | 0o700
            if path == state_directory and failure == "not-writable":
                mode = stat.S_IFDIR | 0o500
            return SimpleNamespace(st_uid=owner_uid, st_gid=40412, st_mode=mode)
        return actual

    monkeypatch.setattr(Path, "stat", synthetic_stat)
    expected = "wrong service UID" if failure == "wrong-uid" else "owner-writable"
    with pytest.raises(PlatformInstallationDenied, match=expected):
        service.register(native_spec)
    assert not service.unit_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX service principal and ancestry semantics")
@pytest.mark.parametrize("defect", ("none", "foreign-release-parent",
                                      "foreign-state-parent", "foreign-primary-group"))
def test_signed_systemd_preflight_denies_foreign_outer_ancestor_and_primary_gid(
        native_spec, tmp_path, monkeypatch, defect):
    """A signed leaf behind foreign 0700 is not runnable as non-root aegis."""
    import grp
    import pwd
    import stat
    from types import SimpleNamespace
    import sofia.platform.ops.platform_installer_native_service as mod

    driver = DebianSystemdNativeService(unit_path=tmp_path / "aegis-platform.service")
    monkeypatch.setattr(driver, "_require_root", lambda: None)
    monkeypatch.setattr(mod, "_check_spec", lambda *args: None)
    monkeypatch.setattr(
        pwd, "getpwnam", lambda name: SimpleNamespace(
            pw_uid=40411, pw_gid=40412, pw_shell="/usr/sbin/nologin",
        ),
    )
    monkeypatch.setattr(
        grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=40412),
    )
    release_root = native_spec.executable.parent.parent
    # Make the outer state ancestor distinct from the release ancestor:
    # otherwise both defects would silently cover the same temp directory.
    relocated_state_dir = tmp_path / "state-outer" / "service-state"
    relocated_state_dir.mkdir(parents=True)
    relocated_state = relocated_state_dir / "platform.db"
    relocated_state.write_bytes(native_spec.local_state.read_bytes())
    native_spec = replace(native_spec, local_state=relocated_state)
    state_dir = native_spec.local_state.parent
    protected = {release_root, native_spec.identity_home,
                 native_spec.local_state, state_dir}
    for executable in (native_spec.executable, native_spec.python_executable):
        node = executable
        while node != release_root:
            protected.add(node)
            node = node.parent
        protected.add(release_root)
    outer = set()
    for directory in (release_root, state_dir, native_spec.identity_home):
        node = directory.parent
        while True:
            outer.add(node)
            if node == node.parent:
                break
            node = node.parent
    # The selected release ancestor is above the B1 signed tree. It must be
    # traversable without asking the installer to chmod a foreign parent.
    foreign_release = release_root.parent
    foreign_state = state_dir.parent
    original_stat = Path.stat

    def fake_stat(node, *, follow_symlinks=True):
        actual = original_stat(node, follow_symlinks=follow_symlinks)
        if node in protected:
            is_file = node in (
                native_spec.executable, native_spec.python_executable,
                native_spec.local_state,
            )
            wrong_gid = defect == "foreign-primary-group" and node == state_dir
            return SimpleNamespace(
                st_uid=40411,
                st_gid=40413 if wrong_gid else 40412,
                st_mode=(stat.S_IFREG if is_file else stat.S_IFDIR) | 0o700,
            )
        if node in outer:
            foreign = (
                defect == "foreign-release-parent" and node == foreign_release
            ) or (
                defect == "foreign-state-parent" and node == foreign_state
            )
            return SimpleNamespace(
                st_uid=0, st_gid=0,
                st_mode=stat.S_IFDIR | (0o700 if foreign else 0o755),
            )
        return actual

    monkeypatch.setattr(Path, "stat", fake_stat)
    if defect == "none":
        # No caller-provided owner-grant flag. Merely validating existing
        # signed installation permissions cannot register or start anything.
        driver._require_service_identity(native_spec)
    else:
        error = (
            "wrong service primary GID"
            if defect == "foreign-primary-group"
            else "native path ancestor not traversable"
        )
        with pytest.raises(PlatformInstallationDenied, match=error):
            driver._require_service_identity(native_spec)
    assert not driver.unit_path.exists()
