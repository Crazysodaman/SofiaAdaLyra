from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event
from time import sleep
from uuid import uuid4
import sqlite3

import pytest

from sofia.core.social.principals import local_sparks_principal
from sofia.platform.application.module_lifecycle import ModuleLifecycleCommandService
from sofia.platform.capability import Capability, CapabilitySystem
from sofia.platform.modules import (
    AdapterFactoryContract,
    AdapterFactoryRegistry,
    AdapterInspection,
    ModuleAttemptStatus,
    ModuleCancellationPolicy,
    ModuleLifecycle,
    ModuleOperationCoordinator,
    ModuleOperationRequest,
    ModuleOperationType,
    ModulePlatformTarget,
    OperationProfileKind,
    ReviewedAdapterFactory,
    ReviewedModuleAdapter,
)
from sofia.platform.run import (
    DurableWorkStore,
    ProcessState,
    RuntimeObservation,
    TaskExecutionManager,
    WorkStatus,
)
from sofia.platform.modules import CanonicalPlatformModuleObserver
from sofia.core.modreg.platform import ModuleObservationKind, OutcomeStatus
from sofia.core.modreg.self_model import CapabilitySelfModel, Grounding
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.operator_stop import OperatorStopStore
from test.test_module_lifecycle_v1 import verified_package
from test.test_platform_module_command_service import authorize


NOW = datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture(autouse=True)
def _fresh_operation_clock():
    """Keep bounded approvals/deadlines fresh after long suite collection."""
    global NOW
    NOW = datetime.now(timezone.utc).replace(microsecond=0)


class Adapter(ReviewedModuleAdapter):
    def __init__(self, package_digest, *, fail_start=False, observed_at=None):
        self.package_digest = package_digest
        self.fail_start = fail_start
        self.observed_at = observed_at or datetime.now(timezone.utc)
        self.state = ProcessState.STOPPED
        self.starts = 0

    def inspect(self):
        return AdapterInspection(
            "org.sofia.research", self.package_digest, "research.worker",
            "host:test", self.state, self.state is ProcessState.RUNNING,
            "probe:research-worker", self.observed_at,
        )

    def observe(self):
        return RuntimeObservation(
            self.state, ready=self.state is ProcessState.RUNNING,
        )

    def start(self, *, epoch):
        self.starts += 1
        if self.fail_start:
            raise RuntimeError("transport disappeared")
        self.state = ProcessState.RUNNING

    def stop(self):
        self.state = ProcessState.STOPPED

    def capability_registrations(self):
        return ((Capability("research.search", "reviewed search"), lambda request: {}),)


class Factory(ReviewedAdapterFactory):
    def __init__(self, package_digest, adapter):
        self.adapter = adapter
        self._contract = AdapterFactoryContract(
            "factory:research", "org.sofia.research",
            frozenset({package_digest}), frozenset({"research.worker"}),
            ("sofia.module.adapter.v1",),
            frozenset({OperationProfileKind.OBSERVE}),
            frozenset({"module.activate"}), "subprocess-restricted",
            (("cpu_millis", 100), ("ram_mib", 128)),
            frozenset({"host:test"}), frozenset(), True, True, False,
        )

    @property
    def contract(self):
        return self._contract

    @property
    def platform_target(self):
        return ModulePlatformTarget(
            "linux-x86_64", "1.0.0", (),
            (("cpu_millis", 100), ("ram_mib", 128)),
            ("subprocess-restricted",),
        )

    def reconstruct_for_inspection(
        self, *, package, profile, component_id, host_identity,
    ):
        assert package.package_digest in self.contract.package_digests
        assert profile is OperationProfileKind.OBSERVE
        assert component_id == "research.worker"
        assert host_identity == "host:test"
        return self.adapter


