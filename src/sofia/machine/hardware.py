from __future__ import annotations

import glob
import platform
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from sofia.machine.model import (
    HardwareProfile,
    NetworkAdapterInfo,
    StorageDeviceInfo,
    VirtualizationInfo,
)


_LINUX_MEMINFO: Final[Path] = Path("/proc/meminfo")
_LINUX_CPUINFO: Final[Path] = Path("/proc/cpuinfo")
_LINUX_SYSFS_DMI: Final[Path] = Path("/sys/class/dmi/id")
_LINUX_DRM_PATH: Final[Path] = Path("/sys/class/drm")
_LINUX_BLOCK_PATH: Final[Path] = Path("/sys/class/block")
_LINUX_NET_PATH: Final[Path] = Path("/sys/class/net")


@dataclass(frozen=True)
class HardwareDiscoveryResult:
    """
    Immutable observation of hardware and virtualization state.

    This is an observation result. Persistence, freshness, invalidation,
    comparison, and refresh policy belong to later inventory layers.
    """

    hardware: HardwareProfile
    virtualization: VirtualizationInfo
    source: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.hardware,
            HardwareProfile,
        ):
            raise TypeError(
                "HardwareDiscoveryResult hardware must be "
                "a HardwareProfile."
            )

        if not isinstance(
            self.virtualization,
            VirtualizationInfo,
        ):
            raise TypeError(
                "HardwareDiscoveryResult virtualization must be "
                "a VirtualizationInfo."
            )

        if not isinstance(self.source, str):
            raise TypeError(
                "HardwareDiscoveryResult source must be a string."
            )

        if not self.source.strip():
            raise ValueError(
                "HardwareDiscoveryResult source must not be empty."
            )


class HardwareDiscovery(ABC):
    """
    Platform-neutral hardware discovery contract.
    """

    @abstractmethod
    def discover(self) -> HardwareDiscoveryResult:
        raise NotImplementedError


class UnsupportedHardwareDiscovery(HardwareDiscovery):
    """
    Explicit fallback for unsupported operating systems.

    Unsupported platforms produce an unknown hardware profile rather than
    pretending that the current platform is understood.
    """

    def discover(self) -> HardwareDiscoveryResult:
        return HardwareDiscoveryResult(
            hardware=HardwareProfile(),
            virtualization=VirtualizationInfo(
                is_virtual_machine=False,
            ),
            source="unsupported-platform-hardware-discovery",
        )


