from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sofia.system.backend import SystemCapabilityBackend
from sofia.system.model import (
    NetworkInspection,
    NetworkInterfaceInspection,
    NetworkRouteInspection,
    ProcessInspection,
    ServiceInspection,
    SystemCapability,
    SystemCapabilityName,
    SystemCapabilityRequest,
    SystemCapabilityResult,
    SystemCapabilityResultKind,
    SystemInspection,
)


CommandRunner = Callable[[tuple[str, ...]], str]


class LinuxSystemCapabilityBackend(SystemCapabilityBackend):
    """Linux implementation of read-only system inspection capabilities."""

    _PROCESS_CAPABILITY = SystemCapability(
        name=SystemCapabilityName.PROCESS_INSPECT,
        description="Inspect running Linux processes.",
    )

    _SYSTEM_CAPABILITY = SystemCapability(
        name=SystemCapabilityName.SYSTEM_INSPECT,
        description="Inspect Linux operating-system state.",
    )

    _NETWORK_CAPABILITY = SystemCapability(
        name=SystemCapabilityName.NETWORK_INSPECT,
        description="Inspect Linux network interfaces, routes, and DNS.",
    )

    _SERVICE_CAPABILITY = SystemCapability(
        name=SystemCapabilityName.SERVICE_INSPECT,
        description="Inspect Linux service state and configuration.",
    )

    _IP_ADDRESS_COMMAND = (
        "ip",
        "-j",
        "address",
        "show",
    )

    _SYSTEMCTL_COMMAND = (
        "systemctl",
        "show",
        "--type=service",
        "--all",
        "--no-pager",
        "--no-legend",
        "--property=Id,Description,ActiveState,"
        "SubState,UnitFileState",
    )

    def __init__(
        self,
        command_runner: CommandRunner | None = None,
        proc_root: Path | str = "/proc",
        sys_root: Path | str = "/sys",
        etc_root: Path | str = "/etc",
    ) -> None:
        self._command_runner = command_runner or self._run_command
        self._proc_root = Path(proc_root)
        self._sys_root = Path(sys_root)
        self._etc_root = Path(etc_root)

    @property
    def name(self) -> str:
        return "linux-system"

    @property
    def supported_capabilities(
        self,
    ) -> tuple[SystemCapability, ...]:
        return (
            self._PROCESS_CAPABILITY,
            self._SYSTEM_CAPABILITY,
            self._NETWORK_CAPABILITY,
            self._SERVICE_CAPABILITY,
        )

    def execute(
        self,
        request: SystemCapabilityRequest,
    ) -> SystemCapabilityResult:
        if not isinstance(request, SystemCapabilityRequest):
            raise TypeError(
                "LinuxSystemCapabilityBackend request must be "
                "a SystemCapabilityRequest."
            )

        if platform.system() != "Linux":
            return self._failure(
                request.capability.name,
                SystemCapabilityResultKind.UNSUPPORTED,
                "Linux system backend is running on a non-Linux platform.",
            )

        handlers = {
            SystemCapabilityName.PROCESS_INSPECT:
                self._inspect_processes,
            SystemCapabilityName.SYSTEM_INSPECT:
                self._inspect_system,
            SystemCapabilityName.NETWORK_INSPECT:
                self._inspect_network,
            SystemCapabilityName.SERVICE_INSPECT:
                self._inspect_services,
        }

        handler = handlers.get(request.capability.name)

        if handler is None:
            return self._failure(
                request.capability.name,
                SystemCapabilityResultKind.UNSUPPORTED,
                "Capability is not supported by the Linux system backend.",
            )

        try:
            evidence = handler(request.parameters)
        except FileNotFoundError as exc:
            return self._failure(
                request.capability.name,
                SystemCapabilityResultKind.UNAVAILABLE,
                f"Linux inspection resource is unavailable: {exc}",
            )
        except PermissionError as exc:
            return self._failure(
                request.capability.name,
                SystemCapabilityResultKind.UNAVAILABLE,
                f"Linux inspection resource is inaccessible: {exc}",
            )
        except (
            OSError,
            subprocess.SubprocessError,
            ValueError,
            TypeError,
            KeyError,
        ) as exc:
            return self._failure(
                request.capability.name,
                SystemCapabilityResultKind.FAILED,
                f"Linux capability inspection failed: {exc}",
            )

        return SystemCapabilityResult(
            capability=request.capability.name,
            kind=SystemCapabilityResultKind.SUCCESS,
            evidence=evidence,
            observed_at=datetime.now(timezone.utc),
            backend_name=self.name,
        )

    def _inspect_processes(
        self,
        parameters: Any,
    ) -> dict[str, Any]:
        self._validate_mapping(parameters)

        allowed = {"pid", "limit"}
        unknown = set(parameters.keys()) - allowed

        if unknown:
            names = ", ".join(
                sorted(str(value) for value in unknown)
            )
            raise ValueError(
                f"Unsupported process inspection parameters: {names}"
            )

        pid = parameters.get("pid")
        limit = parameters.get("limit")

        if pid is not None:
            self._validate_positive_or_zero_integer(
                pid,
                "Process inspection pid",
            )

        if limit is not None:
            self._validate_positive_integer(
                limit,
                "Process inspection limit",
            )

        if pid is not None:
            process_ids = [pid]
        else:
            process_ids = self._discover_process_ids()

        if limit is not None:
            process_ids = process_ids[:limit]

        processes: list[ProcessInspection] = []

        for process_id in process_ids:
            process = self._read_process(process_id)

            if process is not None:
                processes.append(process)

        return {
            "processes": tuple(processes),
        }

    def _discover_process_ids(self) -> list[int]:
        process_ids: list[int] = []

        for entry in self._proc_root.iterdir():
            if not entry.is_dir():
                continue

            if not entry.name.isdigit():
                continue

            process_ids.append(int(entry.name))

        process_ids.sort()

        return process_ids

    def _read_process(
        self,
        process_id: int,
    ) -> ProcessInspection | None:
        process_root = self._proc_root / str(process_id)

        try:
            name = self._read_process_name(process_root)
            state = self._read_process_state(process_root)
            executable = self._read_process_executable(process_root)
            memory_bytes = self._read_process_memory(process_root)
            started_at = self._read_process_start_time(
                process_root
            )
        except FileNotFoundError:
            return None
        except PermissionError:
            return ProcessInspection(
                pid=process_id,
            )

        return ProcessInspection(
            pid=process_id,
            name=name,
            executable=executable,
            state=state,
            started_at=started_at,
            memory_bytes=memory_bytes,
        )

    @staticmethod
    def _read_process_name(
        process_root: Path,
    ) -> str | None:
        value = (
            process_root / "comm"
        ).read_text(
            encoding="utf-8",
            errors="replace",
        ).strip()

        return value or None

    @staticmethod
    def _read_process_state(
        process_root: Path,
    ) -> str | None:
        value = (
            process_root / "stat"
        ).read_text(
            encoding="utf-8",
            errors="replace",
        )

        closing = value.rfind(")")

        if closing == -1:
            return None

        fields = value[closing + 1:].strip().split()

        if not fields:
            return None

        state = fields[0]

        return state or None

    @staticmethod
    def _read_process_executable(
        process_root: Path,
    ) -> str | None:
        try:
            return os.readlink(process_root / "exe")
        except FileNotFoundError:
            return None

    @staticmethod
    def _read_process_memory(
        process_root: Path,
    ) -> int | None:
        path = process_root / "status"

        for line in path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            if not line.startswith("VmRSS:"):
                continue

            fields = line.split()

            if len(fields) < 2:
                return None

            try:
                value = int(fields[1])
            except ValueError:
                return None

            return value * 1024

        return None

    def _read_process_start_time(
        self,
        process_root: Path,
    ) -> datetime | None:
        stat = (
            process_root / "stat"
        ).read_text(
            encoding="utf-8",
            errors="replace",
        )

        closing = stat.rfind(")")

        if closing == -1:
            return None

        fields = stat[closing + 1:].strip().split()

        if len(fields) < 20:
            return None

        try:
            start_ticks = int(fields[19])
        except ValueError:
            return None

        uptime = self._read_uptime()

        if uptime is None:
            return None

        clock_ticks = self._get_clock_ticks()

        if clock_ticks is None or clock_ticks <= 0:
            return None

        elapsed_since_boot = start_ticks / clock_ticks

        boot_timestamp = (
            datetime.now(timezone.utc).timestamp() - uptime
        )

        return datetime.fromtimestamp(
            boot_timestamp + elapsed_since_boot,
            timezone.utc,
        )

    @staticmethod
    def _get_clock_ticks() -> int | None:
        sysconf = getattr(os, "sysconf", None)

        if sysconf is None:
            return None

        sysconf_names = getattr(os, "sysconf_names", {})

        clock_ticks_name = sysconf_names.get("SC_CLK_TCK")

        if clock_ticks_name is None:
            return None

        try:
            return int(sysconf(clock_ticks_name))
        except (OSError, ValueError, TypeError):
            return None

    def _inspect_system(
        self,
        parameters: Any,
    ) -> dict[str, Any]:
        self._validate_mapping(parameters)

        if parameters:
            raise ValueError(
                "Linux system inspection does not accept parameters."
            )

        os_release = self._read_os_release()

        operating_system = (
            os_release.get("PRETTY_NAME")
            or os_release.get("NAME")
        )

        operating_system_version = (
            os_release.get("VERSION_ID")
            or os_release.get("VERSION")
        )

        is_virtual_machine, hypervisor = (
            self._detect_virtualization()
        )

        system = SystemInspection(
            hostname=socket.gethostname(),
            operating_system=operating_system,
            operating_system_version=operating_system_version,
            architecture=platform.machine(),
            kernel=platform.release(),
            uptime_seconds=self._read_uptime(),
            is_virtual_machine=is_virtual_machine,
            hypervisor=hypervisor,
        )

        return {
            "system": system,
        }

    def _read_os_release(self) -> dict[str, str]:
        path = self._etc_root / "os-release"

        values: dict[str, str] = {}

        for line in path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)

            key = key.strip()
            value = value.strip()

            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in {"\"", "'"}
            ):
                value = value[1:-1]

            values[key] = value

        return values

    def _read_uptime(self) -> float | None:
        path = self._proc_root / "uptime"

        fields = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).split()

        if not fields:
            return None

        try:
            uptime = float(fields[0])
        except ValueError:
            return None

        if uptime < 0:
            return None

        return uptime

    def _detect_virtualization(
        self,
    ) -> tuple[bool | None, str | None]:
        indicators = " ".join(
            value
            for value in (
                self._read_optional_file(
                    self._sys_root
                    / "class"
                    / "dmi"
                    / "id"
                    / "product_name"
                ),
                self._read_optional_file(
                    self._sys_root
                    / "class"
                    / "dmi"
                    / "id"
                    / "sys_vendor"
                ),
                self._read_optional_file(
                    self._sys_root
                    / "class"
                    / "dmi"
                    / "id"
                    / "product_version"
                ),
            )
            if value
        ).lower()

        markers = (
            ("vmware", "VMware"),
            ("virtualbox", "VirtualBox"),
            ("kvm", "KVM"),
            ("qemu", "QEMU"),
            ("xen", "Xen"),
            ("microsoft corporation", "Hyper-V"),
            ("virtual machine", "Hyper-V"),
        )

        for marker, hypervisor in markers:
            if marker in indicators:
                return True, hypervisor

        if indicators:
            return False, None

        return None, None

    def _inspect_network(
        self,
        parameters: Any,
    ) -> dict[str, Any]:
        self._validate_mapping(parameters)

        allowed = {"interface", "limit"}
        unknown = set(parameters.keys()) - allowed

        if unknown:
            names = ", ".join(
                sorted(str(value) for value in unknown)
            )
            raise ValueError(
                f"Unsupported network inspection parameters: {names}"
            )

        interface_filter = parameters.get("interface")
        limit = parameters.get("limit")

        if interface_filter is not None:
            if not isinstance(interface_filter, str):
                raise TypeError(
                    "Network inspection interface must be a string."
                )

            if not interface_filter.strip():
                raise ValueError(
                    "Network inspection interface must not be empty."
                )

        if limit is not None:
            self._validate_positive_integer(
                limit,
                "Network inspection limit",
            )

        address_map = self._read_ip_addresses()

        interfaces = self._read_network_interfaces(
            address_map
        )

        if interface_filter is not None:
            interfaces = [
                interface
                for interface in interfaces
                if interface.name == interface_filter
            ]

        if limit is not None:
            interfaces = interfaces[:limit]

        network = NetworkInspection(
            interfaces=tuple(interfaces),
            routes=tuple(self._read_network_routes()),
            dns_servers=tuple(self._read_dns_servers()),
        )

        return {
            "network": network,
        }

    def _read_network_interfaces(
        self,
        address_map: dict[str, tuple[str, ...]],
    ) -> list[NetworkInterfaceInspection]:
        net_root = self._sys_root / "class" / "net"

        interfaces = []

        for interface_root in sorted(
            net_root.iterdir(),
            key=lambda path: path.name,
        ):
            name = interface_root.name

            interfaces.append(
                NetworkInterfaceInspection(
                    name=name,
                    state=self._read_optional_file(
                        interface_root / "operstate"
                    ),
                    addresses=address_map.get(
                        name,
                        (),
                    ),
                    mac_address=self._read_optional_file(
                        interface_root / "address"
                    ),
                    received_bytes=self._read_optional_int(
                        interface_root
                        / "statistics"
                        / "rx_bytes"
                    ),
                    transmitted_bytes=self._read_optional_int(
                        interface_root
                        / "statistics"
                        / "tx_bytes"
                    ),
                )
            )

        return interfaces

    def _read_ip_addresses(
        self,
    ) -> dict[str, tuple[str, ...]]:
        raw = self._command_runner(
            self._IP_ADDRESS_COMMAND
        )

        data = json.loads(raw)

        if not isinstance(data, list):
            raise ValueError(
                "Linux ip address output must be a JSON list."
            )

        address_map: dict[str, tuple[str, ...]] = {}

        for interface in data:
            if not isinstance(interface, dict):
                continue

            interface_name = interface.get("ifname")

            if not isinstance(interface_name, str):
                continue

            addresses: list[str] = []

            addr_info = interface.get("addr_info", [])

            if not isinstance(addr_info, list):
                raise ValueError(
                    "Linux ip address addr_info must be a list."
                )

            for address in addr_info:
                if not isinstance(address, dict):
                    continue

                local = address.get("local")

                if isinstance(local, str) and local:
                    addresses.append(local)

            address_map[interface_name] = tuple(addresses)

        return address_map

    def _read_network_routes(
        self,
    ) -> list[NetworkRouteInspection]:
        path = self._proc_root / "net" / "route"

        routes = []

        lines = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()

        for line in lines[1:]:
            fields = line.split()

            if len(fields) < 8:
                continue

            routes.append(
                NetworkRouteInspection(
                    destination=self._ipv4_from_proc_hex(
                        fields[1]
                    ),
                    gateway=self._ipv4_from_proc_hex(
                        fields[2]
                    ),
                    interface=fields[0],
                )
            )

        return routes

    @staticmethod
    def _ipv4_from_proc_hex(value: str) -> str:
        if len(value) != 8:
            return value

        try:
            raw = bytes.fromhex(value)

            if len(raw) != 4:
                return value

            return ".".join(
                str(part)
                for part in raw[::-1]
            )
        except ValueError:
            return value

    def _read_dns_servers(self) -> list[str]:
        path = self._etc_root / "resolv.conf"

        servers = []

        for line in path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            fields = line.split()

            if len(fields) >= 2 and fields[0] == "nameserver":
                address = fields[1]

                if address not in servers:
                    servers.append(address)

        return servers

    def _inspect_services(
        self,
        parameters: Any,
    ) -> dict[str, Any]:
        self._validate_mapping(parameters)

        allowed = {"name", "state", "limit"}
        unknown = set(parameters.keys()) - allowed

        if unknown:
            names = ", ".join(
                sorted(str(value) for value in unknown)
            )
            raise ValueError(
                f"Unsupported service inspection parameters: {names}"
            )

        name_filter = parameters.get("name")
        state_filter = parameters.get("state")
        limit = parameters.get("limit")

        if name_filter is not None:
            if not isinstance(name_filter, str):
                raise TypeError(
                    "Service inspection name must be a string."
                )

            if not name_filter.strip():
                raise ValueError(
                    "Service inspection name must not be empty."
                )

        if state_filter is not None:
            if not isinstance(state_filter, str):
                raise TypeError(
                    "Service inspection state must be a string."
                )

            if not state_filter.strip():
                raise ValueError(
                    "Service inspection state must not be empty."
                )

        if limit is not None:
            self._validate_positive_integer(
                limit,
                "Service inspection limit",
            )

        services = self._parse_systemctl_services(
            self._command_runner(
                self._SYSTEMCTL_COMMAND
            )
        )

        if name_filter is not None:
            services = [
                service
                for service in services
                if service.name == name_filter
            ]

        if state_filter is not None:
            services = [
                service
                for service in services
                if service.state == state_filter
            ]

        if limit is not None:
            services = services[:limit]

        return {
            "services": tuple(services),
        }

    @staticmethod
    def _parse_systemctl_services(
        raw: str,
    ) -> list[ServiceInspection]:
        services = []
        current: dict[str, str] = {}

        def flush() -> None:
            if not current:
                return

            service_id = current.get("Id")

            if not service_id:
                current.clear()
                return

            services.append(
                ServiceInspection(
                    name=service_id,
                    display_name=current.get("Description"),
                    state=current.get("ActiveState"),
                    startup_type=current.get("UnitFileState"),
                    description=current.get("Description"),
                )
            )

            current.clear()

        for line in raw.splitlines():
            line = line.strip()

            if not line:
                flush()
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)

            if key == "Id" and current:
                flush()

            current[key] = value

        flush()

        return services

    @staticmethod
    def _validate_mapping(parameters: Any) -> None:
        if not hasattr(parameters, "keys"):
            raise TypeError(
                "Capability parameters must be a mapping."
            )

    @staticmethod
    def _validate_positive_integer(
        value: Any,
        label: str,
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{label} must be an integer.")

        if value <= 0:
            raise ValueError(
                f"{label} must be greater than zero."
            )

    @staticmethod
    def _validate_positive_or_zero_integer(
        value: Any,
        label: str,
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{label} must be an integer.")

        if value < 0:
            raise ValueError(
                f"{label} must not be negative."
            )

    @staticmethod
    def _read_optional_file(
        path: Path,
    ) -> str | None:
        try:
            value = path.read_text(
                encoding="utf-8",
                errors="replace",
            ).strip()
        except FileNotFoundError:
            return None

        return value or None

    @staticmethod
    def _read_optional_int(
        path: Path,
    ) -> int | None:
        value = LinuxSystemCapabilityBackend._read_optional_file(
            path
        )

        if value is None:
            return None

        try:
            result = int(value)
        except ValueError:
            return None

        return result if result >= 0 else None

    @staticmethod
    def _run_command(
        command: tuple[str, ...],
    ) -> str:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

        return completed.stdout

    def _failure(
        self,
        capability: SystemCapabilityName,
        kind: SystemCapabilityResultKind,
        error: str,
    ) -> SystemCapabilityResult:
        return SystemCapabilityResult(
            capability=capability,
            kind=kind,
            error=error,
            backend_name=self.name,
        )