"""Managed workload state contracts for placement and migration."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .model import WorkloadContract

class StateMode(str,Enum):
    STATELESS="stateless"; CHECKPOINTED="checkpointed"; PERSISTENT="persistent"

class WorkloadPhase(str,Enum):
    STOPPED="stopped"; READY="ready"; DRAINING="draining"; CHECKPOINTED="checkpointed"; STARTING="starting"; FAILED="failed"

@dataclass(frozen=True)
class ManagedWorkload:
    contract:WorkloadContract
    state_mode:StateMode=StateMode.STATELESS
    checkpoint_required:bool=False
    failure_domain_spread:bool=False

@dataclass(frozen=True)
class WorkloadInstance:
    instance_id:str; workload_id:str; version:str; host_id:str; phase:WorkloadPhase; lease_epoch:int|None=None
    def __post_init__(self):
        if not all((self.instance_id.strip(),self.workload_id.strip(),self.version.strip(),self.host_id.strip())): raise ValueError("workload instance identity required")

class MigrationStage(str,Enum):
    PLANNED="planned"; DRAINED="drained"; CHECKPOINTED="checkpointed"; TARGET_STARTED="target_started"; READY="ready"; SOURCE_FENCED="source_fenced"; COMPLETED="completed"; ROLLED_BACK="rolled_back"

@dataclass(frozen=True)
class MigrationPlan:
    migration_id:str; workload:ManagedWorkload; source_host_id:str; target_host_id:str; stage:MigrationStage=MigrationStage.PLANNED
    def __post_init__(self):
        if self.source_host_id==self.target_host_id: raise ValueError("migration target must differ from source")
