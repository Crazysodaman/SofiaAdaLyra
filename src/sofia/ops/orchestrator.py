"""Typed workload migration orchestration with explicit uncertainty boundaries."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from typing import Protocol
from .lease import LeaseTable
from .migration import MigrationCoordinator,MigrationPlan,MigrationStage
from .workload import StateMode

class MigrationExecutionError(RuntimeError): pass
class MigrationOutcomeUncertain(MigrationExecutionError): pass

class WorkloadBackend(Protocol):
    def drain(self,workload_id:str,host_id:str)->None: ...
    def checkpoint(self,workload_id:str,host_id:str)->str: ...
    def start(self,workload_id:str,host_id:str,checkpoint_id:str|None)->None: ...
    def ready(self,workload_id:str,host_id:str)->bool: ...
    def fence(self,workload_id:str,host_id:str)->None: ...
    def stop(self,workload_id:str,host_id:str)->None: ...

@dataclass(frozen=True)
class MigrationReceipt:
    migration_id:str
    workload_id:str
    source_host_id:str
    target_host_id:str
    checkpoint_id:str|None
    lease_epoch:int
    events:tuple[str,...]

class WorkloadOrchestrator:
    def __init__(self,leases:LeaseTable)->None:
        self.leases=leases; self.coordinator=MigrationCoordinator()

    def migrate(self,plan:MigrationPlan,backend:WorkloadBackend,*,now:datetime,lease_ttl:timedelta)->MigrationReceipt:
        workload_id=plan.workload.contract.workload_id
        checkpoint_id=None; events=[]; target_started=False; source_fenced=False
        try:
            backend.drain(workload_id,plan.source_host_id); events.append("source_drained")
            plan=self.coordinator.advance(plan,MigrationStage.DRAINED)
            needs_checkpoint=plan.workload.checkpoint_required or plan.workload.state_mode is not StateMode.STATELESS
            if needs_checkpoint:
                checkpoint_id=backend.checkpoint(workload_id,plan.source_host_id); events.append("checkpoint_created")
                if not checkpoint_id: raise MigrationExecutionError("checkpoint backend returned empty identity")
                plan=self.coordinator.advance(plan,MigrationStage.CHECKPOINTED)
            backend.start(workload_id,plan.target_host_id,checkpoint_id); target_started=True; events.append("target_started")
            plan=self.coordinator.advance(plan,MigrationStage.TARGET_STARTED)
            if backend.ready(workload_id,plan.target_host_id) is not True:
                raise MigrationExecutionError("target failed readiness")
            events.append("target_ready"); plan=self.coordinator.advance(plan,MigrationStage.READY)
            backend.fence(workload_id,plan.source_host_id); source_fenced=True
            self.leases.fence(workload_id,plan.source_host_id); events.append("source_fenced")
            plan=self.coordinator.advance(plan,MigrationStage.SOURCE_FENCED)
            lease=self.leases.transfer(workload_id,plan.source_host_id,plan.target_host_id,
                now=now,ttl=lease_ttl,state_verified=(not needs_checkpoint or checkpoint_id is not None))
            events.append(f"lease_epoch:{lease.epoch}")
            backend.stop(workload_id,plan.source_host_id); events.append("source_stopped")
            plan=self.coordinator.advance(plan,MigrationStage.COMPLETED)
            return MigrationReceipt(plan.migration_id,workload_id,plan.source_host_id,plan.target_host_id,checkpoint_id,lease.epoch,tuple(events))
        except Exception as exc:
            if source_fenced:
                raise MigrationOutcomeUncertain("migration failed after source fencing; do not automatically reactivate source") from exc
            if target_started:
                try: backend.stop(workload_id,plan.target_host_id)
                except Exception: raise MigrationOutcomeUncertain("target rollback outcome is unknown") from exc
            raise MigrationExecutionError(str(exc)) from exc