def prepared(
    canonical_state_path, tmp_path, *, register_factory=True, fail_start=False,
    now=None,
):
    # This helper is imported by several package suites.  A module-level clock
    # becomes expired when collection/execution crosses a validity boundary,
    # so derive the bounded authorization window at fixture invocation unless
    # a deterministic scenario clock is explicitly supplied.
    operation_now = now or datetime.now(timezone.utc).replace(microsecond=0)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    lifecycle = ModuleLifecycleCommandService(
        state_path=canonical_state_path,
        store_root=tmp_path / "module-store",
        capability_system=system,
    )
    package = verified_package(tmp_path)
    found = lifecycle.discover(package, now=operation_now)
    approval_id, _ = authorize(
        canonical_state_path, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED, now=operation_now,
    )
    approved = lifecycle.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approval_id, now=operation_now,
    )
    stage_id, _ = authorize(
        canonical_state_path, operation="stage", record=approved,
        target=ModuleLifecycle.STAGED, now=operation_now,
    )
    staged = lifecycle.stage(
        package, expected_revision=approved.revision,
        approval_id=stage_id, now=operation_now,
    )
    activation_id, parameters = authorize(
        canonical_state_path, operation="activate", record=staged,
        target=ModuleLifecycle.ACTIVATING,
        profile=OperationProfileKind.OBSERVE, now=operation_now,
    )
    store = DurableWorkStore(canonical_state_path)
    manager = TaskExecutionManager(store, {}, max_workers=1)
    factories = AdapterFactoryRegistry()
    adapter = Adapter(
        package.package_digest, fail_start=fail_start,
        observed_at=operation_now,
    )
    if register_factory:
        factories.register(Factory(package.package_digest, adapter))
    coordinator = ModuleOperationCoordinator(
        state_path=canonical_state_path, lifecycle=lifecycle,
        factories=factories, work_store=store, manager=manager,
    )
    request = ModuleOperationRequest(
        request_id=f"request:{uuid4()}", idempotency_key="activation:research:v1",
        module_id=staged.module_id, package_digest=staged.package_digest,
        operation=ModuleOperationType.ACTIVATE,
        expected_revision=staged.revision,
        source_lifecycle=ModuleLifecycle.STAGED,
        destination_lifecycle=ModuleLifecycle.ACTIVE,
        profile=OperationProfileKind.OBSERVE,
        principal=local_sparks_principal(),
        principal_attestation_ref=activation_id, approval_id=activation_id,
        component_id="research.worker", host_identity="host:test",
        deadline=operation_now + timedelta(minutes=5), correlation_id="corr:research",
        resource_lease_refs=(), device_lease_refs=(),
        requested_effect="start reviewed research worker",
        cancellation_policy=ModuleCancellationPolicy.BEFORE_EXTERNAL_DISPATCH_ONLY,
    )
    return lifecycle, coordinator, manager, store, adapter, request, parameters


def test_prepared_request_window_is_fresh_and_expiration_still_fails_closed(
    canonical_state_path, tmp_path,
):
    _lifecycle, coordinator, manager, _store, _adapter, request, _ = prepared(
        canonical_state_path, tmp_path,
    )
    moment = datetime.now(timezone.utc)
    try:
        assert request.deadline > moment
        expired = replace(
            request,
            request_id=f"request:{uuid4()}",
            idempotency_key="activation:research:expired",
            deadline=moment - timedelta(seconds=1),
        )
        with pytest.raises(ValueError, match="request expired"):
            coordinator.submit(expired, now=moment)
    finally:
        manager.close(wait=True)


def finish(manager, store, job_id):
    manager.tick(now=datetime.now(timezone.utc))
    for _ in range(200):
        job = store.get(job_id)
        if job.status in {
            WorkStatus.COMPLETED, WorkStatus.FAILED,
            WorkStatus.CANCELLED, WorkStatus.UNCERTAIN,
        }:
            return job
        sleep(0.005)
    raise AssertionError("RUN job did not settle")


def pause_request(canonical_state_path, active, request):
    approval_id, _ = authorize(
        canonical_state_path, operation="pause", record=active,
        target=ModuleLifecycle.PAUSED, now=datetime.now(timezone.utc),
    )
    return replace(
        request,
        request_id=f"request:{uuid4()}",
        idempotency_key="pause:research:v1",
        operation=ModuleOperationType.PAUSE,
        expected_revision=active.revision,
        source_lifecycle=ModuleLifecycle.ACTIVE,
        destination_lifecycle=ModuleLifecycle.PAUSED,
        principal_attestation_ref=approval_id,
        approval_id=approval_id,
        correlation_id="corr:research-pause",
        requested_effect="drain exact research worker",
        cancellation_policy=ModuleCancellationPolicy.COOPERATIVE_SAFE_STOP,
        deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
    )


