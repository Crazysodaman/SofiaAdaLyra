from __future__ import annotations

import json
from datetime import datetime

import pytest

from sofia.system.model import (
    SystemCapability,
    SystemCapabilityName,
    SystemCapabilityRequest,
    SystemCapabilityResultKind,
)
from sofia.system.windows import WindowsSystemCapabilityBackend


def _request(
    capability: SystemCapabilityName,
    parameters: dict[str, object] | None = None,
) -> SystemCapabilityRequest:
    descriptions = {
        SystemCapabilityName.PROCESS_INSPECT:
            "Inspect running Windows processes.",
        SystemCapabilityName.SYSTEM_INSPECT:
            "Inspect Windows operating-system state.",
        SystemCapabilityName.NETWORK_INSPECT:
            "Inspect Windows network interfaces, routes, and DNS.",
        SystemCapabilityName.SERVICE_INSPECT:
            "Inspect Windows service state and configuration.",
    }

    return SystemCapabilityRequest(
        capability=SystemCapability(
            name=capability,
            description=descriptions[capability],
        ),
        parameters=parameters or {},
    )


def _process_payload() -> str:
    return json.dumps(
        [
            {
                "ProcessId": 1234,
                "Name": "python.exe",
                "ExecutablePath": (
                    "C:\\Python\\python.exe"
                ),
                "CreationDate": (
                    "20260919080000.000000-300"
                ),
                "WorkingSetSize": 4096,
            },
            {
                "ProcessId": 5678,
                "Name": "notepad.exe",
                "ExecutablePath": (
                    "C:\\Windows\\notepad.exe"
                ),
                "CreationDate": None,
                "WorkingSetSize": 8192,
            },
        ]
    )


def _system_payload() -> str:
    return json.dumps(
        {
            "OS": {
                "Caption": "Microsoft Windows 11 Pro",
                "Version": "10.0.26100",
                "BuildNumber": "26100",
                "LastBootUpTime": (
                    "20260919060000.000000-300"
                ),
                "Architecture": "64-bit",
            },
            "Computer": {
                "Name": "VENUS",
                "Manufacturer": "ASUSTeK COMPUTER INC.",
                "Model": "ROG STRIX",
                "HypervisorPresent": False,
                "SystemType": "x64-based PC",
            },
            "Product": {
                "Vendor": "ASUSTeK COMPUTER INC.",
                "Version": "1.0",
                "Name": "System Product Name",
            },
        }
    )


def _network_payload() -> str:
    return json.dumps(
        {
            "Interfaces": [
                {
                    "Name": "Ethernet",
                    "Status": "Up",
                    "MacAddress": "00-11-22-33-44-55",
                },
                {
                    "Name": "Wi-Fi",
                    "Status": "Disconnected",
                    "MacAddress": "66-77-88-99-AA-BB",
                },
            ],
            "Addresses": [
                {
                    "InterfaceAlias": "Ethernet",
                    "IPAddress": "192.168.1.55",
                },
                {
                    "InterfaceAlias": "Ethernet",
                    "IPAddress": "fe80::1234",
                },
            ],
            "Statistics": [
                {
                    "Name": "Ethernet",
                    "ReceivedBytes": 100000,
                    "SentBytes": 200000,
                },
                {
                    "Name": "Wi-Fi",
                    "ReceivedBytes": 300000,
                    "SentBytes": 400000,
                },
            ],
            "Routes": [
                {
                    "DestinationPrefix": "0.0.0.0/0",
                    "NextHop": "192.168.1.254",
                    "InterfaceAlias": "Ethernet",
                },
            ],
            "Dns": [
                {
                    "InterfaceAlias": "Ethernet",
                    "ServerAddresses": [
                        "192.168.1.254",
                        "1.1.1.1",
                    ],
                },
            ],
        }
    )


def _service_payload() -> str:
    return json.dumps(
        [
            {
                "Name": "Spooler",
                "DisplayName": "Print Spooler",
                "State": "Running",
                "StartMode": "Auto",
                "Description": "Loads files to memory for later printing.",
            },
            {
                "Name": "wuauserv",
                "DisplayName": "Windows Update",
                "State": "Stopped",
                "StartMode": "Manual",
                "Description": "Enables detection and installation of updates.",
            },
        ]
    )


def test_windows_backend_exposes_process_system_network_and_service_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend()

    assert backend.name == "windows-system"

    assert {
        capability.name
        for capability in backend.supported_capabilities
    } == {
        SystemCapabilityName.PROCESS_INSPECT,
        SystemCapabilityName.SYSTEM_INSPECT,
        SystemCapabilityName.NETWORK_INSPECT,
        SystemCapabilityName.SERVICE_INSPECT,
    }


