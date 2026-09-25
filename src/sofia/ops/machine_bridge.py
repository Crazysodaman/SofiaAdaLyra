"""Bridge existing machine/system evidence into OPS without treating observation as trust."""
from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
from sofia.machine.model import MachineProfile
from sofia.system.model import HardwareInspection,SystemCapabilityResult,SystemCapabilityResultKind
from .model import FleetHost,HostLifecycle,HostTelemetry

def fleet_host_from_machine(profile:MachineProfile,*,trusted:bool=False,lifecycle:HostLifecycle=HostLifecycle.CANDIDATE)->FleetHost:
    return FleetHost(profile.identity.machine_id,profile.operating_system.family.value,
        profile.operating_system.architecture or "unknown",lifecycle,trusted,None,(profile.identity.hostname,))

def _num(mapping:Mapping[str,Any]|None,*keys:str)->Any:
    if not mapping: return None
    for key in keys:
        value=mapping.get(key)
        if value is not None: return value
    return None

def telemetry_from_hardware(inspection:HardwareInspection,*,observed_at:datetime|None=None)->HostTelemetry:
    at=observed_at or datetime.now(timezone.utc)
    cpu=inspection.cpu; gpu=inspection.gpu; memory=inspection.memory; storage=inspection.storage
    return HostTelemetry(
        observed_at=at,
        cpu_percent=_num(cpu,"percent","usage_percent","utilization_percent"),
        ram_used_bytes=_num(memory,"used_bytes","used"),
        ram_total_bytes=_num(memory,"total_bytes","total"),
        gpu_percent=_num(gpu,"percent","usage_percent","utilization_percent"),
        vram_used_bytes=_num(gpu,"vram_used_bytes","memory_used_bytes"),
        vram_total_bytes=_num(gpu,"vram_total_bytes","memory_total_bytes"),
        storage_free_bytes=_num(storage,"free_bytes","available_bytes"),
        temperature_c=_num(cpu,"temperature_c","temp_c") or _num(gpu,"temperature_c","temp_c"),
        throttled=_num(cpu,"throttled") if _num(cpu,"throttled") is not None else _num(gpu,"throttled"),
    )

def telemetry_from_system_result(result:SystemCapabilityResult)->HostTelemetry:
    if result.kind is not SystemCapabilityResultKind.SUCCESS:
        raise ValueError("system capability result is not successful")
    if not isinstance(result.evidence,HardwareInspection):
        raise TypeError("hardware.inspect evidence required")
    return telemetry_from_hardware(result.evidence,observed_at=result.observed_at)
