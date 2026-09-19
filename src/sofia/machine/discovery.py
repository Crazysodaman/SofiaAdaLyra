from __future__ import annotations

import platform
import socket
import sys
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from sofia.machine.model import (
    MachineIdentity,
    OperatingSystemInfo,
    PlatformFamily,
)


_MACHINE_GUID_REGISTRY_PATH: Final[str] = (
    r"SOFTWARE\Microsoft\Cryptography"
)

_MACHINE_ID_PATH: Final[Path] = Path(
    "/etc/machine-id"
)


@dataclass(frozen=True)
class MachineDiscoveryResult:
    """
    Immutable observation of machine identity and operating-system state.

    This is an observation result, not persistent inventory. Persistence,
    comparison, invalidation, and refresh policy belong to later layers.
    """

    identity: MachineIdentity
    operating_system: OperatingSystemInfo
    observed_at: datetime
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.identity, MachineIdentity):
            raise TypeError(
                "MachineDiscoveryResult identity must be "
                "a MachineIdentity."
            )

        if not isinstance(
            self.operating_system,
            OperatingSystemInfo,
        ):
            raise TypeError(
                "MachineDiscoveryResult operating_system must be "
                "an OperatingSystemInfo."
            )

        if not isinstance(self.observed_at, datetime):
            raise TypeError(
                "MachineDiscoveryResult observed_at must be "
                "a datetime."
            )

        if not isinstance(self.source, str):
            raise TypeError(
                "MachineDiscoveryResult source must be a string."
            )

        if not self.source.strip():
            raise ValueError(
                "MachineDiscoveryResult source must not be empty."
            )


class MachineDiscovery(ABC):
    """
    Platform-neutral contract for discovering machine identity
    and operating-system information.
    """

    @abstractmethod
    def discover(self) -> MachineDiscoveryResult:
        """
        Inspect the current machine and return observed environment facts.
        """
        raise NotImplementedError


class UnsupportedMachineDiscovery(MachineDiscovery):
    """
    Discovery implementation used when the current platform is unsupported.
    """

    def __init__(
        self,
        system_name: str | None = None,
    ) -> None:
        self._system_name = (
            system_name
            if system_name is not None
            else platform.system()
        )

    def discover(self) -> MachineDiscoveryResult:
        hostname = socket.gethostname()

        identity = MachineIdentity(
            machine_id=f"unknown:{hostname}",
            hostname=hostname,
        )

        operating_system = OperatingSystemInfo(
            family=PlatformFamily.UNKNOWN,
            name=self._system_name or None,
            version=platform.version() or None,
            architecture=platform.machine() or None,
            kernel=platform.release() or None,
        )

        return MachineDiscoveryResult(
            identity=identity,
            operating_system=operating_system,
            observed_at=datetime.now(timezone.utc),
            source="unsupported-platform-discovery",
        )


class WindowsMachineDiscovery(MachineDiscovery):
    """
    Windows-native machine and operating-system discovery.

    The implementation intentionally uses native Python/Windows APIs rather
    than shelling out to PowerShell. PowerShell remains a possible mechanism
    for later IT capabilities, not a dependency of environmental identity.
    """

    def discover(self) -> MachineDiscoveryResult:
        if sys.platform != "win32":
            raise RuntimeError(
                "WindowsMachineDiscovery can only run on Windows."
            )

        hostname = socket.gethostname()
        machine_id = self._machine_guid()

        identity = MachineIdentity(
            machine_id=machine_id,
            hostname=hostname,
        )

        operating_system = OperatingSystemInfo(
            family=PlatformFamily.WINDOWS,
            name=self._windows_name(),
            version=platform.release(),
            architecture=platform.machine() or None,
            kernel=platform.version() or None,
        )

        return MachineDiscoveryResult(
            identity=identity,
            operating_system=operating_system,
            observed_at=datetime.now(timezone.utc),
            source="windows-native-discovery",
        )

    @staticmethod
    def _machine_guid() -> str:
        try:
            import winreg
        except ImportError as exc:
            raise RuntimeError(
                "Windows registry support is unavailable."
            ) from exc

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                _MACHINE_GUID_REGISTRY_PATH,
            ) as key:
                value, _ = winreg.QueryValueEx(
                    key,
                    "MachineGuid",
                )
        except OSError as exc:
            raise RuntimeError(
                "Unable to read the Windows MachineGuid."
            ) from exc

        if not isinstance(value, str):
            raise RuntimeError(
                "Windows MachineGuid is not a string."
            )

        value = value.strip()

        if not value:
            raise RuntimeError(
                "Windows MachineGuid is empty."
            )

        return value

    @staticmethod
    def _windows_name() -> str:
        release = platform.release()

        if release == "10":
            return "Windows 10/11"

        if release:
            return f"Windows {release}"

        return "Windows"


class LinuxMachineDiscovery(MachineDiscovery):
    """
    Linux-native machine and operating-system discovery.

    The machine-id is read directly from the Linux filesystem. No shell
    command is required.
    """

    def discover(self) -> MachineDiscoveryResult:
        if not sys.platform.startswith("linux"):
            raise RuntimeError(
                "LinuxMachineDiscovery can only run on Linux."
            )

        hostname = socket.gethostname()
        machine_id = self._machine_id()

        identity = MachineIdentity(
            machine_id=machine_id,
            hostname=hostname,
        )

        operating_system = OperatingSystemInfo(
            family=PlatformFamily.LINUX,
            name=self._linux_name(),
            version=self._linux_version(),
            architecture=platform.machine() or None,
            kernel=platform.release() or None,
        )

        return MachineDiscoveryResult(
            identity=identity,
            operating_system=operating_system,
            observed_at=datetime.now(timezone.utc),
            source="linux-native-discovery",
        )

    @staticmethod
    def _machine_id() -> str:
        try:
            value = _MACHINE_ID_PATH.read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            value = ""

        if value:
            return value

        hostname = socket.gethostname().strip()

        if hostname:
            return f"hostname:{hostname}"

        return "unknown:linux"

    @staticmethod
    def _linux_name() -> str:
        os_release = Path("/etc/os-release")

        try:
            values = os_release.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError:
            return "Linux"

        parsed: dict[str, str] = {}

        for line in values:
            if "=" not in line:
                continue

            key, value = line.split(
                "=",
                1,
            )

            value = value.strip()

            if (
                len(value) >= 2
                and value[0] == '"'
                and value[-1] == '"'
            ):
                value = value[1:-1]

            parsed[key] = value

        return (
            parsed.get("PRETTY_NAME")
            or parsed.get("NAME")
            or "Linux"
        )

    @staticmethod
    def _linux_version() -> str | None:
        os_release = Path("/etc/os-release")

        try:
            values = os_release.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError:
            return platform.release() or None

        for line in values:
            if line.startswith("VERSION_ID="):
                value = line.split(
                    "=",
                    1,
                )[1].strip()

                if (
                    len(value) >= 2
                    and value[0] == '"'
                    and value[-1] == '"'
                ):
                    value = value[1:-1]

                return value or None

        return platform.release() or None


def create_machine_discovery() -> MachineDiscovery:
    """
    Select the native machine discovery implementation for this platform.
    """

    if sys.platform == "win32":
        return WindowsMachineDiscovery()

    if sys.platform.startswith("linux"):
        return LinuxMachineDiscovery()

    return UnsupportedMachineDiscovery()