from datetime import datetime, timedelta, timezone
from uuid import UUID

from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.ops.migration_grants import (
    migration_approval_parameters,
    migration_execution_profile_sha256,
    migration_remote_grant_specs,
    temporary_migration_remote_grants,
)
from sofia.ops.model import WorkloadContract
from sofia.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)
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



def test_execution_profile_hash_changes_when_reviewed_binding_changes():
    original = catalog()
    changed_target = HostWorkloadProfile(
        workload_id="worker",
        version="1",
        host_id="target",
        drain=binding("workload.manage", "unused-drain"),
        start=binding("workload.manage", "start-v2"),
        ready=binding("system.inspect", "service"),
        fence=binding("workload.manage", "unused-fence"),
        activate=binding("workload.manage", "activate"),
        rollback=binding("workload.manage", "rollback"),
    )
    source = original.profile("worker", "1", "source")
    changed = WorkloadExecutionCatalog((source, changed_target))

    assert migration_execution_profile_sha256(
        catalog=original,
        plan=plan(),
    ) != migration_execution_profile_sha256(
        catalog=changed,
        plan=plan(),
    )


def test_old_approval_is_rejected_after_catalog_binding_changes(tmp_path):
    state = tmp_path / "sofia.db"
    original = catalog()
    p = plan()
    original_specs = migration_remote_grant_specs(
        catalog=original,
        plan=p,
        host_node_ids={"source": SOURCE_NODE, "target": TARGET_NODE},
    )
    original_parameters = migration_approval_parameters(
        catalog=original,
        plan=p,
        workload_parameters={
            "workload_id": "worker",
            "version": "1",
            "supported_platforms": ["linux"],
            "supported_architectures": ["x86_64"],
            "singleton": True,
        },
        source_node_id=SOURCE_NODE,
        target_node_id=TARGET_NODE,
        grant_specs=original_specs,
    )
    verifier = ExecutionApprovalVerifier(state)
    verifier.record(
        ExecutionApproval(
            approval_id="migration-catalog-old",
            capability="ops.migration.execute",
            request_fingerprint=execution_fingerprint(
                "ops.migration.execute",
                original_parameters,
            ),
            approved_by="Sparks",
            approved_at=NOW,
            expires_at=NOW + timedelta(minutes=10),
        )
    )

    source = original.profile("worker", "1", "source")
    target = HostWorkloadProfile(
        workload_id="worker",
        version="1",
        host_id="target",
        drain=binding("workload.manage", "unused-drain"),
        start=binding("workload.manage", "start-v2"),
        ready=binding("system.inspect", "service"),
        fence=binding("workload.manage", "unused-fence"),
        activate=binding("workload.manage", "activate"),
        rollback=binding("workload.manage", "rollback"),
    )
    changed = WorkloadExecutionCatalog((source, target))
    changed_specs = migration_remote_grant_specs(
        catalog=changed,
        plan=p,
        host_node_ids={"source": SOURCE_NODE, "target": TARGET_NODE},
    )
    changed_parameters = migration_approval_parameters(
        catalog=changed,
        plan=p,
        workload_parameters=original_parameters["workload"],
        source_node_id=SOURCE_NODE,
        target_node_id=TARGET_NODE,
        grant_specs=changed_specs,
    )

    import pytest
    with pytest.raises(PermissionError, match="parameters do not match"):
        verifier.consume(
            approval_id="migration-catalog-old",
            capability="ops.migration.execute",
            parameters=changed_parameters,
            now=NOW + timedelta(seconds=1),
        )


def test_old_approval_is_rejected_after_target_node_replacement(tmp_path):
    state = tmp_path / "sofia.db"
    c = catalog()
    p = plan()
    specs = migration_remote_grant_specs(
        catalog=c,
        plan=p,
        host_node_ids={"source": SOURCE_NODE, "target": TARGET_NODE},
    )
    workload = {
        "workload_id": "worker",
        "version": "1",
        "supported_platforms": ["linux"],
        "supported_architectures": ["x86_64"],
        "singleton": True,
    }
    approved = migration_approval_parameters(
        catalog=c,
        plan=p,
        workload_parameters=workload,
        source_node_id=SOURCE_NODE,
        target_node_id=TARGET_NODE,
        grant_specs=specs,
    )
    verifier = ExecutionApprovalVerifier(state)
    verifier.record(
        ExecutionApproval(
            approval_id="migration-node-old",
            capability="ops.migration.execute",
            request_fingerprint=execution_fingerprint(
                "ops.migration.execute",
                approved,
            ),
            approved_by="Sparks",
            approved_at=NOW,
            expires_at=NOW + timedelta(minutes=10),
        )
    )

    replacement = UUID("33333333-3333-4333-8333-333333333333")
    replacement_specs = migration_remote_grant_specs(
        catalog=c,
        plan=p,
        host_node_ids={"source": SOURCE_NODE, "target": replacement},
    )
    replacement_parameters = migration_approval_parameters(
        catalog=c,
        plan=p,
        workload_parameters=workload,
        source_node_id=SOURCE_NODE,
        target_node_id=replacement,
        grant_specs=replacement_specs,
    )

    import pytest
    with pytest.raises(PermissionError, match="parameters do not match"):
        verifier.consume(
            approval_id="migration-node-old",
            capability="ops.migration.execute",
            parameters=replacement_parameters,
            now=NOW + timedelta(seconds=1),
        )