class WindowsHardwareDiscovery(HardwareDiscovery):
    """
    Windows hardware discovery.

    Windows-specific hardware information is obtained through PowerShell/CIM
    where useful. PowerShell is an implementation mechanism here, not part
    of Sofía's capability model.
    """

    def discover(self) -> HardwareDiscoveryResult:
        if sys.platform != "win32":
            raise RuntimeError(
                "WindowsHardwareDiscovery can only run on Windows."
            )

        cpu = self._discover_cpu()
        gpu = self._discover_gpu()
        memory = self._discover_memory()
        storage = self._discover_storage()
        network = self._discover_network()
        virtualization = self._discover_virtualization()

        return HardwareDiscoveryResult(
            hardware=HardwareProfile(
                cpu=cpu,
                gpu=gpu,
                memory_bytes=memory,
                storage=storage,
                network_adapters=network,
            ),
            virtualization=virtualization,
            source="windows-native-hardware-discovery",
        )

    @staticmethod
    def _powershell(
        command: str,
    ) -> str | None:
        try:
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (
            OSError,
            subprocess.SubprocessError,
        ):
            return None

        if completed.returncode != 0:
            return None

        output = completed.stdout.strip()

        if not output:
            return None

        return output

    def _discover_cpu(self) -> str | None:
        output = self._powershell(
            "(Get-CimInstance Win32_Processor | "
            "Select-Object -First 1 -ExpandProperty Name)"
        )

        if not output:
            return None

        return output.splitlines()[0].strip() or None

    def _discover_gpu(self) -> tuple[str, ...]:
        output = self._powershell(
            "(Get-CimInstance Win32_VideoController | "
            "Select-Object -ExpandProperty Name)"
        )

        if not output:
            return ()

        values = []

        for line in output.splitlines():
            value = line.strip()

            if value and value not in values:
                values.append(value)

        return tuple(values)

    def _discover_memory(self) -> int | None:
        output = self._powershell(
            "(Get-CimInstance Win32_ComputerSystem | "
            "Select-Object -ExpandProperty TotalPhysicalMemory)"
        )

        if not output:
            return None

        value = output.splitlines()[0].strip()

        try:
            memory = int(value)
        except ValueError:
            return None

        if memory < 0:
            return None

        return memory

    def _discover_storage(
        self,
    ) -> tuple[StorageDeviceInfo, ...]:
        output = self._powershell(
            "Get-CimInstance Win32_DiskDrive | "
            "Select-Object Model,Size,MediaType | "
            "ForEach-Object { "
            "$model = $_.Model; "
            "$size = $_.Size; "
            "$media = $_.MediaType; "
            "\"$model`t$size`t$media\" "
            "}"
        )

        if not output:
            return ()

        devices: list[StorageDeviceInfo] = []

        for line in output.splitlines():
            parts = line.split("\t")

            if not parts:
                continue

            name = parts[0].strip()

            if not name:
                continue

            capacity: int | None = None

            if len(parts) > 1:
                try:
                    candidate = int(parts[1].strip())
                    if candidate >= 0:
                        capacity = candidate
                except ValueError:
                    pass

            device_type = (
                parts[2].strip()
                if len(parts) > 2 and parts[2].strip()
                else None
            )

            devices.append(
                StorageDeviceInfo(
                    name=name,
                    capacity_bytes=capacity,
                    device_type=device_type,
                )
            )

        return tuple(devices)

    def _discover_network(
        self,
    ) -> tuple[NetworkAdapterInfo, ...]:
        output = self._powershell(
            "Get-CimInstance Win32_NetworkAdapterConfiguration "
            "-Filter \"IPEnabled=True\" | "
            "ForEach-Object { "
            "\"$($_.Description)`t$($_.MACAddress)\" "
            "}"
        )

        if not output:
            return ()

        adapters: list[NetworkAdapterInfo] = []

        for line in output.splitlines():
            parts = line.split("\t")

            name = parts[0].strip()

            if not name:
                continue

            mac = (
                parts[1].strip()
                if len(parts) > 1 and parts[1].strip()
                else None
            )

            adapters.append(
                NetworkAdapterInfo(
                    name=name,
                    mac_address=mac,
                    interface_type=None,
                )
            )

        return tuple(adapters)

    def _discover_virtualization(
        self,
    ) -> VirtualizationInfo:
        output = self._powershell(
            "(Get-CimInstance Win32_ComputerSystem | "
            "Select-Object Manufacturer,Model | "
            "ForEach-Object { "
            "\"$($_.Manufacturer)`t$($_.Model)\" "
            "})"
        )

        if not output:
            return VirtualizationInfo(
                is_virtual_machine=False,
            )

        line = output.splitlines()[0]
        parts = line.split("\t")

        manufacturer = (
            parts[0].strip().lower()
            if parts
            else ""
        )

        model = (
            parts[1].strip().lower()
            if len(parts) > 1
            else ""
        )

        evidence = f"{manufacturer} {model}".strip()

        hypervisor = None

        if "vmware" in evidence:
            hypervisor = "VMware"
        elif "virtualbox" in evidence:
            hypervisor = "VirtualBox"
        elif "hyper-v" in evidence:
            hypervisor = "Hyper-V"
        elif "microsoft corporation" in manufacturer and (
            "virtual" in model
            or "virtual machine" in model
        ):
            hypervisor = "Hyper-V"

        if hypervisor is None:
            return VirtualizationInfo(
                is_virtual_machine=False,
            )

        return VirtualizationInfo(
            is_virtual_machine=True,
            hypervisor=hypervisor,
            platform="windows",
        )


