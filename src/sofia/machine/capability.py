"""Read-only local hardware inspection capability."""
from __future__ import annotations
from sofia.capability.model import Capability,CapabilityRequest
from .hardware import HardwareDiscovery,create_hardware_discovery

HARDWARE_INSPECT_CAPABILITY=Capability(
    name="hardware.inspect",
    description="Inspect local CPU, GPU, memory, storage, network-adapter and virtualization hardware. Read-only.",
)

class HardwareInspectionCapability:
    def __init__(self,discovery:HardwareDiscovery|None=None)->None:
        self.discovery=discovery or create_hardware_discovery()
        self.capability=HARDWARE_INSPECT_CAPABILITY
    def execute(self,request:CapabilityRequest):
        if request.capability.name!=self.capability.name:
            raise ValueError("capability mismatch")
        if request.parameters:
            raise ValueError("hardware.inspect does not accept parameters")
        return self.discovery.discover()