def test_process_inspection_returns_structured_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    commands: list[str] = []

    def runner(command: str) -> str:
        commands.append(command)
        return _process_payload()

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=runner
    )

    result = backend.execute(
        _request(SystemCapabilityName.PROCESS_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS
    assert result.backend_name == "windows-system"
    assert isinstance(result.observed_at, datetime)

    processes = result.evidence["processes"]

    assert len(processes) == 2
    assert processes[0].pid == 1234
    assert processes[0].name == "python.exe"
    assert processes[0].memory_bytes == 4096

    assert commands
    assert "Get-CimInstance Win32_Process" in commands[0]
    assert "ConvertTo-Json" in commands[0]


def test_process_filter_by_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _process_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.PROCESS_INSPECT,
            {"pid": 5678},
        )
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS

    processes = result.evidence["processes"]

    assert len(processes) == 1
    assert processes[0].pid == 5678


def test_process_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _process_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.PROCESS_INSPECT,
            {"limit": 1},
        )
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS
    assert len(result.evidence["processes"]) == 1


@pytest.mark.parametrize(
    "parameters",
    [
        {"pid": -1},
        {"pid": True},
        {"limit": 0},
        {"limit": -1},
        {"limit": True},
        {"unexpected": "value"},
    ],
)
def test_invalid_process_parameters_fail(
    monkeypatch: pytest.MonkeyPatch,
    parameters: dict[str, object],
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _process_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.PROCESS_INSPECT,
            parameters,
        )
    )

    assert result.kind is SystemCapabilityResultKind.FAILED
    assert result.evidence is None


def test_system_inspection_returns_structured_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    commands: list[str] = []

    def runner(command: str) -> str:
        commands.append(command)
        return _system_payload()

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=runner
    )

    result = backend.execute(
        _request(SystemCapabilityName.SYSTEM_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS
    assert result.backend_name == "windows-system"
    assert isinstance(result.observed_at, datetime)

    system = result.evidence["system"]

    assert system.hostname == "VENUS"
    assert system.operating_system == "Microsoft Windows 11 Pro"
    assert system.operating_system_version == (
        "10.0.26100 (build 26100)"
    )
    assert system.architecture == "64-bit"
    assert system.kernel == "10.0.26100"
    assert system.uptime_seconds is not None
    assert system.uptime_seconds >= 0
    assert system.is_virtual_machine is False
    assert system.hypervisor is None

    assert commands
    assert "Win32_OperatingSystem" in commands[0]
    assert "Win32_ComputerSystem" in commands[0]


def test_system_inspection_rejects_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _system_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"hostname": True},
        )
    )

    assert result.kind is SystemCapabilityResultKind.FAILED
    assert result.evidence is None


def test_system_virtual_machine_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    payload = json.loads(_system_payload())

    payload["Computer"]["Manufacturer"] = (
        "Microsoft Corporation"
    )
    payload["Computer"]["Model"] = (
        "Virtual Machine"
    )
    payload["Product"]["Vendor"] = (
        "Microsoft Corporation"
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: json.dumps(payload)
    )

    result = backend.execute(
        _request(SystemCapabilityName.SYSTEM_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS

    system = result.evidence["system"]

    assert system.is_virtual_machine is True
    assert system.hypervisor == "Hyper-V"


def test_network_inspection_returns_interfaces_routes_and_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    commands: list[str] = []

    def runner(command: str) -> str:
        commands.append(command)
        return _network_payload()

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=runner
    )

    result = backend.execute(
        _request(SystemCapabilityName.NETWORK_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS
    assert result.backend_name == "windows-system"

    network = result.evidence["network"]

    assert len(network.interfaces) == 2

    ethernet = network.interfaces[0]

    assert ethernet.name == "Ethernet"
    assert ethernet.state == "Up"
    assert ethernet.mac_address == "00-11-22-33-44-55"
    assert ethernet.addresses == (
        "192.168.1.55",
        "fe80::1234",
    )
    assert ethernet.received_bytes == 100000
    assert ethernet.transmitted_bytes == 200000

    assert len(network.routes) == 1
    assert network.routes[0].destination == "0.0.0.0/0"
    assert network.routes[0].gateway == "192.168.1.254"
    assert network.routes[0].interface == "Ethernet"

    assert network.dns_servers == (
        "192.168.1.254",
        "1.1.1.1",
    )

    assert commands
    assert "Get-NetAdapter" in commands[0]
    assert "Get-NetRoute" in commands[0]
    assert "Get-DnsClientServerAddress" in commands[0]


def test_network_interface_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _network_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.NETWORK_INSPECT,
            {"interface": "Ethernet"},
        )
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS

    interfaces = result.evidence["network"].interfaces

    assert len(interfaces) == 1
    assert interfaces[0].name == "Ethernet"


def test_network_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _network_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.NETWORK_INSPECT,
            {"limit": 1},
        )
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS
    assert len(
        result.evidence["network"].interfaces
    ) == 1


@pytest.mark.parametrize(
    "parameters",
    [
        {"interface": ""},
        {"interface": 123},
        {"limit": 0},
        {"limit": -1},
        {"limit": True},
        {"unexpected": "value"},
    ],
)
def test_invalid_network_parameters_fail(
    monkeypatch: pytest.MonkeyPatch,
    parameters: dict[str, object],
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _network_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.NETWORK_INSPECT,
            parameters,
        )
    )

    assert result.kind is SystemCapabilityResultKind.FAILED
    assert result.evidence is None


