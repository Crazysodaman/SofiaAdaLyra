from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class PlatformFamily(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    BSD = "bsd"
    OTHER = "other"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MachineIdentity:
    machine_id: str
    hostname: str

    def __post_init__(self) -> None:
        if not isinstance(self.machine_id, str):
            raise TypeError(
                "MachineIdentity machine_id must be a string."
            )

        if not self.machine_id.strip():
            raise ValueError(
                "MachineIdentity machine_id must not be empty."
            )

        if not isinstance(self.hostname, str):
            raise TypeError(
                "MachineIdentity hostname must be a string."
            )

        if not self.hostname.strip():
            raise ValueError(
                "MachineIdentity hostname must not be empty."
            )


@dataclass(frozen=True)
class OperatingSystemInfo:
    family: PlatformFamily
    name: str | None = None
    version: str | None = None
    architecture: str | None = None
    kernel: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.family, PlatformFamily):
            raise TypeError(
                "OperatingSystemInfo family must be a PlatformFamily."
            )

        for field_name in (
            "name",
            "version",
            "architecture",
            "kernel",
        ):
            value = getattr(self, field_name)

            if value is not None and not isinstance(value, str):
                raise TypeError(
                    f"OperatingSystemInfo {field_name} must be "
                    "a string or None."
                )


@dataclass(frozen=True)
class VirtualizationInfo:
    is_virtual_machine: bool
    hypervisor: str | None = None
    platform: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.is_virtual_machine, bool):
            raise TypeError(
                "VirtualizationInfo is_virtual_machine must be a bool."
            )

        if (
            self.hypervisor is not None
            and not isinstance(self.hypervisor, str)
        ):
            raise TypeError(
                "VirtualizationInfo hypervisor must be a string or None."
            )

        if (
            self.platform is not None
            and not isinstance(self.platform, str)
        ):
            raise TypeError(
                "VirtualizationInfo platform must be a string or None."
            )


@dataclass(frozen=True)
class NetworkAdapterInfo:
    name: str
    mac_address: str | None = None
    interface_type: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                "NetworkAdapterInfo name must be a string."
            )

        if not self.name.strip():
            raise ValueError(
                "NetworkAdapterInfo name must not be empty."
            )

        if (
            self.mac_address is not None
            and not isinstance(self.mac_address, str)
        ):
            raise TypeError(
                "NetworkAdapterInfo mac_address must be a string or None."
            )

        if (
            self.interface_type is not None
            and not isinstance(self.interface_type, str)
        ):
            raise TypeError(
                "NetworkAdapterInfo interface_type must be a string or None."
            )


@dataclass(frozen=True)
class StorageDeviceInfo:
    name: str
    capacity_bytes: int | None = None
    device_type: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                "StorageDeviceInfo name must be a string."
            )

        if not self.name.strip():
            raise ValueError(
                "StorageDeviceInfo name must not be empty."
            )

        if self.capacity_bytes is not None:
            if not isinstance(self.capacity_bytes, int):
                raise TypeError(
                    "StorageDeviceInfo capacity_bytes must be "
                    "an int or None."
                )

            if self.capacity_bytes < 0:
                raise ValueError(
                    "StorageDeviceInfo capacity_bytes must not be negative."
                )

        if (
            self.device_type is not None
            and not isinstance(self.device_type, str)
        ):
            raise TypeError(
                "StorageDeviceInfo device_type must be a string or None."
            )


@dataclass(frozen=True)
class HardwareProfile:
    cpu: str | None = None
    gpu: tuple[str, ...] = ()
    memory_bytes: int | None = None
    storage: tuple[StorageDeviceInfo, ...] = ()
    network_adapters: tuple[NetworkAdapterInfo, ...] = ()

    def __post_init__(self) -> None:
        if self.cpu is not None and not isinstance(self.cpu, str):
            raise TypeError(
                "HardwareProfile cpu must be a string or None."
            )

        if not isinstance(self.gpu, tuple):
            raise TypeError(
                "HardwareProfile gpu must be a tuple."
            )

        for gpu in self.gpu:
            if not isinstance(gpu, str):
                raise TypeError(
                    "HardwareProfile gpu must contain strings."
                )

        if self.memory_bytes is not None:
            if not isinstance(self.memory_bytes, int):
                raise TypeError(
                    "HardwareProfile memory_bytes must be an int or None."
                )

            if self.memory_bytes < 0:
                raise ValueError(
                    "HardwareProfile memory_bytes must not be negative."
                )

        if not isinstance(self.storage, tuple):
            raise TypeError(
                "HardwareProfile storage must be a tuple."
            )

        for device in self.storage:
            if not isinstance(device, StorageDeviceInfo):
                raise TypeError(
                    "HardwareProfile storage must contain "
                    "StorageDeviceInfo instances."
                )

        if not isinstance(self.network_adapters, tuple):
            raise TypeError(
                "HardwareProfile network_adapters must be a tuple."
            )

        for adapter in self.network_adapters:
            if not isinstance(adapter, NetworkAdapterInfo):
                raise TypeError(
                    "HardwareProfile network_adapters must contain "
                    "NetworkAdapterInfo instances."
                )


@dataclass(frozen=True)
class MachineVerification:
    first_observed_at: datetime
    last_verified_at: datetime
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.first_observed_at, datetime):
            raise TypeError(
                "MachineVerification first_observed_at must be a datetime."
            )

        if not isinstance(self.last_verified_at, datetime):
            raise TypeError(
                "MachineVerification last_verified_at must be a datetime."
            )

        if self.last_verified_at < self.first_observed_at:
            raise ValueError(
                "MachineVerification last_verified_at must not be "
                "earlier than first_observed_at."
            )

        if not isinstance(self.source, str):
            raise TypeError(
                "MachineVerification source must be a string."
            )

        if not self.source.strip():
            raise ValueError(
                "MachineVerification source must not be empty."
            )


@dataclass(frozen=True)
class MachineProfile:
    identity: MachineIdentity
    operating_system: OperatingSystemInfo
    virtualization: VirtualizationInfo
    hardware: HardwareProfile
    verification: MachineVerification

    def __post_init__(self) -> None:
        if not isinstance(self.identity, MachineIdentity):
            raise TypeError(
                "MachineProfile identity must be a MachineIdentity."
            )

        if not isinstance(
            self.operating_system,
            OperatingSystemInfo,
        ):
            raise TypeError(
                "MachineProfile operating_system must be "
                "an OperatingSystemInfo."
            )

        if not isinstance(
            self.virtualization,
            VirtualizationInfo,
        ):
            raise TypeError(
                "MachineProfile virtualization must be "
                "a VirtualizationInfo."
            )

        if not isinstance(self.hardware, HardwareProfile):
            raise TypeError(
                "MachineProfile hardware must be a HardwareProfile."
            )

        if not isinstance(
            self.verification,
            MachineVerification,
        ):
            raise TypeError(
                "MachineProfile verification must be "
                "a MachineVerification."
            )