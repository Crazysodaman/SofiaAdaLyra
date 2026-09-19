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
    parameters: dict[str, object] | None = None,
) -> SystemCapabilityRequest:
    return SystemCapabilityRequest(
        capability=SystemCapability(
            name=SystemCapabilityName.PROCESS_INSPECT,
            description="Inspect running Windows processes.",
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


def test_windows_backend_exposes_process_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.windows.platform.system",
        lambda: "Windows",
    )

    backend = WindowsSystemCapabilityBackend(
        powershell_runner=lambda command: _process_payload()
    )

    assert backend.name == "windows-system"
    assert [
        item.name
        for item in backend.supported_capabilities
    ] == [
        SystemCapabilityName.PROCESS_INSPECT
    ]


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

    result = backend.execute(_request())

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
        _request({"pid": 5678})
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
        _request({"limit": 1})
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
        _request(parameters)
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

    result = backend.execute(_request())

    assert result.kind is SystemCapabilityResultKind.UNSUPPORTED
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

    result = backend.execute(_request())

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

    result = backend.execute(_request())

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

    result = backend.execute(_request())

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
        _request({"command": "whoami"})


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
            name=SystemCapabilityName.SYSTEM_INSPECT,
            description="Inspect operating-system state.",
        )
    )

    result = backend.execute(request)

    assert result.kind is SystemCapabilityResultKind.UNSUPPORTED
    assert result.evidence is None