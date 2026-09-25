"""Bridge OS-specific system inspection backends into CapabilitySystem."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sofia.capability.model import Capability, CapabilityRequest
from sofia.system.backend import SystemCapabilityBackend
from sofia.system.model import (
    SystemCapabilityName,
    SystemCapabilityRequest,
    SystemCapabilityResultKind,
)

_DESCRIPTIONS = {
    SystemCapabilityName.PROCESS_INSPECT: "Inspect running processes on the local host.",
    SystemCapabilityName.SYSTEM_INSPECT: "Inspect operating-system and uptime state on the local host.",
    SystemCapabilityName.NETWORK_INSPECT: "Inspect local network interfaces, routes, and DNS.",
    SystemCapabilityName.SERVICE_INSPECT: "Inspect local service state and configuration.",
}

@dataclass(frozen=True)
class SystemInspectionCapability:
    backend: SystemCapabilityBackend
    name: SystemCapabilityName

    @property
    def capability(self) -> Capability:
        return Capability(self.name.value, _DESCRIPTIONS[self.name])

    def execute(self, request: CapabilityRequest) -> Any:
        if request.capability.name != self.name.value:
            raise ValueError("capability name mismatch")
        native = next(
            (item for item in self.backend.supported_capabilities if item.name is self.name),
            None,
        )
        if native is None:
            raise RuntimeError(f"backend does not support {self.name.value}")
        result = self.backend.execute(
            SystemCapabilityRequest(native, request.parameters)
        )
        if result.kind is not SystemCapabilityResultKind.SUCCESS:
            raise RuntimeError(result.error or f"{self.name.value} failed")
        return {
            "backend": result.backend_name,
            "observed_at": (
                None
                if result.observed_at is None
                else result.observed_at.isoformat()
            ),
            "evidence": result.evidence,
        }

def create_system_capabilities(
    backend: SystemCapabilityBackend,
) -> tuple[SystemInspectionCapability, ...]:
    return tuple(
        SystemInspectionCapability(backend, item.name)
        for item in backend.supported_capabilities
    )
