"""Cognitive tool surface for local machine discovery and durable inventory."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sofia.capability.model import Capability,CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding

from .discovery import create_machine_discovery
from .hardware import HardwareDiscovery,create_hardware_discovery
from .inventory import MachineInventory
from .persistence import MachineInventoryPersistence
from .refresh import MachineInventoryRefresher

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

class MachineToolService:
    def __init__(self,state_path:Path)->None:
        self.persistence=MachineInventoryPersistence(state_path.parent/"machine-inventory.json")
        try:
            self.inventory=self.persistence.load()
        except FileNotFoundError:
            self.inventory=MachineInventory()
        self.refresher=MachineInventoryRefresher(create_machine_discovery(),create_hardware_discovery())

    @staticmethod
    def _observation(value)->dict[str,Any]:
        profile=value.profile
        return {
            "machine_id":value.machine_id,
            "hostname":value.hostname,
            "state":value.state.value,
            "observed_at":value.observed_at.isoformat(),
            "verified_at":value.verified_at.isoformat(),
            "source":value.provenance.source_name,
            "operating_system":{
                "family":profile.operating_system.family.value,
                "name":profile.operating_system.name,
                "version":profile.operating_system.version,
                "architecture":profile.operating_system.architecture,
                "kernel":profile.operating_system.kernel,
            },
            "virtualization":asdict(profile.virtualization),
            "hardware":{
                "cpu":profile.hardware.cpu,
                "gpu":profile.hardware.gpu,
                "memory_bytes":profile.hardware.memory_bytes,
                "storage":tuple(asdict(x) for x in profile.hardware.storage),
                "network_adapters":tuple(asdict(x) for x in profile.hardware.network_adapters),
            },
        }

    def list(self)->tuple[dict[str,Any],...]:
        return tuple(self._observation(self.inventory.get(machine_id)) for machine_id in sorted(self.inventory.machine_ids()))

    def get(self,machine_id:str)->dict[str,Any]|None:
        observation=self.inventory.get(machine_id)
        return None if observation is None else self._observation(observation)

    def discover_local(self)->dict[str,Any]:
        temporary=MachineInventory()
        result=self.refresher.refresh(temporary)
        if not result.succeeded or result.observation is None:
            raise RuntimeError(result.error or "local machine discovery failed")
        return self._observation(result.observation)

    def refresh_local(self,known_machine_id:str|None=None)->dict[str,Any]:
        result=self.refresher.refresh(self.inventory,known_machine_id=known_machine_id)
        self.persistence.save(self.inventory)
        return {
            "succeeded":result.succeeded,
            "error":result.error,
            "observation":None if result.observation is None else self._observation(result.observation),
            "machine_discovery_succeeded":result.machine_discovery_succeeded,
            "hardware_discovery_succeeded":result.hardware_discovery_succeeded,
        }

class MachineCapabilitySet:
    NAMES=("machine.list","machine.get","machine.discover.local","machine.refresh.local")
    def __init__(self,service:MachineToolService)->None: self.service=service
    def capabilities(self)->tuple[Capability,...]:
        desc={
            "machine.list":"List durable known machine observations. Read-only.",
            "machine.get":"Read one durable machine observation. Read-only.",
            "machine.discover.local":"Inspect the current machine identity and hardware without persisting it. Read-only.",
            "machine.refresh.local":"Refresh and persist the current machine observation.",
        }
        return tuple(Capability(x,desc[x]) for x in self.NAMES)
    def execute(self,request:CapabilityRequest)->Any:
        p=dict(request.parameters); n=request.capability.name
        if n=="machine.list": return self.service.list()
        if n=="machine.get": return self.service.get(p["machine_id"])
        if n=="machine.discover.local": return self.service.discover_local()
        if n=="machine.refresh.local": return self.service.refresh_local(p.get("known_machine_id"))
        raise ValueError("unsupported machine capability")

def create_machine_tool_bindings()->tuple[CognitiveToolBinding,...]:
    def b(tool,cap,desc,props=None,required=()):
        return CognitiveToolBinding(
            definition=CognitiveToolDefinition(name=tool,description=desc,
                parameters={"type":"object","properties":props or {},"required":list(required),"additionalProperties":False}),
            capability_name=cap,
        )
    return (
        b("list_known_machines","machine.list","List machines in Sofía's durable local inventory. Read-only."),
        b("inspect_known_machine","machine.get","Inspect one durable known-machine observation. Read-only.",
          {"machine_id":{"type":"string"}},("machine_id",)),
        b("discover_local_machine","machine.discover.local","Inspect this machine's identity and hardware without changing inventory. Read-only."),
        b("refresh_local_machine","machine.refresh.local","Refresh and persist this machine's inventory observation.",
          {"known_machine_id":{"type":"string"}}),
    )