def test_durable_activation_uses_shared_run_and_verified_observation(
    canonical_state_path, tmp_path,
):
    lifecycle, coordinator, manager, store, adapter, request, _ = prepared(
        canonical_state_path, tmp_path,
    )
    try:
        job = coordinator.submit(request, now=NOW)
        duplicate = coordinator.submit(request, now=NOW)
        assert duplicate.job_id == job.job_id
        settled = finish(manager, store, job.job_id)
        assert settled.status is WorkStatus.COMPLETED
        assert adapter.starts == 1
        assert lifecycle.describe(request.module_id).lifecycle is ModuleLifecycle.ACTIVE
        assert [event.status.value for event in coordinator.attempts(request.request_id)] == [
            "admitted", "running", "external_effect_attempted",
            "externally_verified_success",
        ]
        assert settled.result["evidence_ref"] == "probe:research-worker"
        [health] = CanonicalPlatformModuleObserver(
            canonical_state_path,
        ).health()
        assert health.health is ModuleObservationKind.HEALTHY
        assert health.host_identity == "host:test"
        [outcome] = CanonicalPlatformModuleObserver(
            canonical_state_path,
        ).outcomes()
        assert outcome.request_id == request.request_id
        assert outcome.module_id == request.module_id
        assert outcome.capability == "module.activate"
        assert outcome.status is OutcomeStatus.SUCCEEDED_VERIFIED
        assert outcome.verification_method == "authenticated-adapter-probe"
        assert outcome.error_class is None
        first_page = CanonicalPlatformModuleObserver(
            canonical_state_path,
        ).outcome_page(after_cursor=None, limit=1)
        assert first_page.outcomes == (outcome,)
        assert first_page.next_cursor is not None
        assert not first_page.has_more
        assert CanonicalPlatformModuleObserver(
            canonical_state_path,
        ).outcome_page(
            after_cursor=first_page.next_cursor, limit=1,
        ).outcomes == ()
        [placement] = CanonicalPlatformModuleObserver(
            canonical_state_path,
        ).placements()
        assert placement.module_id == request.module_id
        assert placement.component == request.component_id
        assert placement.host_identity == request.host_identity
        assert placement.placement_mode.value == "portable_stateless"
        assert placement.eligible_hosts == ()
        assert placement.device_affinity is None
        [awareness] = CapabilitySelfModel(
            None, CanonicalPlatformModuleObserver(canonical_state_path),
        ).project(now=datetime.now(timezone.utc))
        assert awareness.module_id == request.module_id
        assert awareness.verified_outcomes == 1
        assert awareness.unverified_outcomes == 0
        assert awareness.placements == ((
            request.component_id,
            request.host_identity,
            "portable_stateless",
        ),)
        assert all(
            aspect.grant_state is Grounding.UNKNOWN
            for aspect in awareness.permission_aspects
        )
        manager.close(wait=True)
        coordinator.close()
    finally:
        manager.close(wait=True)
        coordinator.close()
        assert adapter.state is ProcessState.STOPPED


def test_changed_idempotency_payload_is_rejected(canonical_state_path, tmp_path):
    _, coordinator, manager, _, _, request, _ = prepared(canonical_state_path, tmp_path)
    try:
        coordinator.submit(request, now=NOW)
        # Admission/queueing is not a settled execution outcome.
        assert CanonicalPlatformModuleObserver(canonical_state_path).outcomes() == ()
        changed = replace(
            request, request_id=f"request:{uuid4()}",
            requested_effect="different effect",
        )
        with pytest.raises(RuntimeError, match="fingerprint collision|idempotency"):
            coordinator.submit(changed, now=NOW)
    finally:
        manager.close(wait=True)


def test_verified_process_with_failed_lifecycle_commit_is_uncertain_and_owned(
    canonical_state_path, tmp_path, monkeypatch,
):
    lifecycle, coordinator, manager, store, adapter, request, _ = prepared(
        canonical_state_path, tmp_path,
    )
    def fail_commit(*args, **kwargs):
        raise sqlite3.OperationalError("injected lifecycle commit fault")
    monkeypatch.setattr(lifecycle, "complete_activation", fail_commit)
    try:
        job = coordinator.submit(request, now=NOW)
        settled = finish(manager, store, job.job_id)
        assert settled.status is WorkStatus.UNCERTAIN
        assert settled.reason == "external_module_running_lifecycle_commit_unknown"
        assert adapter.state is ProcessState.RUNNING
        assert coordinator.attempts(request.request_id)[-1].status is (
            ModuleAttemptStatus.OUTCOME_UNKNOWN
        )
        manager.close(wait=True)
        coordinator.close()
    finally:
        manager.close(wait=True)
        coordinator.close()


