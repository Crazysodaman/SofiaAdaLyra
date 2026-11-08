"""Read-only Windows SCM / Debian systemd origin fencing for AG-D011.

A service name or running process is never proof that an installer owns it.
This observer does not install, start, stop, adopt, update or remove services.
It is a prerequisite for Team A's eventual authenticated OS executor.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import re
import subprocess

from sofia.platform.state.private_file import assert_no_redirected_components

_WINDOWS_NAME = "AegisPlatform"
_DEBIAN_UNIT = "aegis-platform.service"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class NativeServiceObservation:
    name: str
    source: str
    origin: str
    process_state: str
    health: str = "UNKNOWN"
    executable_verified: bool = False

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "aegis.installer.native-service-observation.v1",
            "name": self.name,
            "source": self.source,
            "origin": self.origin,
            "process_state": self.process_state,
            "health": self.health,
            "executable_verified": self.executable_verified,
            "authorized": False,
            "executed": False,
        }


def inspect_debian_systemd_service(
    *, expected_unit_sha256: str, unit_path: Path | str = "/etc/systemd/system/aegis-platform.service",
    runner=subprocess.run,
) -> NativeServiceObservation:
    """Fail closed on ambiguous, redirected or foreign unit origin.

    expected_unit_sha256 must come from an independently trusted signed
    service configuration receipt, never from a user-controlled unit file.
    """
    if not isinstance(expected_unit_sha256, str) or not _SHA.fullmatch(expected_unit_sha256):
        raise ValueError("trusted unit digest required")
    path = Path(unit_path).absolute()
    expected_name = _DEBIAN_UNIT
    try:
        result = runner(
            ["systemctl", "show", expected_name,
             "--property=LoadState,FragmentPath,ActiveState,SubState,MainPID",
             "--no-pager"],
            check=False, capture_output=True, text=True, timeout=12,
        )
    except (OSError, subprocess.TimeoutExpired):
        return NativeServiceObservation(expected_name, "systemd", "UNKNOWN", "UNKNOWN")
    if result.returncode != 0 or len(result.stdout) > 4096:
        return NativeServiceObservation(expected_name, "systemd", "UNKNOWN", "UNKNOWN")
    fields = {}
    for line in result.stdout.splitlines():
        k, sep, v = line.partition("=")
        if sep and k in ("LoadState", "FragmentPath", "ActiveState", "SubState", "MainPID"):
            if k in fields or len(v) > 1024:
                return NativeServiceObservation(expected_name, "systemd", "UNKNOWN", "UNKNOWN")
            fields[k] = v
    if fields.get("LoadState") == "not-found":
        if path.exists() or path.is_symlink():
            return NativeServiceObservation(expected_name, "systemd", "FOREIGN", "UNKNOWN")
        return NativeServiceObservation(expected_name, "systemd", "ABSENT", "NOT_INSTALLED")
    if fields.get("LoadState") != "loaded":
        return NativeServiceObservation(expected_name, "systemd", "UNKNOWN", "UNKNOWN")
    if fields.get("FragmentPath") != str(path):
        return NativeServiceObservation(expected_name, "systemd", "FOREIGN", "UNKNOWN")
    try:
        assert_no_redirected_components(path, include_leaf=True)
        if not path.is_file() or path.stat(follow_symlinks=False).st_size > 64_000:
            raise ValueError("invalid unit")
        actual = sha256(path.read_bytes()).hexdigest()
    except (OSError, ValueError, PermissionError):
        return NativeServiceObservation(expected_name, "systemd", "UNKNOWN", "UNKNOWN")
    if actual != expected_unit_sha256:
        return NativeServiceObservation(expected_name, "systemd", "FOREIGN", "UNKNOWN")
    # Matching config alone is not an installation-receipt/identity match.
    return NativeServiceObservation(
        expected_name, "systemd", "MATCHES_CONFIG_UNVERIFIED",
        fields.get("ActiveState", "UNKNOWN").upper(),
        executable_verified=False,
    )


def inspect_windows_scm_service(*, expected_binary_command: str,
                                win32service_module=None,
                                pywintypes_module=None) -> NativeServiceObservation:
    """Observe native SCM config without modifying an existing service."""
    if not isinstance(expected_binary_command, str) or not expected_binary_command.strip():
        raise ValueError("signed executable command expected")
    if win32service_module is None or pywintypes_module is None:
        if os.name != "nt":
            return NativeServiceObservation(_WINDOWS_NAME, "SCM", "UNKNOWN", "UNKNOWN")
        import pywintypes
        import win32service
        win32service_module, pywintypes_module = win32service, pywintypes
    service_api = win32service_module
    manager = None
    handle = None
    try:
        manager = service_api.OpenSCManager(None, None, service_api.SC_MANAGER_CONNECT)
        try:
            handle = service_api.OpenService(
                manager, _WINDOWS_NAME,
                service_api.SERVICE_QUERY_CONFIG | service_api.SERVICE_QUERY_STATUS,
            )
        except pywintypes_module.error as error:
            if getattr(error, "winerror", None) == 1060:
                return NativeServiceObservation(_WINDOWS_NAME, "SCM", "ABSENT", "NOT_INSTALLED")
            raise
        config = service_api.QueryServiceConfig(handle)
        status = service_api.QueryServiceStatus(handle)
        if len(config) < 9 or len(status) < 2:
            return NativeServiceObservation(_WINDOWS_NAME, "SCM", "UNKNOWN", "UNKNOWN")
        if config[3] != expected_binary_command:
            return NativeServiceObservation(_WINDOWS_NAME, "SCM", "FOREIGN", "UNKNOWN")
        state = {
            service_api.SERVICE_RUNNING: "RUNNING",
            service_api.SERVICE_STOPPED: "STOPPED",
        }.get(status[1], "UNKNOWN")
        return NativeServiceObservation(
            _WINDOWS_NAME, "SCM", "MATCHES_CONFIG_UNVERIFIED", state,
            executable_verified=False,
        )
    except Exception:
        return NativeServiceObservation(_WINDOWS_NAME, "SCM", "UNKNOWN", "UNKNOWN")
    finally:
        if handle is not None:
            service_api.CloseServiceHandle(handle)
        if manager is not None:
            service_api.CloseServiceHandle(manager)
