from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from typing import Any, Callable

from sofia.system.backend import SystemCapabilityBackend
from sofia.system.model import (
    ProcessInspection,
    SystemCapability,
    SystemCapabilityName,
    SystemCapabilityRequest,
    SystemCapabilityResult,
    SystemCapabilityResultKind,
)


PowerShellRunner = Callable[[str], str]


class WindowsSystemCapabilityBackend(SystemCapabilityBackend):
    """Windows implementation of the read-only process inspection capability."""

    _CAPABILITY = SystemCapability(
        name=SystemCapabilityName.PROCESS_INSPECT,
        description="Inspect running Windows processes.",
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
        return (self._CAPABILITY,)

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

        if request.capability.name is not SystemCapabilityName.PROCESS_INSPECT:
            return self._failure(
                request.capability.name,
                SystemCapabilityResultKind.UNSUPPORTED,
                "Capability is not supported by the Windows system backend.",
            )

        try:
            processes = self._inspect_processes(request.parameters)
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
        ) as exc:
            return self._failure(
                request.capability.name,
                SystemCapabilityResultKind.FAILED,
                f"Windows process inspection failed: {exc}",
            )

        return SystemCapabilityResult(
            capability=request.capability.name,
            kind=SystemCapabilityResultKind.SUCCESS,
            evidence={"processes": processes},
            observed_at=datetime.now(timezone.utc),
            backend_name=self.name,
        )

    def _inspect_processes(
        self,
        parameters: Any,
    ) -> list[ProcessInspection]:
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

        return result

    @staticmethod
    def _parse_wmi_datetime(
        value: Any,
    ) -> datetime | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise TypeError(
                "WMI CreationDate must be a string or None."
            )

        normalized = value[:14]

        if len(normalized) != 14 or not normalized.isdigit():
            raise ValueError(
                "Invalid WMI CreationDate."
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
                "Windows process string fields must be strings."
            )

        return value

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