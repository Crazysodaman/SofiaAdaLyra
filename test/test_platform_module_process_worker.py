from datetime import datetime, timedelta, timezone
import os
from time import sleep
from uuid import uuid4

import pytest

from sofia.platform.capability import (
    CapabilityRequest,
    CapabilityResultKind,
    CapabilitySystem,
)
from sofia.platform.modules import (
    RESEARCH_CAPABILITY_ID,
    RESEARCH_COMPONENT_ID,
    RESEARCH_MODULE_ID,
    AdapterFactoryRegistry,
    ModuleCancellationPolicy,
    ModuleLifecycle,
    ModuleOperationCoordinator,
    ModuleOperationRequest,
    ModuleOperationType,
    ModulePlatformTarget,
    OperationProfileKind,
    ResearchModuleProcessAdapter,
    ReviewedResearchProcessFactory,
)
from sofia.platform.application.module_lifecycle import ModuleLifecycleCommandService
from sofia.platform.run import (
    DurableWorkStore,
    ProcessState,
    TaskExecutionManager,
    WorkStatus,
)
from sofia.core.social.principals import local_sparks_principal
from test.test_module_lifecycle_v1 import verified_custom
from test.test_platform_module_command_service import authorize


def snapshot(now):
    return {
        "source_ref": "source:test",
        "observed_at": now.isoformat(),
        "claim_id": "claim:test",
        "evidence": [{
            "evidence_id": "evidence:one",
            "origin_ref": "origin:one",
            "published_at": (now - timedelta(days=1)).isoformat(),
            "stance": "supports",
            "citation_ref": "citation:one",
        }],
    }


def test_real_research_module_process_keeps_platform_and_state_outside_child(
    tmp_path,
):
    adapter = ResearchModuleProcessAdapter(
        package_digest="a" * 64,
        host_identity="host:test",
        runtime_dir=tmp_path / "runtime",
    )
    platform_pid = os.getpid()
    adapter.start(epoch=7)
    try:
        inspection = adapter.inspect()
        assert inspection.state is ProcessState.RUNNING
        assert inspection.ready
        assert inspection.package_digest == "a" * 64
        assert inspection.host_identity == "host:test"
        assert f":{platform_pid}:" not in inspection.evidence_ref

        system = CapabilitySystem(authorization_checker=lambda request: True)
        system.register_batch(adapter.capability_registrations())
        capability = system.resolve(RESEARCH_CAPABILITY_ID)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        result = system.execute(CapabilityRequest(
            capability, {"snapshot": snapshot(now)}, "private",
            "review supplied evidence",
        ))
        assert result.kind is CapabilityResultKind.SUCCESS
        assert result.evidence["status"] == "reviewed"
        assert result.evidence["effect"] == "none"
        assert result.evidence["external_requests_sent"] is False
    finally:
        adapter.stop()
    assert adapter.observe().state is ProcessState.STOPPED
    assert os.getpid() == platform_pid


def test_platform_authorization_denial_never_dispatches_to_worker(tmp_path):
    adapter = ResearchModuleProcessAdapter(
        package_digest="b" * 64,
        host_identity="host:test",
        runtime_dir=tmp_path / "runtime",
    )
    adapter.start(epoch=8)
    try:
        system = CapabilitySystem(authorization_checker=lambda request: False)
        system.register_batch(adapter.capability_registrations())
        capability = system.resolve(RESEARCH_CAPABILITY_ID)
        result = system.execute(CapabilityRequest(
            capability, {"snapshot": {}}, "private", "denied request",
        ))
        assert result.kind is CapabilityResultKind.UNAUTHORIZED
        assert adapter.inspect().ready
    finally:
        adapter.stop()


def test_invalid_or_oversized_request_fails_without_success_receipt(tmp_path):
    adapter = ResearchModuleProcessAdapter(
        package_digest="c" * 64,
        host_identity="host:test",
        runtime_dir=tmp_path / "runtime",
    )
    adapter.start(epoch=9)
    capability = adapter.capability_registrations()[0][0]
    try:
        with pytest.raises((ModuleNotFoundError, RuntimeError, ValueError)):
            adapter.capability_registrations()[0][1](CapabilityRequest(
                capability,
                {"snapshot": {}, "padding": "x" * 300_000},
                "private", "malformed request",
            ))
    finally:
        adapter.stop()


