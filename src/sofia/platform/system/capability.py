"""Bridge platform system-inspection backends into the generic CapabilitySystem."""
from __future__ import annotations
import sys
from typing import Any
from sofia.capability.model import Capability,CapabilityRequest
from .backend import SystemCapabilityBackend
from .linux import LinuxSystemCapabilityBackend
from .model import SystemCapability,SystemCapabilityName,SystemCapabilityRequest
from .windows import WindowsSystemCapabilityBackend

def create_local_system_backend() -> SystemCapabilityBackend:
    if sys.platform=="win32":
        return WindowsSystemCapabilityBackend()
    if sys.platform.startswith("linux"):
        return LinuxSystemCapabilityBackend()
    raise RuntimeError(f"unsupported local system platform: {sys.platform}")

class SystemInspectionCapability:
    def __init__(self,backend:SystemCapabilityBackend,system_capability:SystemCapability)->None:
        self.backend=backend; self.system_capability=system_capability
        self.capability=Capability(
            name=system_capability.name.value,
            description=system_capability.description,
        )
    def execute(self,request:CapabilityRequest)->Any:
        if request.capability.name!=self.capability.name:
            raise ValueError("capability mismatch")
        result=self.backend.execute(SystemCapabilityRequest(
            capability=self.system_capability,
            parameters=request.parameters,
        ))
        return result

def create_local_system_capabilities(backend:SystemCapabilityBackend|None=None)->tuple[SystemInspectionCapability,...]:
    backend=backend or create_local_system_backend()
    return tuple(SystemInspectionCapability(backend,c) for c in backend.supported_capabilities)
