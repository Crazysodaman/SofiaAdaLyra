"""Real exact owner proof at OPS boundaries; external execution is a local fake."""
from test.fleet_state_fixture import register_fixture_candidate, authenticate_fixture_candidate
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from sofia.platform.distributed.durable import DurableRemoteAuthorization
from sofia.platform.ops.capability import OpsToolService
from sofia.platform.ops.migration_grants import migration_approval_parameters, migration_remote_grant_specs
from sofia.platform.ops.model import FleetHost, HostLifecycle
from sofia.platform.run import release_rollout_cli
from sofia.platform.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_ops_workload_migration_grants import catalog, plan, SOURCE_NODE, TARGET_NODE


def prepared_service(path, monkeypatch):
    monkeypatch.delenv("SOFIA_WORKLOAD_CATALOG_FILE", raising=False)
    service = OpsToolService(path)
    for host, node in (("source", SOURCE_NODE), ("target", TARGET_NODE)):
        register_fixture_candidate(service.registry, FleetHost(host, "linux", "x86_64", HostLifecycle.CANDIDATE, False))
        authenticate_fixture_candidate(service.registry, host, node)
        service.registry.transition(host, HostLifecycle.ENROLLED)
    return service


def record(path, capability, parameters, actor):
    now = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        str(uuid4()), capability, execution_fingerprint(capability, parameters),
        actor, now - timedelta(seconds=1), now + timedelta(minutes=5),
    )
    record_verified_owner_approval(ExecutionApprovalVerifier(path), approval)
    return approval.approval_id


def active_grants(path):
    store = DurableRemoteAuthorization(path)
    try:
        return store.active_grants(now=datetime.now(timezone.utc))
    finally:
        store.close()


@pytest.mark.parametrize("actor", ["person:sparks", "Sparks"])
def test_migration_accepts_verified_owner_and_derives_grant_actor(canonical_state_path, monkeypatch, actor):
    service = prepared_service(canonical_state_path, monkeypatch)
    operation = plan(checkpoint=False)
    service._workload_catalog = catalog()
    service._placement_decision = lambda raw, now: SimpleNamespace(eligible_hosts=("target",), rejected=())
    payload = {
        "migration_id": operation.migration_id, "source_host_id": "source", "target_host_id": "target",
        "workload": {"workload_id": "worker", "version": "1", "supported_platforms": ["linux"],
                     "supported_architectures": ["x86_64"], "singleton": True},
    }
    specs = migration_remote_grant_specs(
        catalog=service._workload_catalog, plan=operation,
        host_node_ids={"source": SOURCE_NODE, "target": TARGET_NODE},
    )
    exact = migration_approval_parameters(
        catalog=service._workload_catalog, plan=operation, workload_parameters=payload["workload"],
        source_node_id=SOURCE_NODE, target_node_id=TARGET_NODE, grant_specs=specs,
    )
    payload["approval_id"] = record(canonical_state_path, "ops.migration.execute", exact, actor)
    calls = []

    def execute(selected):
        grants = active_grants(canonical_state_path)
        assert len(grants) == len(specs)
        assert {grant.approved_by for grant in grants} == {"person:sparks"}
        calls.append(selected)
        return SimpleNamespace(migration_id=selected.migration_id, stage=SimpleNamespace(value="completed"),
                               lease_epoch=1, checkpoint_ref=None, receipts=())

    service.migration_executor = SimpleNamespace(preflight=lambda selected: None, execute=execute)
    result = service.execute_migration(payload)
    assert result["migration_id"] == operation.migration_id
    assert len(calls) == 1
    assert active_grants(canonical_state_path) == ()
    with pytest.raises(PermissionError):
        service.execute_migration(payload)
    assert len(calls) == 1
    assert active_grants(canonical_state_path) == ()


@pytest.mark.parametrize("actor", ["person:sparks", "Sparks"])
@pytest.mark.parametrize("fail", [False, True])
def test_rollout_accepts_verified_owner_and_derives_grant_actor(canonical_state_path, monkeypatch, actor, fail):
    prepared_service(canonical_state_path, monkeypatch)
    exact = {"release_id": "release-test", "manifest_sha256": "a" * 64,
             "targets": [{"host_id": "target", "ring": "canary"}], "runtime_service": "runtime-test"}
    approval_id = record(canonical_state_path, "release.rollout.execute", exact, actor)
    monkeypatch.setattr(release_rollout_cli, "create_configured_remote_fleet_service", lambda path: object())
    calls = []

    def rollout(self, **kwargs):
        grants = active_grants(canonical_state_path)
        assert len(grants) == 4
        assert {grant.approved_by for grant in grants} == {"person:sparks"}
        assert {grant.node_id for grant in grants} == {TARGET_NODE}
        calls.append(kwargs)
        if fail:
            raise RuntimeError("local execution boundary failed")
        return SimpleNamespace(rollout_id=kwargs["rollout_id"], release_id=kwargs["release_id"], events=())

    monkeypatch.setattr(release_rollout_cli.ReleaseRolloutCoordinator, "rollout", rollout)
    argv = [
        "--state-path", str(canonical_state_path), "--release-id", exact["release_id"],
        "--manifest-sha256", exact["manifest_sha256"], "--targets", "target:canary",
        "--approval-id", approval_id, "--runtime-service", exact["runtime_service"],
    ]
    assert release_rollout_cli.main(argv) == (2 if fail else 0)
    assert len(calls) == 1
    assert active_grants(canonical_state_path) == ()
    assert release_rollout_cli.main(argv) == 2
    assert len(calls) == 1
    assert active_grants(canonical_state_path) == ()


@pytest.mark.parametrize("mode", ["label", "wrong_target", "expired"])
def test_rollout_denies_unverified_or_inexact_owner_before_remote_boundary(canonical_state_path, monkeypatch, mode):
    prepared_service(canonical_state_path, monkeypatch)
    exact = {"release_id": "release-test", "manifest_sha256": "a" * 64,
             "targets": [{"host_id": "source" if mode == "wrong_target" else "target", "ring": "canary"}],
             "runtime_service": "runtime-test"}
    approval_id = "person:sparks"
    if mode == "wrong_target":
        approval_id = record(canonical_state_path, "release.rollout.execute", exact, "person:sparks")
    elif mode == "expired":
        now = datetime.now(timezone.utc)
        approval = ExecutionApproval(
            str(uuid4()), "release.rollout.execute",
            execution_fingerprint("release.rollout.execute", exact), "person:sparks",
            now - timedelta(minutes=10), now - timedelta(minutes=5),
        )
        record_verified_owner_approval(ExecutionApprovalVerifier(canonical_state_path), approval)
        approval_id = approval.approval_id

    def forbidden_remote(path):
        pytest.fail("owner denial must precede remote construction")

    monkeypatch.setattr(release_rollout_cli, "create_configured_remote_fleet_service", forbidden_remote)
    assert release_rollout_cli.main([
        "--state-path", str(canonical_state_path), "--release-id", "release-test",
        "--manifest-sha256", "a" * 64, "--targets", "target:canary",
        "--approval-id", approval_id, "--runtime-service", "runtime-test",
    ]) == 2
    assert active_grants(canonical_state_path) == ()
    if mode == "wrong_target":
        assert ExecutionApprovalVerifier(canonical_state_path).matches_unconsumed(
            approval_id=approval_id, capability="release.rollout.execute",
            parameters=exact, now=datetime.now(timezone.utc),
        )