def test_response_timeout_terminates_worker_instead_of_accepting_late_reply(
    tmp_path,
):
    adapter = ResearchModuleProcessAdapter(
        package_digest="d" * 64,
        host_identity="host:test",
        runtime_dir=tmp_path / "runtime",
    )
    adapter.start(epoch=10)
    adapter.response_timeout_seconds = 0.0
    capability, handler = adapter.capability_registrations()[0]
    with pytest.raises(TimeoutError, match="deadline"):
        handler(CapabilityRequest(
            capability,
            {"snapshot": snapshot(datetime.now(timezone.utc))},
            "private", "force bounded timeout",
        ))
    assert adapter.observe().state is ProcessState.STOPPED


def test_signed_run_activation_owns_real_process_and_shutdown(
    canonical_state_path, tmp_path,
):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    package = verified_custom(
        tmp_path, directory="signed-research",
        capabilities=(RESEARCH_CAPABILITY_ID,),
    )
    system = CapabilitySystem(authorization_checker=lambda request: True)
    lifecycle = ModuleLifecycleCommandService(
        state_path=canonical_state_path,
        store_root=tmp_path / "module-store",
        capability_system=system,
    )
    found = lifecycle.discover(package, now=now)
    approval_id, _ = authorize(
        canonical_state_path, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED, now=now,
    )
    approved = lifecycle.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approval_id, now=now,
    )
    stage_id, _ = authorize(
        canonical_state_path, operation="stage", record=approved,
        target=ModuleLifecycle.STAGED, now=now,
    )
    staged = lifecycle.stage(
        package, expected_revision=approved.revision,
        approval_id=stage_id, now=now,
    )
    activation_id, _ = authorize(
        canonical_state_path, operation="activate", record=staged,
        target=ModuleLifecycle.ACTIVATING,
        profile=OperationProfileKind.OBSERVE, now=now,
    )
    store = DurableWorkStore(canonical_state_path)
    manager = TaskExecutionManager(store, {}, max_workers=1)
    factories = AdapterFactoryRegistry()
    factories.register(ReviewedResearchProcessFactory(
        package_digest=package.package_digest,
        host_identity="host:test",
        runtime_dir=tmp_path / "runtime",
        platform_target=ModulePlatformTarget(
            "linux-x86_64", "1.0.0", (),
            (("cpu_millis", 100), ("ram_mib", 128)),
            ("subprocess-restricted",),
        ),
    ))
    coordinator = ModuleOperationCoordinator(
        state_path=canonical_state_path, lifecycle=lifecycle,
        factories=factories, work_store=store, manager=manager,
    )
    request = ModuleOperationRequest(
        request_id=f"request:{uuid4()}", idempotency_key="research:process:v1",
        module_id=RESEARCH_MODULE_ID, package_digest=package.package_digest,
        operation=ModuleOperationType.ACTIVATE,
        expected_revision=staged.revision,
        source_lifecycle=ModuleLifecycle.STAGED,
        destination_lifecycle=ModuleLifecycle.ACTIVE,
        profile=OperationProfileKind.OBSERVE,
        principal=local_sparks_principal(),
        principal_attestation_ref=activation_id, approval_id=activation_id,
        component_id=RESEARCH_COMPONENT_ID, host_identity="host:test",
        deadline=now + timedelta(minutes=5), correlation_id="corr:research-process",
        resource_lease_refs=(), device_lease_refs=(),
        requested_effect="start exact reviewed research process",
        cancellation_policy=ModuleCancellationPolicy.BEFORE_EXTERNAL_DISPATCH_ONLY,
    )
    try:
        job = coordinator.submit(request, now=now)
        manager.tick(now=now)
        for _ in range(300):
            settled = store.get(job.job_id)
            if settled.status in {
                WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.UNCERTAIN,
            }:
                break
            sleep(0.01)
        assert settled.status is WorkStatus.COMPLETED
        assert lifecycle.describe(RESEARCH_MODULE_ID).lifecycle is ModuleLifecycle.ACTIVE
        capability = system.resolve(RESEARCH_CAPABILITY_ID)
        result = system.execute(CapabilityRequest(
            capability, {"snapshot": snapshot(datetime.now(timezone.utc))},
            "private", "execute isolated research capability",
        ))
        assert result.kind is CapabilityResultKind.SUCCESS
        manager.close(wait=True)
        coordinator.close()
        after = system.execute(CapabilityRequest(
            capability, {"snapshot": snapshot(datetime.now(timezone.utc))},
            "private", "worker must be stopped",
        ))
        assert after.kind is CapabilityResultKind.UNAVAILABLE
    finally:
        manager.close(wait=True)
        coordinator.close()
