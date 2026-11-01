"""G2-E: Core-free MODULE_HOST state ownership and remote authority.

These tests exercise the real production lifecycle manager, command service,
settings boundary, local RUN work store, and operation coordinator against a
Platform-local store that must never touch a canonical ``sofia.db``.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.platform.application.module_lifecycle import ModuleLifecycleCommandService
from sofia.platform.capability import Capability, CapabilitySystem
from sofia.platform.config.roles import (
    PlatformRole,
    PlatformRoleConfiguration,
)
from sofia.platform.modules import (
    AdapterFactoryRegistry,
    ModuleLifecycle,
    ModuleOperationCoordinator,
    ModuleOperationRequest,
    ModuleOperationType,
    ModuleCancellationPolicy,
    OperationProfileKind,
)
from sofia.platform.modules.host_authority import (
    ImportedApprovalBinding,
    LocalModuleAuthority,
)
from sofia.platform.run import DurableWorkStore, TaskExecutionManager, WorkStatus
from sofia.platform.safe.execution_approval import (
    ExecutionApproval,
    execution_fingerprint,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.platform.state.local_store import (
    PlatformHostBinding,
    PlatformLocalStore,
)
from sofia.core.social.principals import local_sparks_principal
from test.test_module_lifecycle_v1 import (
    compatibility,
    verified_custom,
    verified_package,
)
from test.test_platform_module_operations import Adapter, Factory, finish


NOW = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)

MODULE_HOST_ROLES = PlatformRoleConfiguration((PlatformRole.MODULE_HOST,))
CORE_ONLY_ROLES = PlatformRoleConfiguration((PlatformRole.CORE_HOST,))


def local_store(tmp_path, *, host="host:venus", roles=MODULE_HOST_ROLES):
    path = tmp_path / "platform-local" / "module_host.db"
    return PlatformLocalStore(path, roles=roles, host_identity=host)


def command_service(tmp_path, store, *, system=None):
    return ModuleLifecycleCommandService(
        state_path=store.path,
        store_root=tmp_path / "module-store",
        capability_system=(
            system if system is not None
            else CapabilitySystem(authorization_checker=lambda request: True)
        ),
        storage=store,
    )


def import_receipt(store, authority, approval, *, host=None, core=None):
    binding = store.binding
    authority.import_core_approval(
        approval,
        binding=ImportedApprovalBinding(
            core_identity=core or binding.core_identity,
            host_identity=host or binding.host_identity,
            imported_at=NOW,
        ),
    )
    return approval


def authorize(
    store, authority, *, operation, record, target, profile=None,
    now=NOW, expires_at=None,
):
    parameters = {
        "module_id": record.module_id,
        "version": record.version,
        "package_digest": record.package_digest,
        "expected_revision": record.revision,
        "target_lifecycle": target.value,
        "profile": None if profile is None else profile.value,
    }
    approval = ExecutionApproval(
        approval_id=str(uuid4()),
        capability=f"module.{operation}",
        request_fingerprint=execution_fingerprint(f"module.{operation}", parameters),
        approved_by="Sparks",
        approved_at=now,
        expires_at=expires_at or (now + timedelta(minutes=5)),
    )
    import_receipt(store, authority, approval)
    return approval.approval_id, parameters


def prepared_stage(tmp_path, store, service, authority, package=None):
    package = package or verified_package(tmp_path)
    found = service.discover(package, now=NOW)
    approve_id, _ = authorize(
        store, authority, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED, now=NOW,
    )
    approved = service.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approve_id, now=NOW,
    )
    stage_id, _ = authorize(
        store, authority, operation="stage", record=approved,
        target=ModuleLifecycle.STAGED, now=NOW,
    )
    staged = service.stage(
        package, expected_revision=approved.revision,
        approval_id=stage_id, now=NOW,
    )
    return staged, package


def activate_approvals(tmp_path, store, authority, service, staged, package):
    """Begin one verified reviewable activation against local storage."""
    activation_id, _ = authorize(
        store, authority, operation="activate", record=staged,
        target=ModuleLifecycle.ACTIVATING,
        profile=OperationProfileKind.OBSERVE, now=NOW,
    )
    return activation_id


def test_module_host_initializes_without_canonical_core_state(tmp_path):
    canonical = tmp_path / "sofia.db"
    assert not canonical.exists()
    store = local_store(tmp_path)
    service = command_service(tmp_path, store)
    assert store.binding.host_identity == "host:venus"
    assert PlatformRole.MODULE_HOST in store.binding.roles
    assert store.binding.core_identity is None
    package = verified_package(tmp_path)
    found = service.discover(package, now=NOW)
    assert found.lifecycle is ModuleLifecycle.VALIDATED
    assert LocalModuleAuthority(store).current().active is False
    assert not canonical.exists()


def test_module_host_role_declaration_is_required(tmp_path):
    with pytest.raises(PermissionError, match="MODULE_HOST role"):
        PlatformLocalStore(
            tmp_path / "module_host.db", roles=CORE_ONLY_ROLES,
            host_identity="host:venus",
        )
    with pytest.raises(ValueError, match="MODULE_HOST"):
        PlatformHostBinding(
            host_identity="host:venus", roles=(PlatformRole.CORE_HOST,),
            core_identity=None, created_at=NOW,
        )


def test_local_binding_refuses_other_hosts_and_roles(tmp_path):
    path = tmp_path / "module_host.db"
    store = PlatformLocalStore(
        path, roles=MODULE_HOST_ROLES, host_identity="host:venus",
    )
    reopened = PlatformLocalStore(
        path, roles=MODULE_HOST_ROLES, host_identity="host:venus",
    )
    assert reopened.binding.host_identity == "host:venus"
    assert reopened.binding.created_at == store.binding.created_at
    with pytest.raises(RuntimeError, match="another host identity"):
        PlatformLocalStore(
            path, roles=MODULE_HOST_ROLES, host_identity="host:artemis",
        )
    with pytest.raises(RuntimeError, match="role binding differs"):
        PlatformLocalStore(
            path,
            roles=PlatformRoleConfiguration(
                (PlatformRole.MODULE_HOST, PlatformRole.STANDBY),
            ),
            host_identity="host:venus",
        )
    with pytest.raises(RuntimeError, match="unavailable"):
        PlatformLocalStore(
            tmp_path / "missing.db", roles=MODULE_HOST_ROLES,
            host_identity="host:venus", create=False,
        )
    # A canonical Core database must never be adopted as local module state.
    canonical = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    with pytest.raises(RuntimeError, match="application identity"):
        PlatformLocalStore(
            canonical, roles=MODULE_HOST_ROLES, host_identity="host:venus",
        )
    assert canonical.exists()


def test_remote_core_binding_is_exact_and_refuses_another_core(tmp_path):
    store = local_store(tmp_path)
    authority = LocalModuleAuthority(store)
    orphan = ExecutionApproval(
        approval_id="approval:orphan", capability="module.approve",
        request_fingerprint=execution_fingerprint("module.approve", {}),
        approved_by="Sparks", approved_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    with pytest.raises(PermissionError, match="bound remote Core"):
        authority.import_core_approval(
            orphan,
            binding=ImportedApprovalBinding(
                core_identity="core:artemis", host_identity="host:venus",
                imported_at=NOW,
            ),
        )
    store.bind_core("core:artemis", now=NOW)
    assert store.binding.core_identity == "core:artemis"
    with pytest.raises(RuntimeError, match="another Core identity"):
        store.bind_core("core:other", now=NOW)


def test_approval_binding_to_wrong_host_or_core_is_rejected(tmp_path):
    store = local_store(tmp_path)
    store.bind_core("core:artemis", now=NOW)
    authority = LocalModuleAuthority(store)
    approval = ExecutionApproval(
        approval_id="approval:host-swap", capability="module.approve",
        request_fingerprint=execution_fingerprint("module.approve", {}),
        approved_by="Sparks", approved_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    with pytest.raises(PermissionError, match="exact host identity"):
        authority.import_core_approval(
            approval,
            binding=ImportedApprovalBinding(
                core_identity="core:artemis", host_identity="host:OTHER",
                imported_at=NOW,
            ),
        )
    with pytest.raises(PermissionError, match="bound remote Core"):
        authority.import_core_approval(
            approval,
            binding=ImportedApprovalBinding(
                core_identity="core:OTHER", host_identity="host:venus",
                imported_at=NOW,
            ),
        )
    exact_binding = ImportedApprovalBinding(
        core_identity="core:artemis", host_identity="host:venus",
        imported_at=NOW,
    )
    authority.import_core_approval(approval, binding=exact_binding)
    # Idempotent exact duplicate import keeps Core Link delivery replay safe.
    authority.import_core_approval(approval, binding=exact_binding)
    with pytest.raises(PermissionError, match="conflicts"):
        authority.import_core_approval(
            ExecutionApproval(
                approval_id="approval:host-swap",
                capability="module.quarantine",
                request_fingerprint=approval.request_fingerprint,
                approved_by="Sparks", approved_at=NOW,
                expires_at=NOW + timedelta(minutes=5),
            ),
            binding=exact_binding,
        )


def test_lifecycle_authorization_consumes_exact_remote_receipts_once(tmp_path):
    store = local_store(tmp_path)
    store.bind_core("core:artemis", now=NOW)
    authority = LocalModuleAuthority(store)
    service = command_service(tmp_path, store)
    package = verified_package(tmp_path)
    found = service.discover(package, now=NOW)

    with pytest.raises(PermissionError, match="not authorized"):
        service.approve(
            found.module_id, expected_revision=found.revision,
            approval_id="approval:missing", now=NOW,
        )

    approval_id, parameters = authorize(
        store, authority, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED, now=NOW,
    )
    approved = service.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approval_id, now=NOW,
    )
    assert approved.lifecycle is ModuleLifecycle.APPROVED
    # The receipt was consumed exactly once; replay fails closed.
    with pytest.raises(PermissionError, match="not authorized"):
        service.approve(
            found.module_id, expected_revision=approved.revision,
            approval_id=approval_id, now=NOW,
        )
    with pytest.raises(PermissionError, match="already consumed"):
        authority.consume(
            approval_id=approval_id, capability="module.approve",
            parameters=parameters, now=NOW,
        )


def test_revoked_and_expired_remote_receipts_fail_closed(tmp_path):
    store = local_store(tmp_path)
    store.bind_core("core:artemis", now=NOW)
    authority = LocalModuleAuthority(store)
    service = command_service(tmp_path, store)
    staged, package = prepared_stage(tmp_path, store, service, authority)
    binding = ImportedApprovalBinding(
        core_identity="core:artemis", host_identity="host:venus",
        imported_at=NOW,
    )

    # A receipt bound for later use is revoked before consumption.
    revoked_id, revoked_parameters = authorize(
        store, authority, operation="activate", record=staged,
        target=ModuleLifecycle.ACTIVATING,
        profile=OperationProfileKind.OBSERVE, now=NOW,
    )
    authority.revoke_core_approval(revoked_id, binding=binding)
    authority.revoke_core_approval(revoked_id, binding=binding)
    with pytest.raises(PermissionError, match="not authorized"):
        service.begin_activation(
            package, expected_revision=staged.revision,
            profile=OperationProfileKind.OBSERVE,
            compatibility=compatibility(package),
            registrations=((
                Capability("research.search", "reviewed search"),
                lambda request: {},
            ),),
            approval_id=revoked_id, now=NOW,
        )
    assert service.describe(staged.module_id).lifecycle is ModuleLifecycle.STAGED
    assert registry_names(service) == ()
    with pytest.raises(PermissionError, match="remotely revoked"):
        authority.consume(
            approval_id=revoked_id, capability="module.activate",
            parameters=revoked_parameters, now=NOW,
        )

    # Drawing from an expired receipt can never authorize either.
    expired_id, _ = authorize(
        store, authority, operation="activate", record=staged,
        target=ModuleLifecycle.ACTIVATING,
        profile=OperationProfileKind.OBSERVE, now=NOW - timedelta(minutes=2),
        expires_at=NOW - timedelta(minutes=1),
    )
    with pytest.raises(PermissionError, match="not authorized"):
        service.begin_activation(
            package, expected_revision=staged.revision,
            profile=OperationProfileKind.OBSERVE,
            compatibility=compatibility(package),
            registrations=((
                Capability("research.search", "reviewed search"),
                lambda request: {},
            ),),
            approval_id=expired_id, now=NOW,
        )
    assert service.describe(staged.module_id).lifecycle is ModuleLifecycle.STAGED


def registry_names(service):
    return service.manager.capability_system.capability_names()


def test_module_host_stop_mirrors_owner_and_blocks_then_allows(tmp_path):
    store = local_store(tmp_path)
    store.bind_core("core:artemis", now=NOW)
    authority = LocalModuleAuthority(store)
    service = command_service(tmp_path, store)
    package = verified_package(tmp_path)
    found = service.discover(package, now=NOW)
    with pytest.raises(PermissionError, match="owner"):
        authority.mirror_operator_stop(
            active=True, updated_by="principal:other",
            reason="attempted stop injection", at=NOW,
        )
    authority.mirror_operator_stop(
        active=True, updated_by="Sparks", reason="owner emergency stop", at=NOW,
    )
    assert authority.current().active is True
    approval_id, _ = authorize(
        store, authority, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED, now=NOW,
    )
    with pytest.raises(PermissionError, match="not authorized"):
        service.approve(
            found.module_id, expected_revision=found.revision,
            approval_id=approval_id, now=NOW,
        )
    assert service.describe(found.module_id).lifecycle is ModuleLifecycle.VALIDATED
    authority.mirror_operator_stop(
        active=False, updated_by="Sparks", reason="owner resumed autonomy",
        at=NOW,
    )
    assert authority.current().active is False
    approved = service.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approval_id, now=NOW,
    )
    assert approved.lifecycle is ModuleLifecycle.APPROVED


def test_module_settings_use_platform_local_state(tmp_path):
    from sofia.sdk import (
        ModuleSettingApplyClass,
        ModuleSettingField,
        ModuleSettingType,
        ModuleSettingsContract,
    )

    store = local_store(tmp_path)
    store.bind_core("core:artemis", now=NOW)
    authority = LocalModuleAuthority(store)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    service = ModuleLifecycleCommandService(
        state_path=store.path, store_root=tmp_path / "module-store",
        capability_system=system, storage=store,
    )
    contract = ModuleSettingsContract(
        "sofia.module.settings.v1", 1, (
            ModuleSettingField(
                "display.mode", "Display mode", ModuleSettingType.STRING,
                ModuleSettingApplyClass.COMPONENT_RESTART, required=True,
            ),
        ),
    )
    package = verified_custom(
        tmp_path, directory="local-settings-package",
        module_id="org.sofia.localsettings", version="4.0.0",
        schema_version=3, settings_contract=contract,
    )
    staged, package = prepared_stage(tmp_path, store, service, authority, package)
    assert staged.lifecycle is ModuleLifecycle.STAGED

    settings_parameters = {
        "module_id": staged.module_id,
        "package_digest": package.package_digest,
        "lifecycle_revision": staged.revision,
        "expected_settings_revision": 0,
        "principal_id": "principal:sparks",
        "audience_id": "audience:owner-private",
        "changed_fields": ["display.mode"],
    }
    settings_approval = ExecutionApproval(
        approval_id=str(uuid4()), capability="module.settings.update",
        request_fingerprint=execution_fingerprint(
            "module.settings.update", settings_parameters,
        ),
        approved_by="Sparks", approved_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    import_receipt(store, authority, settings_approval)
    receipt = service.settings.update(
        module_id=staged.module_id,
        expected_package_digest=package.package_digest,
        expected_lifecycle_revision=staged.revision,
        expected_revision=0,
        client_id="client:local", principal_id="principal:sparks",
        audience_id="audience:owner-private",
        approval_ref=settings_approval.approval_id,
        idempotency_key="settings:local:1",
        changes={"display.mode": "compact"},
        now=NOW,
    )
    replay = service.settings.update(
        module_id=staged.module_id,
        expected_package_digest=package.package_digest,
        expected_lifecycle_revision=staged.revision,
        expected_revision=0,
        client_id="client:local", principal_id="principal:sparks",
        audience_id="audience:owner-private",
        approval_ref=settings_approval.approval_id,
        idempotency_key="settings:local:1",
        changes={"display.mode": "compact"},
        now=NOW,
    )
    assert receipt == replay
    assert receipt.module_id == staged.module_id
    assert receipt.effective_revision == 0

    # Local state must survive restart with the persisted revision retained.
    restarted = command_service(tmp_path, store, system=system)
    snapshot = restarted.settings.snapshot(module_id=staged.module_id)
    assert snapshot["revision"] == receipt.revision
    assert snapshot["values"] == {"display.mode": "compact"}

    # A second distinct settings request still requires a fresh exact receipt.
    with pytest.raises(PermissionError, match="not authorized"):
        service.settings.update(
            module_id=staged.module_id,
            expected_package_digest=package.package_digest,
            expected_lifecycle_revision=staged.revision,
            expected_revision=receipt.revision,
            client_id="client:local", principal_id="principal:sparks",
            audience_id="audience:owner-private",
            approval_ref=settings_approval.approval_id,
            idempotency_key="settings:local:2",
            changes={"display.mode": "full"},
            now=NOW,
        )


def test_module_settings_stay_denied_without_remote_authority(tmp_path):
    from sofia.sdk import (
        ModuleSettingApplyClass,
        ModuleSettingField,
        ModuleSettingType,
        ModuleSettingsContract,
    )

    store = local_store(tmp_path)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    service = ModuleLifecycleCommandService(
        state_path=store.path, store_root=tmp_path / "module-store",
        capability_system=system, storage=store,
    )
    contract = ModuleSettingsContract(
        "sofia.module.settings.v1", 1, (
            ModuleSettingField(
                "display.mode", "Display mode", ModuleSettingType.STRING,
                ModuleSettingApplyClass.COMPONENT_RESTART, required=True,
            ),
        ),
    )
    package = verified_custom(
        tmp_path, directory="local-settings-authority-package",
        module_id="org.sofia.localauthority", version="4.1.0",
        schema_version=3, settings_contract=contract,
    )
    found = service.discover(package, now=NOW)
    authority = LocalModuleAuthority(store)
    with pytest.raises(PermissionError, match="not authorized"):
        # No Core receipt exists: protected approval must fail closed.
        service.approve(
            found.module_id, expected_revision=found.revision,
            approval_id="approval:absent", now=NOW,
        )
    store.bind_core("core:artemis", now=NOW)
    approve_id, _ = authorize(
        store, authority, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED, now=NOW,
    )
    approved = service.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approve_id, now=NOW,
    )
    assert approved.lifecycle is ModuleLifecycle.APPROVED
    # Unbound hosts may never enter protected settings mutations either, so
    # the settings authority itself is only exercised through the bound host
    # composition in other tests on this file.
    assert service.settings.snapshot(module_id=found.module_id)["values"] == {}


def test_failed_activation_preserves_recoverable_local_state(tmp_path):
    store = local_store(tmp_path)
    store.bind_core("core:artemis", now=NOW)
    authority = LocalModuleAuthority(store)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    service = ModuleLifecycleCommandService(
        state_path=store.path, store_root=tmp_path / "module-store",
        capability_system=system, storage=store,
    )
    package = verified_package(tmp_path)
    staged, package = prepared_stage(tmp_path, store, service, authority, package)
    activation_id = activate_approvals(
        tmp_path, store, authority, service, staged, package,
    )
    activating = service.begin_activation(
        package, expected_revision=staged.revision,
        profile=OperationProfileKind.OBSERVE,
        compatibility=compatibility(package),
        registrations=((
            Capability("research.search", "reviewed search"),
            lambda request: {},
        ),),
        approval_id=activation_id, now=NOW,
    )
    assert system.capability_names() == ()
    # The activation process never completes: the host restarts in-place.
    restarted_store = PlatformLocalStore(
        store.path, roles=MODULE_HOST_ROLES, host_identity="host:venus",
    )
    restarted = ModuleLifecycleCommandService(
        state_path=store.path, store_root=tmp_path / "module-store",
        capability_system=CapabilitySystem(
            authorization_checker=lambda request: True,
        ),
        storage=restarted_store,
    )
    record = restarted.describe(staged.module_id)
    assert record.lifecycle is ModuleLifecycle.QUARANTINED
    assert record.revision == activating.revision + 1
    receipt = restarted.transition_receipt(staged.module_id, record.revision)
    assert receipt.actor == "platform:runtime"
    assert restarted.manager.capability_system.capability_names() == ()
    assert not (tmp_path / "sofia.db").exists()


def test_module_host_operation_flow_uses_local_run_state(tmp_path):
    store = PlatformLocalStore(
        tmp_path / "platform-local" / "module_host.db",
        roles=MODULE_HOST_ROLES, host_identity="host:test",
    )
    store.bind_core("core:artemis", now=NOW)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    service = ModuleLifecycleCommandService(
        state_path=store.path, store_root=tmp_path / "module-store",
        capability_system=system, storage=store,
    )
    package = verified_package(tmp_path)
    found = service.discover(package, now=datetime.now(timezone.utc))
    authority = LocalModuleAuthority(store)
    moment = datetime.now(timezone.utc).replace(microsecond=0)
    approve_id, _ = authorize(
        store, authority, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED, now=moment,
    )
    approved = service.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approve_id, now=moment,
    )
    stage_id, _ = authorize(
        store, authority, operation="stage", record=approved,
        target=ModuleLifecycle.STAGED, now=moment,
    )
    staged = service.stage(
        package, expected_revision=approved.revision,
        approval_id=stage_id, now=moment,
    )
    activation_id, _ = authorize(
        store, authority, operation="activate", record=staged,
        target=ModuleLifecycle.ACTIVATING,
        profile=OperationProfileKind.OBSERVE, now=moment,
    )
    work_store = DurableWorkStore(store.path, storage=store)
    manager = TaskExecutionManager(work_store, {}, max_workers=1)
    factories = AdapterFactoryRegistry()
    adapter = Adapter(package.package_digest)
    factories.register(Factory(package.package_digest, adapter))
    coordinator = ModuleOperationCoordinator(
        state_path=store.path, lifecycle=service,
        factories=factories, work_store=work_store, manager=manager,
        storage=store,
    )
    request = ModuleOperationRequest(
        request_id=f"request:{uuid4()}", idempotency_key="activation:local:v1",
        module_id=staged.module_id, package_digest=staged.package_digest,
        operation=ModuleOperationType.ACTIVATE,
        expected_revision=staged.revision,
        source_lifecycle=ModuleLifecycle.STAGED,
        destination_lifecycle=ModuleLifecycle.ACTIVE,
        profile=OperationProfileKind.OBSERVE,
        principal=local_sparks_principal(),
        principal_attestation_ref=activation_id, approval_id=activation_id,
        component_id="research.worker", host_identity="host:test",
        deadline=moment + timedelta(minutes=5), correlation_id="corr:local",
        resource_lease_refs=(), device_lease_refs=(),
        requested_effect="start reviewed research worker locally",
        cancellation_policy=ModuleCancellationPolicy.BEFORE_EXTERNAL_DISPATCH_ONLY,
    )
    try:
        job = coordinator.submit(request, now=moment)
        duplicate = coordinator.submit(request, now=moment)
        assert duplicate.job_id == job.job_id
        settled = finish(manager, work_store, job.job_id)
        assert settled.status is WorkStatus.COMPLETED
        assert adapter.starts == 1
        assert service.describe(staged.module_id).lifecycle is ModuleLifecycle.ACTIVE
        assert [event.status.value for event in coordinator.attempts(
            request.request_id,
        )] == [
            "admitted", "running", "external_effect_attempted",
            "externally_verified_success",
        ]
        assert store.path == work_store.path
    finally:
        manager.close(wait=True)
        coordinator.close()
    with pytest.raises(RuntimeError, match="only an uncertain module operation"):
        coordinator.reconcile(request.request_id, now=datetime.now(timezone.utc))
    # Local RUN rows are durable in the Platform-local file.
    with closing(store.connect(read_only=True)) as db:
        count = db.execute(
            "SELECT COUNT(*) FROM autonomous_work_job WHERE job_id=?",
            (job.job_id,),
        ).fetchone()[0]
    assert count == 1
    assert not (tmp_path / "sofia.db").exists()


def test_local_module_state_is_isolated_from_canonical_writer(tmp_path):
    store = local_store(tmp_path)
    service = command_service(tmp_path, store)
    package = verified_package(tmp_path)
    service.discover(package, now=NOW)
    # Canonical state was never created by the module host.
    assert not (tmp_path / "sofia.db").exists()
    with closing(store.connect(read_only=True)) as db:
        rows = db.execute(
            "SELECT module_id FROM platform_module_lifecycle"
        ).fetchall()
    assert [str(row[0]) for row in rows] == [package.manifest.module_id]
