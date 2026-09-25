"""Read-only cognitive surface for OPS fleet state, telemetry and planning."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sofia.capability.model import Capability,CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding

from .desired import DesiredHostState,DesiredWorkloadPlacement,detect_drift
from .history import TelemetryHistory
from .migration import MigrationPlan
from .model import HostLifecycle,WorkloadContract
from .persistence import JsonFleetRegistry
from .placement import PlacementEngine
from .workload import ManagedWorkload,StateMode,WorkloadInstance,WorkloadPhase

class OpsToolService:
    def __init__(self,state_path:Path)->None:
        self.registry=JsonFleetRegistry(state_path.parent/"fleet.json")
        self.history=TelemetryHistory(state_path.parent/"ops-telemetry.jsonl")
        self.placement=PlacementEngine()

    @staticmethod
    def _host(host)->dict[str,Any]:
        return {
            "host_id":host.host_id,
            "platform":host.platform,
            "architecture":host.architecture,
            "lifecycle":host.lifecycle.value,
            "trusted":host.trusted,
            "telemetry":None if host.telemetry is None else {
                **asdict(host.telemetry),
                "observed_at":host.telemetry.observed_at.isoformat(),
            },
            "tags":host.tags,
        }

    def fleet(self)->tuple[dict[str,Any],...]:
        return tuple(self._host(host) for host in self.registry.hosts())

    def host(self,host_id:str)->dict[str,Any]|None:
        host=self.registry.host(host_id)
        return None if host is None else self._host(host)

    def telemetry_latest(self,host_id:str)->dict[str,Any]|None:
        telemetry=self.history.latest(host_id)
        if telemetry is None:
            host=self.registry.host(host_id)
            telemetry=None if host is None else host.telemetry
        if telemetry is None: return None
        return {**asdict(telemetry),"observed_at":telemetry.observed_at.isoformat()}

    @staticmethod
    def _workload(raw:dict[str,Any])->WorkloadContract:
        return WorkloadContract(
            workload_id=raw["workload_id"],
            version=raw["version"],
            supported_platforms=tuple(raw["supported_platforms"]),
            supported_architectures=tuple(raw["supported_architectures"]),
            min_ram_bytes=int(raw.get("min_ram_bytes",0)),
            min_storage_bytes=int(raw.get("min_storage_bytes",0)),
            gpu_required=bool(raw.get("gpu_required",False)),
            min_vram_bytes=int(raw.get("min_vram_bytes",0)),
            singleton=bool(raw.get("singleton",False)),
            allowed_host_ids=tuple(raw.get("allowed_host_ids",())),
            denied_host_ids=tuple(raw.get("denied_host_ids",())),
        )

    def choose_placement(self,raw:dict[str,Any])->dict[str,Any]:
        decision=self.placement.choose(self._workload(raw),self.registry.hosts())
        return asdict(decision)

    def drift(self,p:dict[str,Any])->tuple[dict[str,Any],...]:
        desired_hosts=tuple(
            DesiredHostState(x["host_id"],HostLifecycle(x["lifecycle"]))
            for x in p.get("desired_hosts",())
        )
        desired_workloads=tuple(
            DesiredWorkloadPlacement(x["workload_id"],x["host_id"])
            for x in p.get("desired_workloads",())
        )
        instances=tuple(
            WorkloadInstance(
                x["instance_id"],x["workload_id"],x["version"],x["host_id"],
                WorkloadPhase(x["phase"]),x.get("lease_epoch"),
            )
            for x in p.get("instances",())
        )
        return tuple(asdict(x) for x in detect_drift(self.registry,instances,desired_hosts,desired_workloads))

    def migration_plan(self,p:dict[str,Any])->dict[str,Any]:
        contract=self._workload(p["workload"])
        managed=ManagedWorkload(
            contract,
            StateMode(p.get("state_mode","stateless")),
            checkpoint_required=bool(p.get("checkpoint_required",False)),
            failure_domain_spread=bool(p.get("failure_domain_spread",False)),
        )
        plan=MigrationPlan(p["migration_id"],managed,p["source_host_id"],p["target_host_id"])
        return {
            "migration_id":plan.migration_id,
            "workload_id":contract.workload_id,
            "source_host_id":plan.source_host_id,
            "target_host_id":plan.target_host_id,
            "stage":plan.stage.value,
            "state_mode":managed.state_mode.value,
            "checkpoint_required":managed.checkpoint_required,
            "failure_domain_spread":managed.failure_domain_spread,
        }

class OpsCapabilitySet:
    NAMES=("ops.fleet.list","ops.fleet.get","ops.telemetry.latest","ops.placement.choose","ops.drift.detect","ops.migration.plan")
    def __init__(self,service:OpsToolService)->None: self.service=service
    def capabilities(self)->tuple[Capability,...]:
        descriptions={
            "ops.fleet.list":"List durable OPS fleet hosts and current state. Read-only.",
            "ops.fleet.get":"Inspect one durable OPS fleet host. Read-only.",
            "ops.telemetry.latest":"Read the latest durable telemetry for one fleet host. Read-only.",
            "ops.placement.choose":"Evaluate eligible placement for a workload using current durable fleet evidence. Read-only.",
            "ops.drift.detect":"Compare supplied desired state/workload placements with durable fleet evidence. Read-only.",
            "ops.migration.plan":"Construct a migration plan without executing it. Read-only planning.",
        }
        return tuple(Capability(name,descriptions[name]) for name in self.NAMES)
    def execute(self,request:CapabilityRequest)->Any:
        p=dict(request.parameters); name=request.capability.name
        if name=="ops.fleet.list": return self.service.fleet()
        if name=="ops.fleet.get": return self.service.host(p["host_id"])
        if name=="ops.telemetry.latest": return self.service.telemetry_latest(p["host_id"])
        if name=="ops.placement.choose": return self.service.choose_placement(p["workload"])
        if name=="ops.drift.detect": return self.service.drift(p)
        if name=="ops.migration.plan": return self.service.migration_plan(p)
        raise ValueError("unsupported OPS capability")

def create_ops_tool_bindings()->tuple[CognitiveToolBinding,...]:
    def b(tool,cap,desc,props=None,required=()):
        return CognitiveToolBinding(
            definition=CognitiveToolDefinition(name=tool,description=desc,
                parameters={"type":"object","properties":props or {},"required":list(required),"additionalProperties":False}),
            capability_name=cap,
        )
    workload={"type":"object","properties":{}}
    return (
        b("list_fleet_hosts","ops.fleet.list","List OPS fleet hosts and durable state. Read-only."),
        b("inspect_fleet_host","ops.fleet.get","Inspect one OPS fleet host. Read-only.",
          {"host_id":{"type":"string"}},("host_id",)),
        b("inspect_fleet_telemetry","ops.telemetry.latest","Read latest durable telemetry for one fleet host. Read-only.",
          {"host_id":{"type":"string"}},("host_id",)),
        b("choose_workload_placement","ops.placement.choose","Evaluate workload placement against current fleet evidence. Does not move anything.",
          {"workload":workload},("workload",)),
        b("detect_fleet_drift","ops.drift.detect","Compare supplied desired host/workload state with durable fleet evidence. Read-only.",
          {"desired_hosts":{"type":"array","items":{"type":"object"}},
           "desired_workloads":{"type":"array","items":{"type":"object"}},
           "instances":{"type":"array","items":{"type":"object"}}}),
        b("plan_workload_migration","ops.migration.plan","Construct a workload migration plan without executing it.",
          {"migration_id":{"type":"string"},"workload":workload,"source_host_id":{"type":"string"},
           "target_host_id":{"type":"string"},"state_mode":{"type":"string"},
           "checkpoint_required":{"type":"boolean"},"failure_domain_spread":{"type":"boolean"}},
          ("migration_id","workload","source_host_id","target_host_id")),
    )
