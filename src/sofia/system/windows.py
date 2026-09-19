from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
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


PowerShellRunner = Callable[[str], str]


class WindowsSystemCapabilityBackend(SystemCapabilityBackend):
    """Windows implementation of read-only system inspection capabilities."""

    _PROCESS_CAPABILITY = SystemCapability(
        name=SystemCapabilityName.PROCESS_INSPECT,
        description="Inspect running Windows processes.",
    )

    _SYSTEM_CAPABILITY = SystemCapability(
        name=SystemCapabilityName.SYSTEM_INSPECT,
        description="Inspect Windows operating-system state.",
    )

    _NETWORK_CAPABILITY = SystemCapability(
        name=SystemCapabilityName.NETWORK_INSPECT,
        description="Inspect Windows network interfaces, routes, and DNS.",
    )

    _SERVICE_CAPABILITY = SystemCapability(
        name=SystemCapabilityName.SERVICE_INSPECT,
        description="Inspect Windows service state and configuration.",
    )

    def __init__(
        self,
        powershell_runner: PowerShellRunner | None = None,
    ) -> None:
        self._powershell_runner = (
            powershell_runner or self._run_powershell
        )

    @property
    def name(self) -> str:
        return "windows-system"

    @property
    def supported_capabilities(self) -> tuple[SystemCapability, ...]:
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
                "WindowsSystemCapabilityBackend request must be "
                "a SystemCapabilityRequest."
            )

        if platform.system() != "Windows":
            return self._failure(
                request.capability.name,
                SystemCapabilityResultKind.UNSUPPORTED,
                "Windows system backend is running on a non-Windows platform.",
            )

        handlers = {
            SystemCapabilityName.PROCESS_INSPECT: self._inspect_processes,
            SystemCapabilityName.SYSTEM_INSPECT: self._inspect_system,
            SystemCapabilityName.NETWORK_INSPECT: self._inspect_network,
            SystemCapabilityName.SERVICE_INSPECT: self._inspect_services,
        }

        handler = handlers.get(request.capability.name)

        if handler is None:
            return self._failure(
                request.capability.name,
                SystemCapabilityResultKind.UNSUPPORTED,
                "Capability is not supported by the Windows system backend.",
            )

        try:
            evidence = handler(request.parameters)
        except FileNotFoundError as exc:
            return self._failure(
                request.capability.name,
                SystemCapabilityResultKind.UNAVAILABLE,
                f"PowerShell is unavailable: {exc}",
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
                f"Windows capability inspection failed: {exc}",
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
        if not hasattr(parameters, "keys"):
            raise TypeError(
                "Process inspection parameters must be a mapping."
            )

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
            if isinstance(pid, bool) or not isinstance(pid, int):
                raise TypeError(
                    "Process inspection pid must be an integer."
                )

            if pid < 0:
                raise ValueError(
                    "Process inspection pid must not be negative."
                )

        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise TypeError(
                    "Process inspection limit must be an integer."
                )

            if limit <= 0:
                raise ValueError(
                    "Process inspection limit must be greater than zero."
                )

        command = (
            "Get-CimInstance Win32_Process | "
            "Select-Object "
            "ProcessId,Name,ExecutablePath,CreationDate,WorkingSetSize | "
            "ConvertTo-Json -Compress"
        )

        raw = self._powershell_runner(command)
        payload = json.loads(raw) if raw.strip() else []

        if isinstance(payload, dict):
            payload = [payload]

        if not isinstance(payload, list):
            raise ValueError(
                "PowerShell returned an invalid process payload."
            )

        result: list[ProcessInspection] = []

        for item in payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "PowerShell returned an invalid process entry."
                )

            process_id = item.get("ProcessId")

            if process_id is None:
                continue

            try:
                process_id = int(process_id)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "PowerShell returned an invalid process identifier."
                ) from exc

            if pid is not None and process_id != pid:
                continue

            started_at = self._parse_wmi_datetime(
                item.get("CreationDate")
            )

            memory_bytes = item.get("WorkingSetSize")

            if memory_bytes is not None:
                memory_bytes = int(memory_bytes)

            result.append(
                ProcessInspection(
                    pid=process_id,
                    name=self._optional_string(
                        item.get("Name")
                    ),
                    executable=self._optional_string(
                        item.get("ExecutablePath")
                    ),
                    started_at=started_at,
                    memory_bytes=memory_bytes,
                )
            )

            if limit is not None and len(result) >= limit:
                break

        return {"processes": result}

    def _inspect_system(
        self,
        parameters: Any,
    ) -> dict[str, Any]:
        self._require_no_parameters(
            parameters,
            "System inspection",
        )

        command = (
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "$cs = Get-CimInstance Win32_ComputerSystem; "
            "$product = Get-CimInstance Win32_ComputerSystemProduct; "
            "[PSCustomObject]@{"
            "OS = [PSCustomObject]@{"
            "Caption = $os.Caption;"
            "Version = $os.Version;"
            "BuildNumber = $os.BuildNumber;"
            "LastBootUpTime = $os.LastBootUpTime;"
            "Architecture = $os.OSArchitecture"
            "};"
            "Computer = [PSCustomObject]@{"
            "Name = $cs.Name;"
            "Manufacturer = $cs.Manufacturer;"
            "Model = $cs.Model;"
            "HypervisorPresent = $cs.HypervisorPresent;"
            "SystemType = $cs.SystemType"
            "};"
            "Product = [PSCustomObject]@{"
            "Vendor = $product.Vendor;"
            "Version = $product.Version;"
            "Name = $product.Name"
            "}"
            "} | ConvertTo-Json -Compress"
        )

        raw = self._powershell_runner(command)

        payload = json.loads(raw) if raw.strip() else None

        if not isinstance(payload, dict):
            raise ValueError(
                "PowerShell returned an invalid system payload."
            )

        operating_system = payload.get("OS")
        computer = payload.get("Computer")
        product = payload.get("Product")

        if not isinstance(operating_system, dict):
            raise ValueError(
                "PowerShell returned invalid operating-system data."
            )

        if not isinstance(computer, dict):
            raise ValueError(
                "PowerShell returned invalid computer data."
            )

        if not isinstance(product, dict):
            raise ValueError(
                "PowerShell returned invalid product data."
            )

        last_boot = self._parse_wmi_datetime(
            operating_system.get("LastBootUpTime")
        )

        uptime_seconds = None

        if last_boot is not None:
            now = datetime.now(timezone.utc)
            uptime_seconds = max(
                0.0,
                (now - last_boot).total_seconds(),
            )

        is_virtual_machine = self._detect_virtual_machine(
            computer,
            product,
        )

        hypervisor = self._detect_hypervisor(
            computer,
            product,
            is_virtual_machine,
        )

        inspection = SystemInspection(
            hostname=self._optional_string(
                computer.get("Name")
            ),
            operating_system=self._optional_string(
                operating_system.get("Caption")
            ),
            operating_system_version=(
                self._build_os_version(
                    operating_system.get("Version"),
                    operating_system.get("BuildNumber"),
                )
            ),
            architecture=self._optional_string(
                operating_system.get("Architecture")
            ),
            kernel=self._optional_string(
                operating_system.get("Version")
            ),
            uptime_seconds=uptime_seconds,
            is_virtual_machine=is_virtual_machine,
            hypervisor=hypervisor,
        )

        return {"system": inspection}

    def _inspect_network(
        self,
        parameters: Any,
    ) -> dict[str, Any]:
        if not hasattr(parameters, "keys"):
            raise TypeError(
                "Network inspection parameters must be a mapping."
            )

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
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise TypeError(
                    "Network inspection limit must be an integer."
                )

            if limit <= 0:
                raise ValueError(
                    "Network inspection limit must be greater than zero."
                )

        command = (
            "$interfaces = Get-NetAdapter | "
            "Select-Object Name,Status,MacAddress; "
            "$addresses = Get-NetIPAddress | "
            "Select-Object InterfaceAlias,IPAddress; "
            "$statistics = Get-NetAdapterStatistics | "
            "Select-Object Name,ReceivedBytes,SentBytes; "
            "$routes = Get-NetRoute | "
            "Select-Object DestinationPrefix,NextHop,InterfaceAlias; "
            "$dns = Get-DnsClientServerAddress | "
            "Select-Object InterfaceAlias,ServerAddresses; "
            "[PSCustomObject]@{"
            "Interfaces = @($interfaces);"
            "Addresses = @($addresses);"
            "Statistics = @($statistics);"
            "Routes = @($routes);"
            "Dns = @($dns)"
            "} | ConvertTo-Json -Depth 6 -Compress"
        )

        raw = self._powershell_runner(command)

        payload = json.loads(raw) if raw.strip() else None

        if not isinstance(payload, dict):
            raise ValueError(
                "PowerShell returned an invalid network payload."
            )

        interfaces = self._as_list(
            payload.get("Interfaces")
        )
        addresses = self._as_list(
            payload.get("Addresses")
        )
        statistics = self._as_list(
            payload.get("Statistics")
        )
        routes = self._as_list(
            payload.get("Routes")
        )
        dns_entries = self._as_list(
            payload.get("Dns")
        )

        address_map: dict[str, list[str]] = {}

        for item in addresses:
            if not isinstance(item, dict):
                raise ValueError(
                    "PowerShell returned an invalid network address."
                )

            alias = item.get("InterfaceAlias")
            address = item.get("IPAddress")

            if alias is None or address is None:
                continue

            alias = self._require_string(
                alias,
                "InterfaceAlias",
            )
            address = self._require_string(
                address,
                "IPAddress",
            )

            address_map.setdefault(alias, []).append(address)

        statistics_map: dict[str, dict[str, int | None]] = {}

        for item in statistics:
            if not isinstance(item, dict):
                raise ValueError(
                    "PowerShell returned invalid network statistics."
                )

            name = item.get("Name")

            if name is None:
                continue

            name = self._require_string(name, "Name")

            statistics_map[name] = {
                "received": self._optional_nonnegative_int(
                    item.get("ReceivedBytes")
                ),
                "transmitted": self._optional_nonnegative_int(
                    item.get("SentBytes")
                ),
            }

        result: list[NetworkInterfaceInspection] = []

        for item in interfaces:
            if not isinstance(item, dict):
                raise ValueError(
                    "PowerShell returned an invalid network interface."
                )

            name = self._require_string(
                item.get("Name"),
                "Name",
            )

            if (
                interface_filter is not None
                and name != interface_filter
            ):
                continue

            statistics_entry = statistics_map.get(
                name,
                {},
            )

            result.append(
                NetworkInterfaceInspection(
                    name=name,
                    state=self._optional_string(
                        item.get("Status")
                    ),
                    addresses=tuple(
                        address_map.get(name, [])
                    ),
                    mac_address=self._optional_string(
                        item.get("MacAddress")
                    ),
                    received_bytes=statistics_entry.get(
                        "received"
                    ),
                    transmitted_bytes=statistics_entry.get(
                        "transmitted"
                    ),
                )
            )

            if limit is not None and len(result) >= limit:
                break

        route_result: list[NetworkRouteInspection] = []

        for item in routes:
            if not isinstance(item, dict):
                raise ValueError(
                    "PowerShell returned an invalid network route."
                )

            destination = item.get("DestinationPrefix")

            if destination is None:
                continue

            route_result.append(
                NetworkRouteInspection(
                    destination=self._require_string(
                        destination,
                        "DestinationPrefix",
                    ),
                    gateway=self._optional_string(
                        item.get("NextHop")
                    ),
                    interface=self._optional_string(
                        item.get("InterfaceAlias")
                    ),
                )
            )

        dns_servers: list[str] = []

        for item in dns_entries:
            if not isinstance(item, dict):
                raise ValueError(
                    "PowerShell returned invalid DNS data."
                )

            server_addresses = item.get(
                "ServerAddresses"
            )

            if server_addresses is None:
                continue

            if isinstance(server_addresses, str):
                server_addresses = [server_addresses]

            if not isinstance(server_addresses, list):
                raise ValueError(
                    "PowerShell returned invalid DNS server data."
                )

            for address in server_addresses:
                dns_servers.append(
                    self._require_string(
                        address,
                        "ServerAddress",
                    )
                )

        inspection = NetworkInspection(
            interfaces=tuple(result),
            routes=tuple(route_result),
            dns_servers=tuple(dict.fromkeys(dns_servers)),
        )

        return {"network": inspection}

    def _inspect_services(
        self,
        parameters: Any,
    ) -> dict[str, Any]:
        if not hasattr(parameters, "keys"):
            raise TypeError(
                "Service inspection parameters must be a mapping."
            )

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
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise TypeError(
                    "Service inspection limit must be an integer."
                )

            if limit <= 0:
                raise ValueError(
                    "Service inspection limit must be greater than zero."
                )

        command = (
            "Get-CimInstance Win32_Service | "
            "Select-Object "
            "Name,DisplayName,State,StartMode,Description | "
            "ConvertTo-Json -Compress"
        )

        raw = self._powershell_runner(command)

        payload = json.loads(raw) if raw.strip() else []

        if isinstance(payload, dict):
            payload = [payload]

        if not isinstance(payload, list):
            raise ValueError(
                "PowerShell returned an invalid service payload."
            )

        result: list[ServiceInspection] = []

        for item in payload:
            if not isinstance(item, dict):
                raise ValueError(
                    "PowerShell returned an invalid service entry."
                )

            name = item.get("Name")

            if name is None:
                continue

            name = self._require_string(
                name,
                "Name",
            )

            if (
                name_filter is not None
                and name != name_filter
            ):
                continue

            state = self._optional_string(
                item.get("State")
            )

            if (
                state_filter is not None
                and state != state_filter
            ):
                continue

            result.append(
                ServiceInspection(
                    name=name,
                    display_name=self._optional_string(
                        item.get("DisplayName")
                    ),
                    state=state,
                    startup_type=self._optional_string(
                        item.get("StartMode")
                    ),
                    description=self._optional_string(
                        item.get("Description")
                    ),
                )
            )

            if limit is not None and len(result) >= limit:
                break

        return {"services": result}

    @staticmethod
    def _require_no_parameters(
        parameters: Any,
        operation: str,
    ) -> None:
        if not hasattr(parameters, "keys"):
            raise TypeError(
                f"{operation} parameters must be a mapping."
            )

        if parameters:
            names = ", ".join(
                sorted(str(value) for value in parameters.keys())
            )
            raise ValueError(
                f"{operation} does not accept parameters: {names}"
            )

    @staticmethod
    def _as_list(
        value: Any,
    ) -> list[Any]:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            return [value]

        raise ValueError(
            "PowerShell returned a value that is neither "
            "an object nor an array."
        )

    @staticmethod
    def _build_os_version(
        version: Any,
        build: Any,
    ) -> str | None:
        version_value = (
            version.strip()
            if isinstance(version, str) and version.strip()
            else None
        )

        build_value = (
            build.strip()
            if isinstance(build, str) and build.strip()
            else None
        )

        if version_value and build_value:
            return f"{version_value} (build {build_value})"

        return version_value or build_value

    @staticmethod
    def _detect_virtual_machine(
        computer: dict[str, Any],
        product: dict[str, Any],
    ) -> bool | None:
        manufacturer = str(
            computer.get("Manufacturer") or ""
        ).lower()

        model = str(
            computer.get("Model") or ""
        ).lower()

        vendor = str(
            product.get("Vendor") or ""
        ).lower()

        product_name = str(
            product.get("Name") or ""
        ).lower()

        virtual_markers = (
            "vmware",
            "virtualbox",
            "kvm",
            "qemu",
            "xen",
            "microsoft corporation",
        )

        combined = " ".join(
            (
                manufacturer,
                model,
                vendor,
                product_name,
            )
        )

        if any(marker in combined for marker in virtual_markers):
            return True

        hypervisor_present = computer.get(
            "HypervisorPresent"
        )

        if isinstance(hypervisor_present, bool):
            return False

        return None

    @staticmethod
    def _detect_hypervisor(
        computer: dict[str, Any],
        product: dict[str, Any],
        is_virtual_machine: bool | None,
    ) -> str | None:
        if is_virtual_machine is not True:
            return None

        combined = " ".join(
            str(value or "").lower()
            for value in (
                computer.get("Manufacturer"),
                computer.get("Model"),
                product.get("Vendor"),
                product.get("Name"),
            )
        )

        if "vmware" in combined:
            return "VMware"

        if "virtualbox" in combined:
            return "VirtualBox"

        if "kvm" in combined:
            return "KVM"

        if "qemu" in combined:
            return "QEMU"

        if "xen" in combined:
            return "Xen"

        if "microsoft corporation" in combined:
            return "Hyper-V"

        return None

    @staticmethod
    def _parse_wmi_datetime(
        value: Any,
    ) -> datetime | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise TypeError(
                "WMI datetime must be a string or None."
            )

        normalized = value[:14]

        if len(normalized) != 14 or not normalized.isdigit():
            raise ValueError(
                "Invalid WMI datetime."
            )

        return datetime.strptime(
            normalized,
            "%Y%m%d%H%M%S",
        ).replace(tzinfo=timezone.utc)

    @staticmethod
    def _optional_string(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise TypeError(
                "Windows string fields must be strings."
            )

        return value

    @staticmethod
    def _require_string(
        value: Any,
        field_name: str,
    ) -> str:
        if not isinstance(value, str):
            raise TypeError(
                f"Windows {field_name} must be a string."
            )

        if not value.strip():
            raise ValueError(
                f"Windows {field_name} must not be empty."
            )

        return value

    @staticmethod
    def _optional_nonnegative_int(
        value: Any,
    ) -> int | None:
        if value is None:
            return None

        if isinstance(value, bool):
            raise TypeError(
                "Windows numeric values must not be boolean."
            )

        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "Windows numeric value must be an integer."
            ) from exc

        if result < 0:
            raise ValueError(
                "Windows numeric value must not be negative."
            )

        return result

    @staticmethod
    def _run_powershell(
        command: str,
    ) -> str:
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
            check=True,
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
        )