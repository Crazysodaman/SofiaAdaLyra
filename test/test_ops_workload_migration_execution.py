from datetime import datetime, timezone

import pytest

from sofia.distributed.operations import RemoteOperationUncertain
from sofia.ops.model import WorkloadContract
from sofia.ops.migration import MigrationJournal, WorkloadMigrationExecutor
from sofia.ops.workload import (
    ManagedWorkload,
    MigrationPlan,
    MigrationStage,
    StateMode,
    WorkloadInstance,
    WorkloadPhase,
)
from sofia.ops.workload_backend import (
    HostWorkloadProfile,
    TypedWorkloadBackend,
    WorkloadBackendError,
    WorkloadExecutionCatalog,
    WorkloadOutcomeUncertain,
    WorkloadOperationBinding,
)
from sofia.ops.workload_store import WorkloadInstanceStore
from sofia.state.sqlite_plane import SQLiteStatePlane


def binding(name, *, expect=False, ref=False):
    return WorkloadOperationBinding(
        capability="workload.test",
        operation=name,
        expect_path="ready" if expect else None,
        expect_equals=True if expect else None,
        result_ref_path="checkpoint_ref" if ref else None,
    )


def plan(singleton=False, checkpoint=False):
    return MigrationPlan(
        "move-1",
        ManagedWorkload(
            WorkloadContract(
                "worker",
                "1",
                ("linux",),
                ("x86_64",),
                singleton=singleton,
            ),
            StateMode.CHECKPOINTED if checkpoint else StateMode.STATELESS,
            checkpoint_required=checkpoint,
        ),
        "source",
        "target",
    )


def profiles(singleton=False, checkpoint=False):
    return (
        HostWorkloadProfile(
            "worker","1","source",
            drain=binding("drain"),
            checkpoint=binding("checkpoint", ref=True) if checkpoint else None,
            start=binding("unused"),
            ready=binding("unused-ready", expect=True),
            fence=binding("fence"),
            rollback=binding("rollback"),
        ),
        HostWorkloadProfile(
            "worker","1","target",
            drain=binding("unused"),
            start=binding("start"),
            ready=binding("ready", expect=True),
            fence=binding("unused-fence"),
            activate=binding("activate") if singleton else None,
            rollback=binding("rollback"),
        ),
    )


def make_executor(
    tmp_path,
    *,
    singleton=False,
    checkpoint=False,
    fail_step=None,
    uncertain_step=None,
):
    state = tmp_path / "sofia.db"
    plane = SQLiteStatePlane(state)
    store = WorkloadInstanceStore(state)
    store.observe(
        WorkloadInstance(
            "worker-1","worker","1","source",WorkloadPhase.READY,1
        )
    )
    calls = []

    def invoke(host, capability, operation, parameters):
        calls.append((host, operation, dict(parameters)))
        if operation == fail_step:
            raise RuntimeError("boom")
        if operation == uncertain_step:
            raise RemoteOperationUncertain("transport outcome unknown")
        if operation == "ready":
            return {
                "outcome":"reported_success",
                "message":'{"ready":true}',
            }
        if operation == "checkpoint":
            return {
                "outcome":"reported_success",
                "message":'{"checkpoint_ref":"cp-1"}',
            }
        return {"outcome":"reported_success","message":"{}"}

    backend = TypedWorkloadBackend(
        WorkloadExecutionCatalog(profiles(singleton, checkpoint)),
        invoke,
    )
    return (
        WorkloadMigrationExecutor(
            backend=backend,
            state_plane=plane,
            instance_store=store,
        ),
        calls,
        store,
        plane,
    )


def test_stateless_migration_executes_and_moves_observed_instance(tmp_path):
    executor, calls, store, plane = make_executor(tmp_path)

    result = executor.execute(plan())

    assert result.stage is MigrationStage.COMPLETED
    assert [operation for _, operation, _ in calls] == [
        "drain","start","ready","fence",
    ]
    instance = store.instances()[0]
    assert instance.host_id == "target"
    assert instance.phase is WorkloadPhase.READY
    assert instance.lease_epoch == result.lease_epoch
    assert MigrationJournal(plane).get("move-1")["stage"] == "completed"


def test_singleton_target_activates_only_after_source_fence(tmp_path):
    executor, calls, _, _ = make_executor(tmp_path, singleton=True)

    executor.execute(plan(singleton=True))

    operations = [operation for _, operation, _ in calls]
    assert operations.index("fence") < operations.index("activate")


def test_checkpoint_reference_is_required_and_propagated(tmp_path):
    executor, calls, _, _ = make_executor(tmp_path, checkpoint=True)

    result = executor.execute(plan(checkpoint=True))

    assert result.checkpoint_ref == "cp-1"
    assert "checkpoint" in [operation for _, operation, _ in calls]


def test_readiness_failure_rolls_back_before_source_fence(tmp_path):
    executor, calls, store, plane = make_executor(tmp_path, fail_step="ready")

    with pytest.raises(WorkloadBackendError):
        executor.execute(plan())

    assert "fence" not in [operation for _, operation, _ in calls]
    assert [op for _, op, _ in calls].count("rollback") == 2
    assert store.instances()[0].host_id == "source"
    assert MigrationJournal(plane).get("move-1")["stage"] == "rolled_back"


def test_checkpoint_required_preflight_fails_before_side_effect(tmp_path):
    executor, calls, _, _ = make_executor(tmp_path, checkpoint=False)
    bad = plan(checkpoint=True)

    with pytest.raises(WorkloadBackendError, match="checkpoint"):
        executor.execute(bad)

    assert calls == []


def test_uncertain_remote_outcome_never_triggers_automatic_rollback(tmp_path):
    executor, calls, store, plane = make_executor(
        tmp_path,
        uncertain_step="start",
    )

    with pytest.raises(WorkloadOutcomeUncertain, match="do not retry or rollback"):
        executor.execute(plan())

    operations = [operation for _, operation, _ in calls]
    assert operations == ["drain", "start"]
    assert "rollback" not in operations
    assert store.instances()[0].host_id == "source"
    assert (
        MigrationJournal(plane).get("move-1")["stage"]
        == "outcome_uncertain"
    )


def test_workload_result_path_supports_indexed_service_evidence(tmp_path):
    state = tmp_path / "sofia.db"
    plane = SQLiteStatePlane(state)
    store = WorkloadInstanceStore(state)
    store.observe(
        WorkloadInstance(
            "worker-1",
            "worker",
            "1",
            "source",
            WorkloadPhase.READY,
            1,
        )
    )
    source, target = profiles()
    target = HostWorkloadProfile(
        target.workload_id,
        target.version,
        target.host_id,
        drain=target.drain,
        start=target.start,
        ready=WorkloadOperationBinding(
            capability="system.inspect",
            operation="service",
            expect_path="evidence.services.0.state",
            expect_equals="Running",
        ),
        fence=target.fence,
        activate=target.activate,
        rollback=target.rollback,
    )

    def invoke(host, capability, operation, parameters):
        if host == "target" and operation == "service":
            return {
                "outcome": "reported_success",
                "message": (
                    '{"kind":"success","evidence":'
                    '{"services":[{"name":"worker","state":"Running"}]}}'
                ),
            }
        return {"outcome": "reported_success", "message": "{}"}

    executor = WorkloadMigrationExecutor(
        backend=TypedWorkloadBackend(
            WorkloadExecutionCatalog((source, target)),
            invoke,
        ),
        state_plane=plane,
        instance_store=store,
    )

    assert executor.execute(plan()).stage is MigrationStage.COMPLETED