def test_ambiguous_process_pause_stays_draining_and_is_not_replayed(
    canonical_state_path, tmp_path,
):
    lifecycle, coordinator, manager, store, adapter, request, _ = prepared(
        canonical_state_path, tmp_path,
    )
    original_stop = adapter.stop
    try:
        activation = coordinator.submit(request, now=NOW)
        assert finish(manager, store, activation.job_id).status is WorkStatus.COMPLETED
        active = lifecycle.describe(request.module_id)
        pause = pause_request(canonical_state_path, active, request)
        def uncertain_stop():
            raise RuntimeError("stop receipt lost")
        adapter.stop = uncertain_stop
        job = coordinator.submit(pause, now=datetime.now(timezone.utc))
        settled = finish(manager, store, job.job_id)
        assert settled.status is WorkStatus.UNCERTAIN
        assert settled.reason == "external_module_pause_outcome_unknown"
        assert lifecycle.describe(request.module_id).lifecycle is ModuleLifecycle.DRAINING
        assert lifecycle.manager.capability_system.capability_names() == ()
        duplicate = coordinator.submit(pause, now=datetime.now(timezone.utc))
        assert duplicate.job_id == job.job_id
        assert adapter.starts == 1
    finally:
        adapter.stop = original_stop
        manager.close(wait=True)
        coordinator.close()
        assert adapter.state is ProcessState.STOPPED


def test_stale_verified_activation_is_history_not_current_placement(
    canonical_state_path, tmp_path,
):
    _, coordinator, manager, store, _, request, _ = prepared(
        canonical_state_path, tmp_path,
    )
    try:
        job = coordinator.submit(request, now=NOW)
        assert finish(manager, store, job.job_id).status is WorkStatus.COMPLETED
        stale = datetime.now(timezone.utc) - timedelta(minutes=10)
        with sqlite3.connect(canonical_state_path) as db:
            db.execute(
                "UPDATE platform_module_operation_attempt SET occurred_at=? "
                "WHERE request_id=?",
                (stale.isoformat(), request.request_id),
            )

        observer = CanonicalPlatformModuleObserver(canonical_state_path)
        assert observer.placements() == ()
        [health] = observer.health()
        assert health.health is ModuleObservationKind.UNKNOWN_STATE
        # The settled fact remains historical evidence; freshness controls
        # only claims about current health and placement.
        [outcome] = observer.outcomes()
        assert outcome.status is OutcomeStatus.SUCCEEDED_VERIFIED
    finally:
        manager.close(wait=True)


def test_missing_factory_fails_before_consuming_approval(
    canonical_state_path, tmp_path,
):
    lifecycle, coordinator, manager, store, _, request, parameters = prepared(
        canonical_state_path, tmp_path, register_factory=False,
    )
    try:
        job = coordinator.submit(request, now=NOW)
        settled = finish(manager, store, job.job_id)
        assert settled.status is WorkStatus.FAILED
        assert lifecycle.describe(request.module_id).lifecycle is ModuleLifecycle.STAGED
        assert ExecutionApprovalVerifier(canonical_state_path).matches_unconsumed(
            approval_id=request.approval_id, capability="module.activate",
            parameters=parameters, now=NOW + timedelta(seconds=2),
        )
    finally:
        manager.close(wait=True)


