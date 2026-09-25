"""Read-only local hardware inventory capability."""
from __future__ import annotations

from dataclasses import asdict

from sofia.capability.model import Capability, CapabilityRequest
from sofia.machine.hardware import create_hardware_discovery

HARDWARE_INSPECT_CAPABILITY = Capability(
    "hardware.inspect",
    "Inspect local CPU, GPU, memory, storage, network adapter, and virtualization inventory.",
)

class HardwareInspectionCapability:
    capability = HARDWARE_INSPECT_CAPABILITY

    def execute(self, request: CapabilityRequest):
        if request.parameters:
            raise ValueError("hardware.inspect accepts no parameters")
        return asdict(create_hardware_discovery().discover())
