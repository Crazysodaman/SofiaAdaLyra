"""Desired-state and drift reporting for fleet reconciliation."""
from __future__ import annotations
from dataclasses import dataclass
from .fleet import FleetRegistry
from .model import HostLifecycle
from .workload import WorkloadInstance

@dataclass(frozen=True)
class DesiredHostState:
    host_id:str; lifecycle:HostLifecycle

@dataclass(frozen=True)
class DesiredWorkloadPlacement:
    workload_id:str; host_id:str

@dataclass(frozen=True)
class Drift:
    kind:str; subject_id:str; expected:str; observed:str|None

def detect_drift(registry:FleetRegistry,instances:tuple[WorkloadInstance,...],desired_hosts:tuple[DesiredHostState,...],desired_workloads:tuple[DesiredWorkloadPlacement,...])->tuple[Drift,...]:
    out=[]
    for d in desired_hosts:
        host=registry.host(d.host_id)
        observed=None if host is None else host.lifecycle.value
        if observed!=d.lifecycle.value: out.append(Drift("host_lifecycle",d.host_id,d.lifecycle.value,observed))
    by_workload={i.workload_id:i for i in instances}
    for d in desired_workloads:
        instance=by_workload.get(d.workload_id)
        observed=None if instance is None else instance.host_id
        if observed!=d.host_id: out.append(Drift("workload_placement",d.workload_id,d.host_id,observed))
    return tuple(out)