class LinuxHardwareDiscovery(HardwareDiscovery):
    """
    Linux-native hardware discovery.

    Linux information is read directly from procfs/sysfs where possible.
    No shell is required for the base discovery path.
    """

    def discover(self) -> HardwareDiscoveryResult:
        if not sys.platform.startswith("linux"):
            raise RuntimeError(
                "LinuxHardwareDiscovery can only run on Linux."
            )

        return HardwareDiscoveryResult(
            hardware=HardwareProfile(
                cpu=self._discover_cpu(),
                gpu=self._discover_gpu(),
                memory_bytes=self._discover_memory(),
                storage=self._discover_storage(),
                network_adapters=self._discover_network(),
            ),
            virtualization=self._discover_virtualization(),
            source="linux-native-hardware-discovery",
        )

    @staticmethod
    def _read_text(path: Path) -> str | None:
        try:
            value = path.read_text(
                encoding="utf-8",
            ).strip()
        except OSError:
            return None

        return value or None

    def _discover_cpu(self) -> str | None:
        value = self._read_text(_LINUX_CPUINFO)

        if not value:
            return None

        for line in value.splitlines():
            if line.startswith("model name"):
                _, separator, name = line.partition(":")

                if separator and name.strip():
                    return name.strip()

            if line.startswith("Hardware"):
                _, separator, name = line.partition(":")

                if separator and name.strip():
                    return name.strip()

        return None

    def _discover_gpu(self) -> tuple[str, ...]:
        devices: list[str] = []

        for path in glob.glob(
            str(_LINUX_DRM_PATH / "card*" / "device"),
        ):
            device_path = Path(path)

            vendor = self._read_text(
                device_path / "vendor"
            )

            device = self._read_text(
                device_path / "device"
            )

            label = None

            if vendor and device:
                label = f"{vendor} {device}"
            elif vendor:
                label = vendor
            elif device:
                label = device

            if label and label not in devices:
                devices.append(label)

        return tuple(devices)

    def _discover_memory(self) -> int | None:
        value = self._read_text(_LINUX_MEMINFO)

        if not value:
            return None

        for line in value.splitlines():
            if not line.startswith("MemTotal:"):
                continue

            parts = line.split()

            if len(parts) < 2:
                return None

            try:
                kib = int(parts[1])
            except ValueError:
                return None

            if kib < 0:
                return None

            return kib * 1024

        return None

    def _discover_storage(
        self,
    ) -> tuple[StorageDeviceInfo, ...]:
        devices: list[StorageDeviceInfo] = []

        try:
            paths = list(
                _LINUX_BLOCK_PATH.iterdir()
            )
        except OSError:
            return ()

        for path in paths:
            name = path.name

            if not name:
                continue

            if name.startswith("loop"):
                continue

            size_text = self._read_text(
                path / "size"
            )

            capacity = None

            if size_text:
                try:
                    sectors = int(size_text)

                    if sectors >= 0:
                        capacity = sectors * 512
                except ValueError:
                    pass

            rotational = self._read_text(
                path / "queue" / "rotational"
            )

            if rotational == "0":
                device_type = "non-rotational"
            elif rotational == "1":
                device_type = "rotational"
            else:
                device_type = None

            devices.append(
                StorageDeviceInfo(
                    name=name,
                    capacity_bytes=capacity,
                    device_type=device_type,
                )
            )

        return tuple(devices)

    def _discover_network(
        self,
    ) -> tuple[NetworkAdapterInfo, ...]:
        try:
            paths = list(
                _LINUX_NET_PATH.iterdir()
            )
        except OSError:
            return ()

        adapters: list[NetworkAdapterInfo] = []

        for path in paths:
            name = path.name

            if not name:
                continue

            mac = self._read_text(
                path / "address"
            )

            interface_type = None

            type_value = self._read_text(
                path / "type"
            )

            if type_value == "1":
                interface_type = "ethernet"
            elif type_value == "772":
                interface_type = "loopback"

            adapters.append(
                NetworkAdapterInfo(
                    name=name,
                    mac_address=mac,
                    interface_type=interface_type,
                )
            )

        return tuple(adapters)

    def _discover_virtualization(
        self,
    ) -> VirtualizationInfo:
        product_name = self._read_text(
            _LINUX_SYSFS_DMI / "product_name"
        )

        sys_vendor = self._read_text(
            _LINUX_SYSFS_DMI / "sys_vendor"
        )

        hypervisor = self._read_text(
            Path("/sys/hypervisor/type")
        )

        evidence = " ".join(
            value.lower()
            for value in (
                product_name,
                sys_vendor,
                hypervisor,
            )
            if value
        )

        if "vmware" in evidence:
            return VirtualizationInfo(
                is_virtual_machine=True,
                hypervisor="VMware",
                platform="linux",
            )

        if "virtualbox" in evidence:
            return VirtualizationInfo(
                is_virtual_machine=True,
                hypervisor="VirtualBox",
                platform="linux",
            )

        if "microsoft" in evidence and (
            "virtual" in evidence
            or "hyper-v" in evidence
        ):
            return VirtualizationInfo(
                is_virtual_machine=True,
                hypervisor="Hyper-V",
                platform="linux",
            )

        if "kvm" in evidence:
            return VirtualizationInfo(
                is_virtual_machine=True,
                hypervisor="KVM",
                platform="linux",
            )

        return VirtualizationInfo(
            is_virtual_machine=False,
        )


def create_hardware_discovery() -> HardwareDiscovery:
    """
    Select the native hardware discovery implementation.
    """

    if sys.platform == "win32":
        return WindowsHardwareDiscovery()

    if sys.platform.startswith("linux"):
        return LinuxHardwareDiscovery()

    return UnsupportedHardwareDiscovery()