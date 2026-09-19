from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class SystemCapabilityName(str, Enum):
    PROCESS_INSPECT = "process.inspect"
    SYSTEM_INSPECT = "system.inspect"
    NETWORK_INSPECT = "network.inspect"
    SERVICE_INSPECT = "service.inspect"
    HARDWARE_INSPECT = "hardware.inspect"


class SystemCapabilityResultKind(str, Enum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True)
class SystemCapability:
    name: SystemCapabilityName
    description: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.name,
            SystemCapabilityName,
        ):
            raise TypeError(
                "SystemCapability name must be a SystemCapabilityName."
            )

        if not isinstance(self.description, str):
            raise TypeError(
                "SystemCapability description must be a string."
            )

        if not self.description.strip():
            raise ValueError(
                "SystemCapability description must not be empty."
            )


@dataclass(frozen=True)
class SystemCapabilityRequest:
    capability: SystemCapability
    parameters: Mapping[str, Any] = MappingProxyType({})

    def __post_init__(self) -> None:
        if not isinstance(
            self.capability,
            SystemCapability,
        ):
            raise TypeError(
                "SystemCapabilityRequest capability must be "
                "a SystemCapability."
            )

        if not isinstance(self.parameters, Mapping):
            raise TypeError(
                "SystemCapabilityRequest parameters must be a mapping."
            )

        forbidden_parameters = {
            "command",
            "commands",
            "cmd",
            "shell",
            "script",
            "executable",
            "argv",
            "arguments",
        }

        supplied_forbidden = forbidden_parameters.intersection(
            self.parameters.keys()
        )

        if supplied_forbidden:
            names = ", ".join(sorted(supplied_forbidden))
            raise ValueError(
                "SystemCapabilityRequest cannot contain arbitrary "
                f"execution parameters: {names}"
            )


@dataclass(frozen=True)
class SystemCapabilityResult:
    capability: SystemCapabilityName
    kind: SystemCapabilityResultKind
    evidence: Mapping[str, Any] | None = None
    observed_at: datetime | None = None
    backend_name: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.capability,
            SystemCapabilityName,
        ):
            raise TypeError(
                "SystemCapabilityResult capability must be "
                "a SystemCapabilityName."
            )

        if not isinstance(
            self.kind,
            SystemCapabilityResultKind,
        ):
            raise TypeError(
                "SystemCapabilityResult kind must be "
                "a SystemCapabilityResultKind."
            )

        if self.evidence is not None and not isinstance(
            self.evidence,
            Mapping,
        ):
            raise TypeError(
                "SystemCapabilityResult evidence must be a mapping "
                "or None."
            )

        if self.observed_at is not None and not isinstance(
            self.observed_at,
            datetime,
        ):
            raise TypeError(
                "SystemCapabilityResult observed_at must be a "
                "datetime or None."
            )

        if self.backend_name is not None:
            if not isinstance(self.backend_name, str):
                raise TypeError(
                    "SystemCapabilityResult backend_name must be "
                    "a string or None."
                )

            if not self.backend_name.strip():
                raise ValueError(
                    "SystemCapabilityResult backend_name must not "
                    "be empty."
                )

        if self.error is not None:
            if not isinstance(self.error, str):
                raise TypeError(
                    "SystemCapabilityResult error must be a "
                    "string or None."
                )

            if not self.error.strip():
                raise ValueError(
                    "SystemCapabilityResult error must not be empty."
                )

        if self.kind is SystemCapabilityResultKind.SUCCESS:
            if self.evidence is None:
                raise ValueError(
                    "Successful system capability results must "
                    "contain evidence."
                )

            if self.observed_at is None:
                raise ValueError(
                    "Successful system capability results must "
                    "contain observation metadata."
                )

            if self.backend_name is None:
                raise ValueError(
                    "Successful system capability results must "
                    "identify the backend."
                )

        if self.kind is not SystemCapabilityResultKind.SUCCESS:
            if self.evidence is not None:
                raise ValueError(
                    "Non-successful system capability results must "
                    "not contain evidence."
                )


@dataclass(frozen=True)
class ProcessInspection:
    pid: int
    name: str | None = None
    executable: str | None = None
    state: str | None = None
    started_at: datetime | None = None
    cpu_percent: float | None = None
    memory_bytes: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.pid, int):
            raise TypeError("ProcessInspection pid must be an integer.")

        if self.pid < 0:
            raise ValueError(
                "ProcessInspection pid must not be negative."
            )

        if self.cpu_percent is not None:
            if not isinstance(self.cpu_percent, (int, float)):
                raise TypeError(
                    "ProcessInspection cpu_percent must be numeric "
                    "or None."
                )

        if self.memory_bytes is not None:
            if not isinstance(self.memory_bytes, int):
                raise TypeError(
                    "ProcessInspection memory_bytes must be an integer "
                    "or None."
                )

            if self.memory_bytes < 0:
                raise ValueError(
                    "ProcessInspection memory_bytes must not be negative."
                )


@dataclass(frozen=True)
class SystemInspection:
    hostname: str | None = None
    operating_system: str | None = None
    operating_system_version: str | None = None
    architecture: str | None = None
    kernel: str | None = None
    uptime_seconds: float | None = None
    is_virtual_machine: bool | None = None
    hypervisor: str | None = None

    def __post_init__(self) -> None:
        if self.uptime_seconds is not None:
            if not isinstance(self.uptime_seconds, (int, float)):
                raise TypeError(
                    "SystemInspection uptime_seconds must be numeric "
                    "or None."
                )

            if self.uptime_seconds < 0:
                raise ValueError(
                    "SystemInspection uptime_seconds must not "
                    "be negative."
                )


@dataclass(frozen=True)
class NetworkInterfaceInspection:
    name: str
    state: str | None = None
    addresses: tuple[str, ...] = ()
    mac_address: str | None = None
    received_bytes: int | None = None
    transmitted_bytes: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                "NetworkInterfaceInspection name must be a string."
            )

        if not self.name.strip():
            raise ValueError(
                "NetworkInterfaceInspection name must not be empty."
            )

        if not isinstance(self.addresses, tuple):
            raise TypeError(
                "NetworkInterfaceInspection addresses must be a tuple."
            )

        if self.received_bytes is not None and (
            not isinstance(self.received_bytes, int)
            or self.received_bytes < 0
        ):
            raise ValueError(
                "NetworkInterfaceInspection received_bytes must be "
                "a non-negative integer or None."
            )

        if self.transmitted_bytes is not None and (
            not isinstance(self.transmitted_bytes, int)
            or self.transmitted_bytes < 0
        ):
            raise ValueError(
                "NetworkInterfaceInspection transmitted_bytes must be "
                "a non-negative integer or None."
            )


@dataclass(frozen=True)
class NetworkRouteInspection:
    destination: str
    gateway: str | None = None
    interface: str | None = None


@dataclass(frozen=True)
class NetworkInspection:
    interfaces: tuple[NetworkInterfaceInspection, ...] = ()
    routes: tuple[NetworkRouteInspection, ...] = ()
    dns_servers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ServiceInspection:
    name: str
    display_name: str | None = None
    state: str | None = None
    startup_type: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                "ServiceInspection name must be a string."
            )

        if not self.name.strip():
            raise ValueError(
                "ServiceInspection name must not be empty."
            )


@dataclass(frozen=True)
class HardwareInspection:
    cpu: Mapping[str, Any] | None = None
    gpu: Mapping[str, Any] | None = None
    memory: Mapping[str, Any] | None = None
    storage: Mapping[str, Any] | None = None
    network: Mapping[str, Any] | None = None
    virtualization: Mapping[str, Any] | None = None