def test_dispatch_failure_is_uncertain_and_never_replayed_after_recovery(
    canonical_state_path, tmp_path,
):
    lifecycle, coordinator, manager, store, adapter, request, _ = prepared(
        canonical_state_path, tmp_path, fail_start=True,
    )
    job = coordinator.submit(request, now=NOW)
    settled = finish(manager, store, job.job_id)
    assert settled.status is WorkStatus.UNCERTAIN
    assert adapter.starts == 1
    assert lifecycle.describe(request.module_id).lifecycle is ModuleLifecycle.ACTIVATING
    [outcome] = CanonicalPlatformModuleObserver(
        canonical_state_path,
    ).outcomes()
    assert outcome.status is OutcomeStatus.OUTCOME_UNKNOWN
    assert outcome.verification_method is None
    assert outcome.error_class == "external_outcome_unknown"
    manager.close(wait=True)

    recovered_manager = TaskExecutionManager(store, {}, max_workers=1)
    recovered = ModuleOperationCoordinator(
        state_path=canonical_state_path, lifecycle=lifecycle,
        factories=coordinator.factories, work_store=store,
        manager=recovered_manager,
    )
    try:
        store.recover(now=NOW + timedelta(minutes=1))
        assert recovered_manager.tick(now=NOW + timedelta(minutes=1)) == 0
        assert store.get(job.job_id).status is WorkStatus.UNCERTAIN
        assert adapter.starts == 1
        assert recovered.attempts(request.request_id)[-1].status.value == "outcome_unknown"
    finally:
        recovered_manager.close(wait=True)


def test_uncertain_activation_reconciles_from_probe_without_replaying_start(
    canonical_state_path, tmp_path,
):
    lifecycle, coordinator, manager, store, adapter, request, _ = prepared(
        canonical_state_path, tmp_path, fail_start=True,
    )
    try:
        job = coordinator.submit(request, now=NOW)
        assert finish(manager, store, job.job_id).status is WorkStatus.UNCERTAIN
        assert adapter.starts == 1
        # The transport may have applied the external start before its reply
        # disappeared.  Recovery is allowed to inspect, never to call start.
        adapter.fail_start = False
        adapter.state = ProcessState.RUNNING
        result = coordinator.reconcile(
            request.request_id, now=NOW + timedelta(seconds=2),
        )
        assert result.value == "externally_verified_success"
        assert adapter.starts == 1
        assert lifecycle.describe(request.module_id).lifecycle is ModuleLifecycle.ACTIVE
        assert store.get(job.job_id).status is WorkStatus.UNCERTAIN
    finally:
        manager.close(wait=True)


def test_uncertain_stopped_probe_quarantines_without_replaying_start(
    canonical_state_path, tmp_path,
):
    lifecycle, coordinator, manager, store, adapter, request, _ = prepared(
        canonical_state_path, tmp_path, fail_start=True,
    )
    try:
        job = coordinator.submit(request, now=NOW)
        assert finish(manager, store, job.job_id).status is WorkStatus.UNCERTAIN
        result = coordinator.reconcile(
            request.request_id, now=NOW + timedelta(seconds=2),
        )
        assert result.value == "externally_verified_failure"
        assert adapter.starts == 1
        assert lifecycle.describe(request.module_id).lifecycle is ModuleLifecycle.QUARANTINED
    finally:
        manager.close(wait=True)


def test_stop_denies_activation_without_consuming_approval(
    canonical_state_path, tmp_path,
):
    lifecycle, coordinator, manager, store, adapter, request, parameters = prepared(
        canonical_state_path, tmp_path,
    )
    OperatorStopStore(canonical_state_path).set(
        active=True, updated_by="Sparks", reason="owner stop", at=NOW,
    )
    try:
        job = coordinator.submit(request, now=NOW)
        settled = finish(manager, store, job.job_id)
        assert settled.status is WorkStatus.FAILED
        assert adapter.starts == 0
        assert lifecycle.describe(request.module_id).lifecycle is ModuleLifecycle.STAGED
        assert ExecutionApprovalVerifier(canonical_state_path).matches_unconsumed(
            approval_id=request.approval_id, capability="module.activate",
            parameters=parameters, now=NOW + timedelta(seconds=2),
        )
    finally:
        manager.close(wait=True)


def test_queued_cancellation_never_dispatches(canonical_state_path, tmp_path):
    _, coordinator, manager, store, adapter, request, _ = prepared(
        canonical_state_path, tmp_path,
    )
    try:
        job = coordinator.submit(request, now=NOW)
        cancelled = manager.cancel(job.job_id, now=NOW + timedelta(seconds=1))
        assert cancelled.status is WorkStatus.CANCELLED
        assert manager.tick(now=NOW + timedelta(seconds=2)) == 0
        assert adapter.starts == 0
    finally:
        manager.close(wait=True)
