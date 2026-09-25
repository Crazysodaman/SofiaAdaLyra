"""Explicit workload migration state machine. It plans and records, but never shells out."""
from __future__ import annotations
from dataclasses import dataclass,replace
from enum import Enum
from .workload import ManagedWorkload,StateMode

class MigrationStage(str,Enum):
    PLANNED="planned"; DRAINED="drained"; CHECKPOINTED="checkpointed"; TARGET_STARTED="target_started"; READY="ready"; SOURCE_FENCED="source_fenced"; COMPLETED="completed"; ROLLED_BACK="rolled_back"

@dataclass(frozen=True)
class MigrationPlan:
    migration_id:str; workload:ManagedWorkload; source_host_id:str; target_host_id:str; stage:MigrationStage=MigrationStage.PLANNED
    def __post_init__(self):
        if self.source_host_id==self.target_host_id: raise ValueError("migration target must differ from source")

class MigrationCoordinator:
    def advance(self,plan:MigrationPlan,next_stage:MigrationStage)->MigrationPlan:
        needs_checkpoint=plan.workload.checkpoint_required or plan.workload.state_mode is not StateMode.STATELESS
        allowed={
            MigrationStage.PLANNED:{MigrationStage.DRAINED,MigrationStage.ROLLED_BACK},
            MigrationStage.DRAINED:({MigrationStage.CHECKPOINTED,MigrationStage.ROLLED_BACK} if needs_checkpoint else {MigrationStage.TARGET_STARTED,MigrationStage.ROLLED_BACK}),
            MigrationStage.CHECKPOINTED:{MigrationStage.TARGET_STARTED,MigrationStage.ROLLED_BACK},
            MigrationStage.TARGET_STARTED:{MigrationStage.READY,MigrationStage.ROLLED_BACK},
            MigrationStage.READY:{MigrationStage.SOURCE_FENCED,MigrationStage.ROLLED_BACK},
            MigrationStage.SOURCE_FENCED:{MigrationStage.COMPLETED},
            MigrationStage.COMPLETED:set(),MigrationStage.ROLLED_BACK:set(),
        }
        if next_stage not in allowed[plan.stage]: raise ValueError(f"invalid migration transition: {plan.stage.value} -> {next_stage.value}")
        return replace(plan,stage=next_stage)
