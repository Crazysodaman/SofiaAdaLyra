from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class HostLifecycle(str,Enum):
    CANDIDATE="candidate"; ENROLLED="enrolled"; HEALTHY="healthy"; DEGRADED="degraded"; MAINTENANCE="maintenance"; DRAINING="draining"; QUARANTINED="quarantined"; OFFLINE="offline"; DECOMMISSIONED="decommissioned"

class WorkloadState(str,Enum):
    STOPPED="stopped"; STARTING="starting"; READY="ready"; DRAINING="draining"; FAILED="failed"

@dataclass(frozen=True)
class HostTelemetry:
    observed_at:datetime
    cpu_percent:float|None=None; ram_used_bytes:int|None=None; ram_total_bytes:int|None=None
    gpu_percent:float|None=None; vram_used_bytes:int|None=None; vram_total_bytes:int|None=None
    storage_free_bytes:int|None=None; temperature_c:float|None=None; throttled:bool|None=None
    def __post_init__(self):
        if self.observed_at.tzinfo is None: raise ValueError("observed_at must be timezone-aware")
        for name in ("cpu_percent","gpu_percent"):
            v=getattr(self,name)
            if v is not None and not 0<=v<=100: raise ValueError(f"{name} must be 0..100")
        for name in ("ram_used_bytes","ram_total_bytes","vram_used_bytes","vram_total_bytes","storage_free_bytes"):
            v=getattr(self,name)
            if v is not None and v<0: raise ValueError(f"{name} cannot be negative")

@dataclass(frozen=True)
class FleetHost:
    host_id:str; platform:str; architecture:str; lifecycle:HostLifecycle; trusted:bool; telemetry:HostTelemetry|None=None; tags:tuple[str,...]=()
    def __post_init__(self):
        if not self.host_id.strip(): raise ValueError("host_id required")

@dataclass(frozen=True)
class WorkloadContract:
    workload_id:str; version:str; supported_platforms:tuple[str,...]; supported_architectures:tuple[str,...]
    min_ram_bytes:int=0; min_storage_bytes:int=0; gpu_required:bool=False; min_vram_bytes:int=0
    singleton:bool=False; allowed_host_ids:tuple[str,...]=(); denied_host_ids:tuple[str,...]=()
    def __post_init__(self):
        if not self.workload_id.strip() or not self.version.strip(): raise ValueError("workload identity required")
        if not self.supported_platforms or not self.supported_architectures: raise ValueError("platform and architecture support required")
