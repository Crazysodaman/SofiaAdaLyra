"""AG-D011 native service executor primitives for a verified B1 release.

This module is NOT a permission API or an installer CLI. It consumes exact
service paths resolved from the signed installed B1 release, never downloads,
builds, guesses identity or accepts a service name from an untrusted menu.

A high-level Team-A authenticated native transaction (not yet frozen) must
consume fresh SAFE/STOP/revocation before calling this boundary. These are
real native SCM/systemd operations, not shell emulation; direct shell entrypoints
remain fail-closed. No production activation is authorized from this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
import subprocess
import time

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore, verify_installed,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseManifest, PlatformReleaseTarget

_SERVICE_WINDOWS = "AegisPlatform"
_SERVICE_LINUX = "aegis-platform.service"
_SAFE_SYSTEMD_PATH = re.compile(r"/[A-Za-z0-9/_+.@-]+\Z")


@dataclass(frozen=True, slots=True)
class NativeServiceSpecification:
    """Immutable signed-code selection and observed, existing Platform identity."""

    target: PlatformReleaseTarget
    release_id: str
    revision: int
    manifest_sha256: str
    executable: Path
    executable_sha256: str
    python_executable: Path
    identity_home: Path
    local_state: Path
    platform_id: str
    public_key_sha256: str

    @property
    def service_name(self) -> str:
        return _SERVICE_WINDOWS if self.target is PlatformReleaseTarget.WINDOWS_X86_64 else _SERVICE_LINUX

    def command(self) -> tuple[str, ...]:
        args = [
            str(self.executable),
            "--python", str(self.python_executable),
            "--identity-home", str(self.identity_home),
            "--state", str(self.local_state),
            "--platform-id", self.platform_id,
            "--public-key-sha256", self.public_key_sha256,
        ]
        if self.target is PlatformReleaseTarget.WINDOWS_X86_64:
            args.insert(1, "--scm")
        return tuple(args)


def signed_native_service_specification(
    *,
    destination: Path | str,
    identity_home: Path | str,
    local_state: Path | str,
    store: PlatformInstallationStore,
    verifier: PlatformReleaseVerifier,
    expected_target: PlatformReleaseTarget,
) -> NativeServiceSpecification:
    """Only select service code already verified/recorded by canonical B1."""
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("canonical B1 store required")
    if not isinstance(verifier, PlatformReleaseVerifier):
        raise TypeError("configured trusted verifier required")
    if not isinstance(expected_target, PlatformReleaseTarget):
        raise TypeError("typed exact target required")
    root = Path(destination).absolute()
    identity_path = Path(identity_home).absolute()
    state = Path(local_state).absolute()
    for path in (root, identity_path, state):
        assert_no_redirected_components(path, include_leaf=True)
    row = store.receipt_for_destination(root)
    if row is None or row["result"] != "SUCCEEDED":
        raise PlatformInstallationDenied("no canonical successful B1 release receipt")
    verified = verify_installed(root, store=store, verifier=verifier)
    if verified["manifest_sha256"] != row["manifest_sha256"]:
        raise PlatformInstallationDenied("signed release and B1 receipt differ")
    if not state.is_file():
        raise PlatformInstallationDenied("Platform local state must be explicitly provisioned")
    identity = InstallationIdentityStore(identity_path).load()
    manifest_path = root / "release-manifest.json"
    info = manifest_path.stat(follow_symlinks=False)
    if info.st_size > 131072:
        raise PlatformInstallationDenied("release manifest oversized")
    manifest = PlatformReleaseManifest.from_payload(loads_strict_model_json(
        read_artifact_file(manifest_path, info.st_size, include_data=True)[1].decode("utf-8")
    ))
    if manifest.digest != row["manifest_sha256"] or manifest.target != expected_target:
        raise PlatformInstallationDenied("signed native target or manifest mismatch")
    service = next(asset.reference for asset in manifest.assets if asset.kind == "service")
    binary = root / "assets" / service.path
    assert_no_redirected_components(binary, include_leaf=True)
    actual_sha, _ = read_artifact_file(binary, service.size_bytes)
    if actual_sha != service.sha256:
        raise PlatformInstallationDenied("native service bytes differ from signed manifest")
    interpreter = root / "runtime" / "python" / (
        "python.exe" if expected_target is PlatformReleaseTarget.WINDOWS_X86_64
        else "bin/python3.12"
    )
    assert_no_redirected_components(interpreter, include_leaf=True)
    if not interpreter.is_file():
        raise PlatformInstallationDenied("signed release runtime interpreter missing")
    return NativeServiceSpecification(
        expected_target, row["release_id"], row["revision"],
        row["manifest_sha256"], binary, service.sha256, interpreter,
        identity_path, state, identity.identity.canonical_uuid,
        identity.public_key_sha256,
    )


def _check_spec(spec: NativeServiceSpecification, expected: PlatformReleaseTarget) -> None:
    if not isinstance(spec, NativeServiceSpecification) or spec.target is not expected:
        raise PlatformInstallationDenied("native service target mismatch")
    for path in (spec.executable, spec.python_executable, spec.identity_home, spec.local_state):
        assert_no_redirected_components(path, include_leaf=True)
    size = spec.executable.stat(follow_symlinks=False).st_size
    if not 1 <= size <= 64 * 1024**2:
        raise PlatformInstallationDenied("selected native service exceeds signed size bound")
    observed_sha, _ = read_artifact_file(spec.executable, size)
    if observed_sha != spec.executable_sha256:
        raise PlatformInstallationDenied("selected signed native binary changed")
    identity = InstallationIdentityStore(spec.identity_home).load()
    if (identity.identity.canonical_uuid != spec.platform_id or
            identity.public_key_sha256 != spec.public_key_sha256):
        raise PlatformInstallationDenied("immutable Platform UUID or key changed")


def _run_systemctl(*args: str) -> str:
    result = subprocess.run(
        ["systemctl", *args], check=False, capture_output=True,
        text=True, timeout=35,
    )
    if result.returncode != 0:
        raise RuntimeError("native systemd operation failed; reconcile actual host state")
    if len(result.stdout) > 4096:
        raise RuntimeError("unbounded systemd response refused")
    return result.stdout


class DebianSystemdNativeService:
    """Actual native systemd service registration, scoped to canonical name.

    The required service account, file ownership and private local state MUST
    already be provisioned by reviewed host setup. Never create/adopt them here.
    Linux service operator socket permissions remain Team A-owned.
    """

    unit_path = Path("/etc/systemd/system/aegis-platform.service")

    def __init__(self, *, unit_path: Path | None = None):
        self.unit_path = Path(unit_path or self.unit_path).absolute()

    @staticmethod
    def _require_root() -> None:
        if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
            raise PermissionError("native systemd mutation requires reviewed root service executor")
        from sofia.platform.ops.platform_installer_bundle import host_release_target
        if host_release_target() is not PlatformReleaseTarget.DEBIAN12_X86_64:
            raise PlatformInstallationDenied("native Linux installer requires exact Debian12 x86_64")

    @staticmethod
    def _require_service_identity(spec: NativeServiceSpecification) -> None:
        """Refuse startup until exact non-root service user owns protected bytes.

        Ownership provisioning is a separate owner-authorized signed installer
        step and MUST NOT be guessed by a launcher or systemd unit. This gate
        prevents an administrator-owned private B1 tree from being installed
        as an unreadable service under `User=aegis`.
        """
        import grp
        import pwd

        _check_spec(spec, PlatformReleaseTarget.DEBIAN12_X86_64)
        try:
            user = pwd.getpwnam("aegis")
            group = grp.getgrnam("aegis")
        except KeyError as error:
            raise PlatformInstallationDenied(
                "dedicated signed installer service identity is not provisioned"
            ) from error
        if (user.pw_uid == 0 or group.gr_gid == 0
                or user.pw_gid != group.gr_gid
                or user.pw_shell not in ("/usr/sbin/nologin", "/sbin/nologin", "/bin/false")):
            raise PlatformInstallationDenied(
                "service account must be dedicated and noninteractive"
            )
        # Exact B1 asset tree and bundled interpreter must be traversable
        # under the SAME non-root service UID. Checking only the leaf python
        # executable is insufficient: a parent runtime/python directory may
        # still be root-owned 0700, yielding a real ExecStart EACCES.
        release_root = spec.executable.parent.parent
        # ProtectSystem=strict otherwise makes SQLite/WAL/lease writes fail
        # even when B1 code and the executable are correctly owned. The
        # narrow ReadWritePaths below is only safe for an already-provisioned
        # private, service-owned state directory, never an arbitrary parent.
        state_directory = spec.local_state.parent
        paths = {release_root, spec.identity_home, spec.local_state,
                 state_directory}
        for executable in (spec.executable, spec.python_executable):
            path = executable
            while True:
                paths.add(path)
                if path == release_root:
                    break
                if release_root not in path.parents:
                    raise PlatformInstallationDenied(
                        "signed executable escaped the verified B1 release root"
                    )
                path = path.parent
        for node in sorted(paths, key=lambda item: (len(item.parts), str(item))):
            assert_no_redirected_components(node, include_leaf=True)
            details = node.stat(follow_symlinks=False)
            if details.st_uid != user.pw_uid:
                raise PlatformInstallationDenied(
                    "signed code or protected Platform identity has wrong service UID"
                )
            if details.st_gid != group.gr_gid:
                raise PlatformInstallationDenied(
                    "signed code or protected Platform identity has wrong service primary GID"
                )
            if details.st_mode & 0o077:
                raise PlatformInstallationDenied(
                    "service code/private state must not grant group/world access"
                )
            if node in paths and node not in (spec.executable, spec.python_executable, spec.local_state):
                if not stat.S_ISDIR(details.st_mode) or not (details.st_mode & stat.S_IXUSR):
                    raise PlatformInstallationDenied(
                        "signed release parent directory is not owner-traversable"
                    )
                if node == state_directory and not (details.st_mode & stat.S_IWUSR):
                    raise PlatformInstallationDenied(
                        "Platform SQLite state directory must be owner-writable"
                    )
        for node in (spec.executable, spec.python_executable):
            details = node.stat(follow_symlinks=False)
            if not stat.S_ISREG(details.st_mode) or not details.st_mode & stat.S_IXUSR:
                raise PlatformInstallationDenied(
                    "signed native executable and bundled interpreter need owner execute"
                )
        # B1's signed release root may itself be placed under root-owned
        # directories such as /opt/aegis/releases. Those ancestors need not
        # be service-owned, but the actual service UID or its primary GID
        # must be able to traverse every one. A foreign 0700 ancestor is
        # otherwise a deterministic systemd ExecStart EACCES on a clean host.
        # Never auto-chmod/chown these paths: provisioning is owner-governed.
        ancestor_paths = set()
        for protected in (release_root, state_directory, spec.identity_home):
            path = protected.parent
            while True:
                ancestor_paths.add(path)
                if path == path.parent:
                    break
                path = path.parent
        for parent in sorted(ancestor_paths, key=lambda item: (len(item.parts), str(item))):
            assert_no_redirected_components(parent, include_leaf=True)
            info = parent.stat(follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):
                raise PlatformInstallationDenied("native path ancestor is not a directory")
            if info.st_uid == user.pw_uid:
                execute = stat.S_IXUSR
            elif info.st_gid == group.gr_gid:
                execute = stat.S_IXGRP
            else:
                execute = stat.S_IXOTH
            if not info.st_mode & execute:
                raise PlatformInstallationDenied(
                    "native path ancestor not traversable by installed service principal"
                )
        if not spec.identity_home.is_dir() or not spec.local_state.is_file():
            raise PlatformInstallationDenied("protected local state/identity unavailable")

    def _unit(self, spec: NativeServiceSpecification) -> bytes:
        _check_spec(spec, PlatformReleaseTarget.DEBIAN12_X86_64)
        for item in spec.command():
            if _SAFE_SYSTEMD_PATH.fullmatch(item) is None and not re.fullmatch(
                r"[A-Za-z0-9-]{1,96}", item
            ) and not re.fullmatch(r"[0-9a-f]{64}", item):
                # The only other permitted tokens are the fixed option labels.
                raise PlatformInstallationDenied("unsafe systemd command token")
        command = " ".join(spec.command())
        return (
            "[Unit]\nDescription=Aegis Platform (signed Core-free release)\n"
            "After=network.target\n"
            "ConditionPathExists=" + str(spec.local_state) + "\n"
            "ConditionPathIsDirectory=" + str(spec.identity_home) + "\n"
            "[Service]\nType=notify\nNotifyAccess=main\n"
            "User=aegis\nGroup=aegis\n"
            "ExecStart=" + command + "\n"
            "WorkingDirectory=" + str(spec.local_state.parent) + "\n"
            "UMask=0077\nRestart=on-failure\nRestartSec=20\n"
            "TimeoutStartSec=15\nTimeoutStopSec=20\n"
            "KillMode=mixed\nNoNewPrivileges=true\n"
            "PrivateTmp=false\nProtectSystem=strict\nProtectHome=true\n"
            # Scope the only writable filesystem carve-out to the exact
            # B1-provisioned Platform SQLite/WAL/lease parent. This grants no
            # access to foreign or unowned paths: registration separately
            # verifies service UID, private mode and owner-write permission.
            "ReadWritePaths=" + str(spec.local_state.parent) + "\n"
            "RuntimeDirectory=aegis-platform\nRuntimeDirectoryMode=0700\n"
            "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6\n"
            "[Install]\nWantedBy=multi-user.target\n"
        ).encode("ascii")

    def _verify_unit_file(self, expected: bytes) -> None:
        """Inspect only the bounded, original unit inode, never foreign bytes."""
        assert_no_redirected_components(self.unit_path, include_leaf=True)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.unit_path, flags)
        except OSError as error:
            raise PlatformInstallationDenied("native systemd unit unavailable") from error
        try:
            details = os.fstat(fd)
            if (not stat.S_ISREG(details.st_mode) or details.st_nlink != 1
                    or details.st_size != len(expected)):
                raise PlatformInstallationDenied("foreign or changed systemd unit refused")
            with os.fdopen(fd, "rb", closefd=False) as source:
                if source.read(len(expected) + 1) != expected:
                    raise PlatformInstallationDenied("foreign or changed systemd unit refused")
            after = os.fstat(fd)
            # Reading the original descriptor is not enough if another
            # process swapped the unit pathname after open. Pin the on-disk
            # entry to the same inode before returning to any native effect.
            try:
                on_disk = os.lstat(self.unit_path)
            except OSError as error:
                raise PlatformInstallationDenied(
                    "systemd unit disappeared during inspection"
                ) from error
            before_identity = (
                details.st_dev, details.st_ino, details.st_size, details.st_mtime_ns
            )
            if (not stat.S_ISREG(on_disk.st_mode)
                    or before_identity != (
                        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
                    )
                    or before_identity != (
                        on_disk.st_dev, on_disk.st_ino,
                        on_disk.st_size, on_disk.st_mtime_ns
                    )):
                raise PlatformInstallationDenied("systemd unit changed during inspection")
        finally:
            os.close(fd)

    def _loaded(self) -> str:
        lines = _run_systemctl(
            "show", _SERVICE_LINUX, "--property=LoadState,FragmentPath", "--no-pager"
        ).splitlines()
        values = dict(line.split("=", 1) for line in lines if line.count("=") == 1)
        return values.get("LoadState", "UNKNOWN")

    def register(self, spec: NativeServiceSpecification) -> dict[str, object]:
        self._require_root()
        self._require_service_identity(spec)
        data = self._unit(spec)
        assert_no_redirected_components(self.unit_path, include_leaf=True)
        if self.unit_path.exists() or self.unit_path.is_symlink() or self._loaded() != "not-found":
            raise PlatformInstallationDenied("refuse to adopt or replace existing systemd service")
        # O_EXCL prevents replacing a raced systemd unit; no best-effort cleanup
        # on failure since the exact native outcome must first be reconciled.
        fd = os.open(self.unit_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | getattr(os, "O_NOFOLLOW", 0), 0o644)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _run_systemctl("daemon-reload")
        _run_systemctl("start", _SERVICE_LINUX)
        # A successful systemctl start is not proof the child stayed alive.
        # Fail before enabling an immediately dead service at boot.
        self._require_running(self.observe(spec))
        _run_systemctl("enable", _SERVICE_LINUX)
        return self._require_running(self.observe(spec))

    def observe(self, spec: NativeServiceSpecification) -> dict[str, object]:
        _check_spec(spec, PlatformReleaseTarget.DEBIAN12_X86_64)
        data = self._unit(spec)
        assert_no_redirected_components(self.unit_path, include_leaf=True)
        self._verify_unit_file(data)
        output = _run_systemctl(
            "show", _SERVICE_LINUX,
            "--property=LoadState,FragmentPath,ActiveState,SubState,MainPID", "--no-pager"
        )
        values = dict(line.split("=", 1) for line in output.splitlines() if line.count("=") == 1)
        if values.get("FragmentPath") != str(self.unit_path):
            raise PlatformInstallationDenied("foreign systemd unit origin")
        pid = values.get("MainPID")
        running = (values.get("LoadState") == "loaded"
                   and values.get("ActiveState") == "active"
                   and values.get("SubState") == "running"
                   and pid is not None and pid.isdecimal() and int(pid) > 0)
        return dict(schema="aegis.native-service-receipt.v1",
                    service=_SERVICE_LINUX, origin="OWNED_CONFIG_VERIFIED",
                    process_state="RUNNING" if running else "NOT_RUNNING",
                    process_id=int(pid) if running else None,
                    platform_id=spec.platform_id,
                    release_manifest_sha256=spec.manifest_sha256,
                    service_health="UNKNOWN", core_activated=False,
                    fully_healthy=False)

    @staticmethod
    def _require_running(receipt: dict[str, object]) -> dict[str, object]:
        if (receipt.get("process_state") != "RUNNING"
                or type(receipt.get("process_id")) is not int
                or receipt["process_id"] <= 0):
            raise PlatformInstallationDenied(
                "native service not running; reconcile host before retry"
            )
        return receipt

    def restart_verified(self, spec: NativeServiceSpecification) -> dict[str, object]:
        """Repair only a matching signed unit; never rewrite unknown configuration."""
        self._require_root()
        self._require_service_identity(spec)
        self.observe(spec)
        _run_systemctl("restart", _SERVICE_LINUX)
        return self._require_running(self.observe(spec))

    def replace_verified(
        self, previous: NativeServiceSpecification, candidate: NativeServiceSpecification,
    ) -> dict[str, object]:
        """Switch only a known owned unit to another already signed B1 release."""
        self._require_root()
        self._require_service_identity(previous)
        self._require_service_identity(candidate)
        self.observe(previous)
        if (candidate.target is not previous.target
                or candidate.platform_id != previous.platform_id
                or candidate.public_key_sha256 != previous.public_key_sha256
                or candidate.identity_home != previous.identity_home
                or candidate.local_state != previous.local_state):
            raise PlatformInstallationDenied("signed replacement changes protected Platform identity")
        replacement = self._unit(candidate)
        # The original unit must remain intact until the temp file is synced.
        assert_no_redirected_components(self.unit_path, include_leaf=True)
        self._verify_unit_file(self._unit(previous))
        pending = self.unit_path.with_name(self.unit_path.name + ".pending")
        assert_no_redirected_components(pending, include_leaf=True)
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | getattr(os, "O_NOFOLLOW", 0), 0o644)
        with os.fdopen(fd, "wb") as stream:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        # Any failure past this point requires exact-host reconciliation:
        # neither a blind restore nor a second unapproved restart is safe.
        _run_systemctl("stop", _SERVICE_LINUX)
        self._verify_unit_file(self._unit(previous))
        os.replace(pending, self.unit_path)
        _run_systemctl("daemon-reload")
        _run_systemctl("start", _SERVICE_LINUX)
        return self._require_running(self.observe(candidate))

    def stop_and_unregister(self, spec: NativeServiceSpecification) -> dict[str, object]:
        self._require_root()
        self.observe(spec)  # No adopting foreign units, even for removal.
        _run_systemctl("stop", _SERVICE_LINUX)
        _run_systemctl("disable", _SERVICE_LINUX)
        assert_no_redirected_components(self.unit_path, include_leaf=True)
        self._verify_unit_file(self._unit(spec))
        self.unit_path.unlink()
        _run_systemctl("daemon-reload")
        return dict(schema="aegis.native-service-receipt.v1",
                    service=_SERVICE_LINUX, process_state="REMOVED",
                    identity_policy="RETAIN", core_activated=False,
                    service_health="UNKNOWN")


class WindowsScmNativeService:
    """Real SCM register/remove with service identity LocalService, no auto-adoption."""

    def __init__(self, service_api=None, error_type=None):
        self._service_api = service_api
        self._error_type = error_type

    def _api(self):
        if self._service_api is None:
            if os.name != "nt":
                raise PlatformInstallationDenied("Windows SCM unavailable on this host")
            import pywintypes
            import win32service
            self._service_api, self._error_type = win32service, pywintypes.error
        return self._service_api

    @staticmethod
    def _verify_owned_config(api, handle, spec: NativeServiceSpecification) -> None:
        """Refuse adopting a foreign SCM service with a matching binary string.

        The exact signed command is necessary but not sufficient: a service
        with a different account, start policy or service type is not the
        Platform installed by our owner-approved native executor.
        """
        from subprocess import list2cmdline
        config = api.QueryServiceConfig(handle)
        if (len(config) < 8
                or config[0] != api.SERVICE_WIN32_OWN_PROCESS
                or config[1] != api.SERVICE_AUTO_START
                or config[3] != list2cmdline(spec.command())
                or config[7] not in (
                    "NT AUTHORITY\\LocalService", "LocalService",
                )):
            raise PlatformInstallationDenied(
                "SCM service identity, startup mode or signed executable differs"
            )

    def register(self, spec: NativeServiceSpecification) -> dict[str, object]:
        _check_spec(spec, PlatformReleaseTarget.WINDOWS_X86_64)
        api = self._api()
        from subprocess import list2cmdline
        scm = api.OpenSCManager(None, None, api.SC_MANAGER_ALL_ACCESS)
        service = None
        try:
            try:
                existing = api.OpenService(scm, _SERVICE_WINDOWS, api.SERVICE_QUERY_STATUS)
            except self._error_type as error:
                if getattr(error, "winerror", None) != 1060:
                    raise
            else:
                api.CloseServiceHandle(existing)
                raise PlatformInstallationDenied("refuse adoption of existing Windows SCM service")
            command = list2cmdline(spec.command())
            service = api.CreateService(
                scm, _SERVICE_WINDOWS, "Aegis Platform (signed Core-free)",
                api.SERVICE_ALL_ACCESS, api.SERVICE_WIN32_OWN_PROCESS,
                api.SERVICE_AUTO_START, api.SERVICE_ERROR_NORMAL,
                command, None, 0, None, "NT AUTHORITY\\LocalService", None,
            )
            api.StartService(service, None)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                status = api.QueryServiceStatus(service)
                if status[1] == api.SERVICE_RUNNING:
                    return dict(schema="aegis.native-service-receipt.v1",
                                service=_SERVICE_WINDOWS, origin="CREATED_BY_SCOPED_EXECUTOR",
                                process_state="RUNNING", platform_id=spec.platform_id,
                                release_manifest_sha256=spec.manifest_sha256,
                                service_health="UNKNOWN", core_activated=False,
                                fully_healthy=False)
                if status[1] == api.SERVICE_STOPPED:
                    break
                time.sleep(0.1)
            raise RuntimeError("SCM service did not reach running state; inspect before retry")
        finally:
            if service is not None:
                api.CloseServiceHandle(service)
            api.CloseServiceHandle(scm)

    def restart_verified(self, spec: NativeServiceSpecification) -> dict[str, object]:
        """SCM repair for an exact matching command, never an unrelated service."""
        _check_spec(spec, PlatformReleaseTarget.WINDOWS_X86_64)
        api = self._api()
        from subprocess import list2cmdline
        scm = api.OpenSCManager(None, None, api.SC_MANAGER_ALL_ACCESS)
        handle = None
        try:
            handle = api.OpenService(scm, _SERVICE_WINDOWS, api.SERVICE_ALL_ACCESS)
            self._verify_owned_config(api, handle, spec)
            status = api.QueryServiceStatus(handle)
            if status[1] != api.SERVICE_STOPPED:
                api.ControlService(handle, api.SERVICE_CONTROL_STOP)
                self._wait_stopped(api, handle)
            api.StartService(handle, None)
            self._wait_running(api, handle)
            return dict(schema="aegis.native-service-receipt.v1",
                        service=_SERVICE_WINDOWS, process_state="RUNNING",
                        platform_id=spec.platform_id,
                        release_manifest_sha256=spec.manifest_sha256,
                        service_health="UNKNOWN", core_activated=False,
                        fully_healthy=False)
        finally:
            if handle is not None:
                api.CloseServiceHandle(handle)
            api.CloseServiceHandle(scm)

    @staticmethod
    def _wait_stopped(api, handle) -> None:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if api.QueryServiceStatus(handle)[1] == api.SERVICE_STOPPED:
                return
            time.sleep(0.1)
        raise RuntimeError("SCM stop timeout; state requires reconciliation")

    @staticmethod
    def _wait_running(api, handle) -> None:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            state = api.QueryServiceStatus(handle)[1]
            if state == api.SERVICE_RUNNING:
                return
            if state == api.SERVICE_STOPPED:
                raise RuntimeError("SCM service immediately exited; reconcile before retry")
            time.sleep(0.1)
        raise RuntimeError("SCM startup timeout; state requires reconciliation")

    def replace_verified(
        self, previous: NativeServiceSpecification, candidate: NativeServiceSpecification,
    ) -> dict[str, object]:
        """SCM exact signed release replacement with retained Platform identity."""
        _check_spec(previous, PlatformReleaseTarget.WINDOWS_X86_64)
        _check_spec(candidate, PlatformReleaseTarget.WINDOWS_X86_64)
        if (candidate.platform_id != previous.platform_id
                or candidate.public_key_sha256 != previous.public_key_sha256
                or candidate.identity_home != previous.identity_home
                or candidate.local_state != previous.local_state):
            raise PlatformInstallationDenied("SCM replacement changes Platform identity")
        from subprocess import list2cmdline
        api = self._api()
        scm = api.OpenSCManager(None, None, api.SC_MANAGER_ALL_ACCESS)
        handle = None
        try:
            handle = api.OpenService(scm, _SERVICE_WINDOWS, api.SERVICE_ALL_ACCESS)
            self._verify_owned_config(api, handle, previous)
            if api.QueryServiceStatus(handle)[1] != api.SERVICE_STOPPED:
                api.ControlService(handle, api.SERVICE_CONTROL_STOP)
                self._wait_stopped(api, handle)
            api.ChangeServiceConfig(
                handle, api.SERVICE_NO_CHANGE, api.SERVICE_NO_CHANGE,
                api.SERVICE_NO_CHANGE, list2cmdline(candidate.command()),
                None, None, None, None, None, None,
            )
            api.StartService(handle, None)
            self._wait_running(api, handle)
            return dict(schema="aegis.native-service-receipt.v1",
                        service=_SERVICE_WINDOWS, process_state="RUNNING",
                        platform_id=candidate.platform_id,
                        release_manifest_sha256=candidate.manifest_sha256,
                        service_health="UNKNOWN", core_activated=False,
                        fully_healthy=False)
        finally:
            if handle is not None:
                api.CloseServiceHandle(handle)
            api.CloseServiceHandle(scm)

    def stop_and_unregister(self, spec: NativeServiceSpecification) -> dict[str, object]:
        _check_spec(spec, PlatformReleaseTarget.WINDOWS_X86_64)
        api = self._api()
        from subprocess import list2cmdline
        scm = api.OpenSCManager(None, None, api.SC_MANAGER_ALL_ACCESS)
        service = None
        try:
            service = api.OpenService(scm, _SERVICE_WINDOWS, api.SERVICE_ALL_ACCESS)
            self._verify_owned_config(api, service, spec)
            status = api.QueryServiceStatus(service)
            if status[1] != api.SERVICE_STOPPED:
                api.ControlService(service, api.SERVICE_CONTROL_STOP)
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if api.QueryServiceStatus(service)[1] == api.SERVICE_STOPPED:
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError("SCM stop deadline; outcome unknown")
            api.DeleteService(service)
            return dict(schema="aegis.native-service-receipt.v1",
                        service=_SERVICE_WINDOWS, process_state="REMOVED",
                        identity_policy="RETAIN", core_activated=False,
                        service_health="UNKNOWN")
        finally:
            if service is not None:
                api.CloseServiceHandle(service)
            api.CloseServiceHandle(scm)
