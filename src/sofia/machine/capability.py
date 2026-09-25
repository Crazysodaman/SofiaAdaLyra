"""Read-only local machine identity capability."""
from __future__ import annotations

from dataclasses import asdict

from sofia.capability.model import Capability, CapabilityRequest
from sofia.machine.discovery import create_machine_discovery

MACHINE_INSPECT_CAPABILITY = Capability(
    "machine.inspect",
    "Inspect stable local machine identity and operating-system facts.",
)

class MachineInspectionCapability:
    capability = MACHINE_INSPECT_CAPABILITY

    def execute(self, request: CapabilityRequest):
        if request.parameters:
            raise ValueError("machine.inspect accepts no parameters")
        return asdict(create_machine_discovery().discover())
