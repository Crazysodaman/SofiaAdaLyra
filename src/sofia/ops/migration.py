"""Durable workload migration execution with lease epochs and receipts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
from typing import Any

from sofia.ops.workload import MigrationPlan, MigrationStage, WorkloadInstance, WorkloadPhase
from sofia.ops.workload_backend import (
    TypedWorkloadBackend,
    WorkloadBackendError,
    WorkloadExecutionReceipt,
    WorkloadOutcomeUncertain,
)
from sofia.ops.workload_store import WorkloadInstanceStore
from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane


@dataclass(frozen=True, slots=True)
class WorkloadLease:
    workload_id: str
    holder_host_id: str
    migration_id: str
    epoch: int
    updated_at: datetime


class WorkloadLeaseStore:
    NAMESPACE = "ops-workload-lease"

    def __init__(self, state_plane: StatePlane) -> None:
        self.state_plane = state_plane

    def advance(
        self,
        *,
        workload_id: str,
        holder_host_id: str,
        migration_id: str,
        now: datetime,
    ) -> WorkloadLease:
        key = StateKey(self.NAMESPACE, workload_id)
        existing = self.state_plane.read(key)
        epoch = 1 if existing is None else int(json.loads(existing.value)["epoch"]) + 1
        lease = WorkloadLease(
            workload_id,
            holder_host_id,
            migration_id,
            epoch,
            now.astimezone(timezone.utc),
        )
        payload = json.dumps(
            {
                "workload_id": lease.workload_id,
                "holder_host_id": lease.holder_host_id,
                "migration_id": lease.migration_id,
                "epoch": lease.epoch,
                "updated_at": lease.updated_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.state_plane.write(
            StateRecord(
                key=key,
                state_class=StateClass.SHARED_AUTHORITATIVE,
                revision=1 if existing is None else existing.revision + 1,
                value=payload,
                updated_at=lease.updated_at,
                source="ops:workload-lease",
            ),
            expected_revision=None if existing is None else existing.revision,
        )
        return lease


class MigrationJournal:
    NAMESPACE = "ops-workload-migration"

    def __init__(self, state_plane: StatePlane) -> None:
        self.state_plane = state_plane

    def record(
        self,
        plan: MigrationPlan,
        *,
        stage: MigrationStage,
        lease_epoch: int | None,
        receipts: tuple[WorkloadExecutionReceipt, ...],
        now: datetime,
        error: str | None = None,
    ) -> None:
        key = StateKey(self.NAMESPACE, plan.migration_id)
        existing = self.state_plane.read(key)
        payload = json.dumps(
            {
                "migration_id": plan.migration_id,
                "workload_id": plan.workload.contract.workload_id,
                "version": plan.workload.contract.version,
                "source_host_id": plan.source_host_id,
                "target_host_id": plan.target_host_id,
                "stage": stage.value,
                "lease_epoch": lease_epoch,
                "checkpoint_required": plan.workload.checkpoint_required,
                "singleton": plan.workload.contract.singleton,
                "receipts": [
                    {
                        "step": r.step,
                        "host_id": r.host_id,
                        "capability": r.capability,
                        "operation": r.operation,
                        "reported_success": r.reported_success,
                        "message": r.message[:1000],
                        "result_ref": r.result_ref,
                    }
                    for r in receipts
                ],
                "error": error,
                "updated_at": now.astimezone(timezone.utc).isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.state_plane.write(
            StateRecord(
                key=key,
                state_class=StateClass.SHARED_AUTHORITATIVE,
                revision=1 if existing is None else existing.revision + 1,
                value=payload,
                updated_at=now.astimezone(timezone.utc),
                source="ops:workload-migration",
            ),
            expected_revision=None if existing is None else existing.revision,
        )

    def get(self, migration_id: str) -> dict[str, Any] | None:
        record = self.state_plane.read(StateKey(self.NAMESPACE, migration_id))
        return None if record is None else json.loads(record.value.decode("utf-8"))


@dataclass(frozen=True, slots=True)
class MigrationExecution:
    migration_id: str
    stage: MigrationStage
    lease_epoch: int
    receipts: tuple[WorkloadExecutionReceipt, ...]
    checkpoint_ref: str | None = None


class WorkloadMigrationExecutor:
    def __init__(
        self,
        *,
        backend: TypedWorkloadBackend,
        state_plane: StatePlane,
        instance_store: WorkloadInstanceStore,
    ) -> None:
        self.backend = backend
        self.state_plane = state_plane
        self.instances = instance_store
        self.leases = WorkloadLeaseStore(state_plane)
        self.journal = MigrationJournal(state_plane)

    def preflight(self, plan: MigrationPlan) -> None:
        if not isinstance(plan, MigrationPlan):
            raise TypeError("plan must be MigrationPlan")
        source = self.backend.catalog.profile(
            plan.workload.contract.workload_id,
            plan.workload.contract.version,
            plan.source_host_id,
        )
        target = self.backend.catalog.profile(
            plan.workload.contract.workload_id,
            plan.workload.contract.version,
            plan.target_host_id,
        )
        if (
            source.drain is None
            or source.fence is None
            or source.rollback is None
        ):
            raise WorkloadBackendError(
                "source requires drain, fence and rollback bindings"
            )
        if (
            target.start is None
            or target.ready is None
            or target.rollback is None
        ):
            raise WorkloadBackendError(
                "target requires start, ready and rollback bindings"
            )
        if plan.workload.checkpoint_required and source.checkpoint is None:
            raise WorkloadBackendError(
                "checkpoint-required workload lacks source checkpoint binding"
            )
        if plan.workload.contract.singleton and target.activate is None:
            raise WorkloadBackendError(
                "singleton target requires explicit activate binding"
            )
        observed = [
            item
            for item in self.instances.instances()
            if item.workload_id == plan.workload.contract.workload_id
            and item.host_id == plan.source_host_id
            and item.phase is WorkloadPhase.READY
        ]
        if len(observed) != 1:
            raise WorkloadBackendError(
                "migration requires exactly one READY source instance"
            )

    def _journal(
        self,
        plan: MigrationPlan,
        stage: MigrationStage,
        epoch: int | None,
        receipts: list[WorkloadExecutionReceipt],
        *,
        error: str | None = None,
    ) -> None:
        self.journal.record(
            plan,
            stage=stage,
            lease_epoch=epoch,
            receipts=tuple(receipts),
            now=datetime.now(timezone.utc),
            error=error,
        )

    def execute(self, plan: MigrationPlan) -> MigrationExecution:
        self.preflight(plan)
        now = datetime.now(timezone.utc)
        lease = self.leases.advance(
            workload_id=plan.workload.contract.workload_id,
            holder_host_id=plan.target_host_id,
            migration_id=plan.migration_id,
            now=now,
        )
        receipts: list[WorkloadExecutionReceipt] = []
        checkpoint_ref = None
        source_fenced = False
        self._journal(plan, MigrationStage.PLANNED, lease.epoch, receipts)

        try:
            receipts.append(
                self.backend.execute(
                    plan,
                    host_id=plan.source_host_id,
                    step="drain",
                    lease_epoch=lease.epoch,
                )
            )
            self._journal(plan, MigrationStage.DRAINED, lease.epoch, receipts)

            if plan.workload.checkpoint_required:
                checkpoint = self.backend.execute(
                    plan,
                    host_id=plan.source_host_id,
                    step="checkpoint",
                    lease_epoch=lease.epoch,
                )
                receipts.append(checkpoint)
                checkpoint_ref = checkpoint.result_ref
                self._journal(
                    plan,
                    MigrationStage.CHECKPOINTED,
                    lease.epoch,
                    receipts,
                )

            receipts.append(
                self.backend.execute(
                    plan,
                    host_id=plan.target_host_id,
                    step="start",
                    lease_epoch=lease.epoch,
                    checkpoint_ref=checkpoint_ref,
                    standby=plan.workload.contract.singleton,
                )
            )
            self._journal(
                plan,
                MigrationStage.TARGET_STARTED,
                lease.epoch,
                receipts,
            )

            receipts.append(
                self.backend.execute(
                    plan,
                    host_id=plan.target_host_id,
                    step="ready",
                    lease_epoch=lease.epoch,
                    checkpoint_ref=checkpoint_ref,
                    standby=plan.workload.contract.singleton,
                )
            )
            self._journal(plan, MigrationStage.READY, lease.epoch, receipts)

            receipts.append(
                self.backend.execute(
                    plan,
                    host_id=plan.source_host_id,
                    step="fence",
                    lease_epoch=lease.epoch,
                    checkpoint_ref=checkpoint_ref,
                )
            )
            source_fenced = True
            self._journal(
                plan,
                MigrationStage.SOURCE_FENCED,
                lease.epoch,
                receipts,
            )

            if plan.workload.contract.singleton:
                receipts.append(
                    self.backend.execute(
                        plan,
                        host_id=plan.target_host_id,
                        step="activate",
                        lease_epoch=lease.epoch,
                        checkpoint_ref=checkpoint_ref,
                    )
                )

            source_instance = next(
                item
                for item in self.instances.instances()
                if item.workload_id == plan.workload.contract.workload_id
                and item.host_id == plan.source_host_id
            )
            target_instance = WorkloadInstance(
                instance_id=source_instance.instance_id,
                workload_id=source_instance.workload_id,
                version=plan.workload.contract.version,
                host_id=plan.target_host_id,
                phase=WorkloadPhase.READY,
                lease_epoch=lease.epoch,
            )
            self.instances.observe(target_instance)
            self._journal(
                plan,
                MigrationStage.COMPLETED,
                lease.epoch,
                receipts,
            )
            return MigrationExecution(
                plan.migration_id,
                MigrationStage.COMPLETED,
                lease.epoch,
                tuple(receipts),
                checkpoint_ref,
            )
        except WorkloadOutcomeUncertain as exc:
            self._journal(
                plan,
                MigrationStage.OUTCOME_UNCERTAIN,
                lease.epoch,
                receipts,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        except Exception as exc:
            rollback_errors: list[str] = []
            # Do not resurrect the source automatically after a confirmed fence.
            # At that point an operator must resolve target/source truth explicitly.
            if not source_fenced:
                for host_id in (plan.target_host_id, plan.source_host_id):
                    try:
                        self.backend.execute(
                            plan,
                            host_id=host_id,
                            step="rollback",
                            lease_epoch=lease.epoch,
                            checkpoint_ref=checkpoint_ref,
                        )
                    except Exception as rollback_exc:
                        rollback_errors.append(
                            f"{host_id}:{type(rollback_exc).__name__}"
                        )
            stage = (
                MigrationStage.FAILED
                if source_fenced or rollback_errors
                else MigrationStage.ROLLED_BACK
            )
            self._journal(
                plan,
                stage,
                lease.epoch,
                receipts,
                error=(
                    f"{type(exc).__name__}: {exc}"
                    + (
                        ""
                        if not rollback_errors
                        else "; rollback=" + ",".join(rollback_errors)
                    )
                ),
            )
            raise