def test_service_inspection_returns_structured_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    commands: list[str] = []

    def runner(command: str) -> str:
        commands.append(command)
        return _service_payload()

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=runner
    )

    result = backend.execute(
        _request(SystemCapabilityName.SERVICE_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS
    assert result.backend_name == "windows-system"

    services = result.evidence["services"]

    assert len(services) == 2

    spooler = services[0]

    assert spooler.name == "Spooler"
    assert spooler.display_name == "Print Spooler"
    assert spooler.state == "Running"
    assert spooler.startup_type == "Auto"
    assert spooler.description is not None

    assert commands
    assert "Get-CimInstance Win32_Service" in commands[0]


def test_service_filter_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _service_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.SERVICE_INSPECT,
            {"name": "Spooler"},
        )
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS

    services = result.evidence["services"]

    assert len(services) == 1
    assert services[0].name == "Spooler"


def test_service_filter_by_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _service_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.SERVICE_INSPECT,
            {"state": "Running"},
        )
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS

    services = result.evidence["services"]

    assert len(services) == 1
    assert services[0].name == "Spooler"


def test_service_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _service_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.SERVICE_INSPECT,
            {"limit": 1},
        )
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS
    assert len(result.evidence["services"]) == 1


@pytest.mark.parametrize(
    "parameters",
    [
        {"name": ""},
        {"name": 123},
        {"state": ""},
        {"state": 123},
        {"limit": 0},
        {"limit": -1},
        {"limit": True},
        {"unexpected": "value"},
    ],
)
def test_invalid_service_parameters_fail(
    monkeypatch: pytest.MonkeyPatch,
    parameters: dict[str, object],
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _service_payload()
    )

    result = backend.execute(
        _request(
            SystemCapabilityName.SERVICE_INSPECT,
            parameters,
        )
    )

    assert result.kind is SystemCapabilityResultKind.FAILED
    assert result.evidence is None


def test_non_windows_is_explicitly_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Linux",
    )

    backend = WindowsSystemCapabilityBackend()

    for capability in (
        SystemCapabilityName.PROCESS_INSPECT,
        SystemCapabilityName.SYSTEM_INSPECT,
        SystemCapabilityName.NETWORK_INSPECT,
        SystemCapabilityName.SERVICE_INSPECT,
    ):
        result = backend.execute(
            _request(capability)
        )

        assert result.kind is (
            SystemCapabilityResultKind.UNSUPPORTED
        )
        assert result.evidence is None


def test_powershell_missing_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    def missing(command: str) -> str:
        raise FileNotFoundError("powershell.exe")

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=missing
    )

    result = backend.execute(
        _request(SystemCapabilityName.SYSTEM_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.UNAVAILABLE
    assert "unavailable" in result.error.lower()


def test_powershell_failure_is_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    def failed(command: str) -> str:
        raise OSError("access denied")

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=failed
    )

    result = backend.execute(
        _request(SystemCapabilityName.NETWORK_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.FAILED
    assert result.evidence is None


def test_invalid_json_is_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: "{not-json"
    )

    result = backend.execute(
        _request(SystemCapabilityName.SERVICE_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.FAILED
    assert result.evidence is None


def test_backend_does_not_accept_arbitrary_execution_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    with pytest.raises(ValueError):
        _request(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"command": "whoami"},
        )


def test_unsupported_capability_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend()

    request = SystemCapabilityRequest(
        capability=SystemCapability(
            name=SystemCapabilityName.HARDWARE_INSPECT,
            description="Inspect Windows hardware.",
        )
    )

    result = backend.execute(request)

    assert result.kind is SystemCapabilityResultKind.UNSUPPORTED
    assert result.evidence is None