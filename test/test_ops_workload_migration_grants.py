from datetime import datetime, timedelta, timezone
from uuid import UUID

from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.ops.migration_grants import (
    migration_remote_grant_specs,
    temporary_migration_remote_grants,
)
from sofia.ops.model import WorkloadContract
from sofia.ops.workload import ManagedWorkload, MigrationPlan, StateMode
from sofia.ops.workload_backend import (
    HostWorkloadProfile,
    WorkloadExecutionCatalog,
    WorkloadOperationBinding,
)


NOW = datetime(2026, 10, 4, 23, 30, tzinfo=timezone.utc)
SOURCE_NODE = UUID("11111111-1111-4111-8111-111111111111")
TARGET_NODE = UUID("22222222-2222-4222-8222-222222222222")


def binding(capability: str, operation: str) -> WorkloadOperationBinding:
    return WorkloadOperationBinding(capability=capability, operation=operation)


def catalog() -> WorkloadExecutionCatalog:
    source = HostWorkloadProfile(
        workload_id="worker",
        version="1",
        host_id="source",
        drain=binding("workload.manage", "drain"),
        checkpoint=binding("workload.manage", "checkpoint"),
        start=binding("workload.manage", "unused-start"),
        ready=binding("system.inspect", "service"),
        fence=binding("workload.manage", "fence"),
        rollback=binding("workload.manage", "rollback"),
    )
    target = HostWorkloadProfile(
        workload_id="worker",
        version="1",
        host_id="target",
        drain=binding("workload.manage", "unused-drain"),
        start=binding("workload.manage", "start"),
        ready=binding("system.inspect", "service"),
        fence=binding("workload.manage", "unused-fence"),
        activate=binding("workload.manage", "activate"),
        rollback=binding("workload.manage", "rollback"),
    )
    return WorkloadExecutionCatalog((source, target))


def plan(*, singleton: bool = True, checkpoint: bool = True) -> MigrationPlan:
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


def test_specs_include_only_operations_executor_can_call_and_skip_reads():
    specs = migration_remote_grant_specs(
        catalog=catalog(),
        plan=plan(),
        host_node_ids={"source": SOURCE_NODE, "target": TARGET_NODE},
    )

    observed = {
        (item.host_id, item.capability, item.operation)
        for item in specs
    }
    assert observed == {
        ("source", "workload.manage", "drain"),
        ("source", "workload.manage", "checkpoint"),
        ("source", "workload.manage", "fence"),
        ("source", "workload.manage", "rollback"),
        ("target", "workload.manage", "start"),
        ("target", "workload.manage", "activate"),
        ("target", "workload.manage", "rollback"),
    }
    assert all(item.operation != "service" for item in specs)
    assert all("unused" not in item.operation for item in specs)


def test_specs_skip_local_host_and_require_remote_node_identity():
    specs = migration_remote_grant_specs(
        catalog=catalog(),
        plan=plan(singleton=False, checkpoint=False),
        host_node_ids={"source": None, "target": TARGET_NODE},
        local_host_id="source",
    )

    assert {item.host_id for item in specs} == {"target"}
    assert {
        item.operation for item in specs
    } == {"start", "rollback"}


def test_temporary_grants_exist_only_inside_execution_scope(tmp_path):
    state = tmp_path / "sofia.db"
    specs = migration_remote_grant_specs(
        catalog=catalog(),
        plan=plan(),
        host_node_ids={"source": SOURCE_NODE, "target": TARGET_NODE},
    )

    with temporary_migration_remote_grants(
        state_path=state,
        specs=specs,
        approved_by="Sparks",
        now=NOW,
        ttl=timedelta(minutes=10),
    ) as created:
        assert len(created) == len(specs)
        store = DurableRemoteAuthorization(state)
        try:
            active = store.active_grants(now=NOW + timedelta(seconds=1))
            assert {grant.grant_id for grant in active} == {
                grant.grant_id for grant in created
            }
            assert {grant.approved_by for grant in active} == {"Sparks"}
        finally:
            store.close()

    store = DurableRemoteAuthorization(state)
    try:
        assert store.active_grants(now=NOW + timedelta(seconds=2)) == ()
    finally:
        store.close()
