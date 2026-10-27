from contextlib import closing
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.platform.capability import CapabilitySystem
from sofia.platform.application.module_lifecycle import ModuleLifecycleCommandService
from sofia.platform.config.settings_authority import SettingsApplyState
from sofia.platform.modules import ModuleLifecycleManager, ModuleSettingsService
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.sdk import (
    ModuleSettingApplyClass, ModuleSettingField, ModuleSettingType,
    ModuleSettingsContract,
)
from test.test_module_lifecycle_v1 import verified_custom
from test.owner_auth_fixture import record_verified_owner_approval


NOW = datetime(2026, 10, 27, 20, tzinfo=timezone.utc)


def configured(canonical_state_path, tmp_path, *, apply_class=None, authorizer=None):
    contract = ModuleSettingsContract(
        "sofia.module.settings.v1", 1, (
            ModuleSettingField(
                "display.mode", "Display mode", ModuleSettingType.ENUM,
                apply_class or ModuleSettingApplyClass.LIVE,
                required=True, enum_values=("compact", "full"),
            ),
            ModuleSettingField(
                "credential.ref", "Credential reference",
                ModuleSettingType.STRING,
                ModuleSettingApplyClass.COMPONENT_RESTART,
                secret_reference=True,
            ),
        ),
    )
    package = verified_custom(
        tmp_path, directory="module-settings-package",
        module_id="org.sofia.settings.test", schema_version=3,
        settings_contract=contract,
    )
    manager = ModuleLifecycleManager(
        state_path=canonical_state_path, store_root=tmp_path / "store",
        capability_system=CapabilitySystem(lambda request: False),
        authorizer=lambda request: False,
    )
    record = manager.discover(package, now=NOW)
    calls = []
    service = ModuleSettingsService(
        canonical_state_path,
        authorizer=authorizer or (lambda request, transaction: calls.append(request) or True),
    )
    return service, package, record, calls


def make_active(canonical_state_path, module_id):
    with closing(CanonicalSQLiteGuard(canonical_state_path).connect()) as db, db:
        db.execute(
            "UPDATE platform_module_lifecycle SET lifecycle='active' WHERE module_id=?",
            (module_id,),
        )


def update(service, package, record, *, key="settings:1", expected=0, changes=None):
    return service.update(
        module_id=record.module_id,
        expected_package_digest=package.package_digest,
        expected_lifecycle_revision=record.revision,
        expected_revision=expected,
        client_id="client:windows-owner", principal_id="principal:sparks",
        audience_id="audience:owner-private", approval_ref="approval:settings",
        idempotency_key=key,
        changes=changes or {"display.mode": "compact"}, now=NOW,
    )


def test_live_module_settings_are_exact_package_cas_applied_and_restart_durable(
    canonical_state_path, tmp_path,
):
    service, package, record, authorizations = configured(
        canonical_state_path, tmp_path,
    )
    make_active(canonical_state_path, record.module_id)
    applied = []
    service.register_apply_handler(
        module_id=record.module_id, package_digest=package.package_digest,
        handler=lambda *arguments: applied.append(arguments),
    )

    first = update(service, package, record)
    replay = update(service, package, record)

    assert first == replay
    assert first.apply_state is SettingsApplyState.APPLIED
    assert first.revision == first.effective_revision == 1
    assert len(authorizations) == 1
    assert len(applied) == 1
    restarted = ModuleSettingsService(
        canonical_state_path, authorizer=lambda request, transaction: True,
    )
    snapshot = restarted.snapshot(module_id=record.module_id)
    assert snapshot["revision"] == snapshot["effective_revision"] == 1
    assert snapshot["values"] == {"display.mode": "compact"}


def test_module_settings_redact_secret_reference_and_never_claim_restart_apply(
    canonical_state_path, tmp_path,
):
    service, package, record, _ = configured(canonical_state_path, tmp_path)

    receipt = update(
        service, package, record,
        changes={
            "display.mode": "full", "credential.ref": "secret:module.token",
        },
    )

    assert receipt.apply_state is SettingsApplyState.PENDING_COMPONENT_RESTART
    assert receipt.effective_revision == 0
    snapshot = service.snapshot(module_id=record.module_id)
    assert snapshot["values"]["credential.ref"] == "<protected-secret-reference>"
    assert "secret:module.token" not in repr(snapshot)


def test_module_settings_validate_before_authority_and_fence_all_revisions(
    canonical_state_path, tmp_path,
):
    service, package, record, authorizations = configured(
        canonical_state_path, tmp_path,
    )
    with pytest.raises(ValueError, match="allowed value"):
        update(service, package, record, changes={"display.mode": "invented"})
    with pytest.raises(RuntimeError, match="package revision conflict"):
        service.update(
            module_id=record.module_id, expected_package_digest="0" * 64,
            expected_lifecycle_revision=record.revision, expected_revision=0,
            client_id="client:test", principal_id="principal:sparks",
            audience_id="audience:owner-private", approval_ref="approval:test",
            idempotency_key="wrong-package", changes={"display.mode": "compact"},
            now=NOW,
        )
    with pytest.raises(RuntimeError, match="lifecycle revision conflict"):
        service.update(
            module_id=record.module_id,
            expected_package_digest=package.package_digest,
            expected_lifecycle_revision=record.revision + 1,
            expected_revision=0, client_id="client:test",
            principal_id="principal:sparks", audience_id="audience:owner-private",
            approval_ref="approval:test", idempotency_key="wrong-lifecycle",
            changes={"display.mode": "compact"}, now=NOW,
        )
    assert authorizations == []


def test_changed_idempotency_payload_is_rejected_without_second_authorization(
    canonical_state_path, tmp_path,
):
    service, package, record, authorizations = configured(
        canonical_state_path, tmp_path,
        apply_class=ModuleSettingApplyClass.NEXT_OPERATION,
    )
    update(service, package, record)
    with pytest.raises(RuntimeError, match="idempotency payload conflict"):
        update(
            service, package, record, changes={"display.mode": "full"},
        )
    assert len(authorizations) == 1


def test_live_module_setting_without_reviewed_handler_is_truthfully_unknown(
    canonical_state_path, tmp_path,
):
    service, package, record, _ = configured(canonical_state_path, tmp_path)
    make_active(canonical_state_path, record.module_id)

    receipt = update(service, package, record)

    assert receipt.apply_state is SettingsApplyState.UNKNOWN
    assert receipt.effective_revision == 0
    assert receipt.error == "no reviewed apply handler is registered"


def test_lifecycle_change_during_live_apply_never_claims_applied(
    canonical_state_path, tmp_path,
):
    service, package, record, _ = configured(canonical_state_path, tmp_path)
    make_active(canonical_state_path, record.module_id)

    def pause_during_apply(*_):
        with closing(CanonicalSQLiteGuard(canonical_state_path).connect()) as db, db:
            db.execute(
                "UPDATE platform_module_lifecycle SET lifecycle='paused' "
                "WHERE module_id=?", (record.module_id,),
            )

    service.register_apply_handler(
        module_id=record.module_id, package_digest=package.package_digest,
        handler=pause_during_apply,
    )

    receipt = update(service, package, record)

    assert receipt.apply_state is SettingsApplyState.UNKNOWN
    assert receipt.effective_revision == 0
    assert "outcome is uncertain" in receipt.error


def test_module_package_change_requires_reviewed_settings_migration(
    canonical_state_path, tmp_path,
):
    service, package, record, _ = configured(
        canonical_state_path, tmp_path,
        apply_class=ModuleSettingApplyClass.NEXT_OPERATION,
    )
    update(service, package, record)
    with closing(CanonicalSQLiteGuard(canonical_state_path).connect()) as db, db:
        db.execute(
            "UPDATE platform_module_lifecycle SET package_digest=? WHERE module_id=?",
            ("f" * 64, record.module_id),
        )

    with pytest.raises(RuntimeError, match="manifest identity mismatch"):
        service.snapshot(module_id=record.module_id)


def test_production_boundary_atomically_consumes_exact_owner_approval_and_stop_blocks(
    canonical_state_path, tmp_path,
):
    contract = ModuleSettingsContract(
        "sofia.module.settings.v1", 1, (
            ModuleSettingField(
                "display.mode", "Display mode", ModuleSettingType.ENUM,
                ModuleSettingApplyClass.NEXT_OPERATION,
                enum_values=("compact", "full"),
            ),
        ),
    )
    package = verified_custom(
        tmp_path, directory="production-settings-package",
        module_id="org.sofia.settings.production", schema_version=3,
        settings_contract=contract,
    )
    command = ModuleLifecycleCommandService(
        state_path=canonical_state_path, store_root=tmp_path / "command-store",
        capability_system=CapabilitySystem(lambda request: True),
    )
    record = command.discover(package, now=NOW)
    parameters = {
        "module_id": record.module_id,
        "package_digest": package.package_digest,
        "lifecycle_revision": record.revision,
        "expected_settings_revision": 0,
        "principal_id": "principal:sparks",
        "audience_id": "audience:owner-private",
        "changed_fields": ["display.mode"],
    }

    def approval(label):
        value = ExecutionApproval(
            approval_id=f"{label}:{uuid4()}",
            capability="module.settings.update",
            request_fingerprint=execution_fingerprint(
                "module.settings.update", parameters,
            ),
            approved_by="Sparks", approved_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
        )
        verifier = ExecutionApprovalVerifier(canonical_state_path)
        record_verified_owner_approval(verifier, value)
        return verifier, value

    request = dict(
        module_id=record.module_id,
        expected_package_digest=package.package_digest,
        expected_lifecycle_revision=record.revision, expected_revision=0,
        client_id="client:owner", principal_id="principal:sparks",
        audience_id="audience:owner-private",
        approval_ref="pending",
        idempotency_key="module-settings:production",
        changes={"display.mode": "compact"}, now=NOW + timedelta(seconds=2),
    )
    verifier, accepted = approval("settings-accepted")
    request["approval_ref"] = accepted.approval_id
    request["audience_id"] = "audience:public"
    with pytest.raises(PermissionError, match="not authorized"):
        command.settings.update(**request)
    assert verifier.matches_unconsumed(
        approval_id=accepted.approval_id,
        capability="module.settings.update", parameters=parameters,
        now=NOW + timedelta(seconds=2),
    )
    request["audience_id"] = "audience:owner-private"
    receipt = command.settings.update(**request)
    replay = command.settings.update(**request)

    assert receipt == replay
    assert receipt.apply_state is SettingsApplyState.PENDING_NEXT_OPERATION
    request["audience_id"] = "audience:public"
    with pytest.raises(RuntimeError, match="idempotency payload conflict"):
        command.settings.update(**request)
    request["audience_id"] = "audience:owner-private"
    assert not verifier.matches_unconsumed(
        approval_id=accepted.approval_id,
        capability="module.settings.update", parameters=parameters,
        now=NOW + timedelta(seconds=2),
    )

    stopped_parameters = {
        **parameters, "expected_settings_revision": 1,
    }
    stopped = ExecutionApproval(
        approval_id=f"settings-stop:{uuid4()}",
        capability="module.settings.update",
        request_fingerprint=execution_fingerprint(
            "module.settings.update", stopped_parameters,
        ),
        approved_by="Sparks", approved_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    record_verified_owner_approval(verifier, stopped)
    OperatorStopStore(canonical_state_path).set(
        active=True, updated_by="Sparks", reason="hold configuration effects",
        at=NOW + timedelta(seconds=1),
    )
    request.update({
        "approval_ref": stopped.approval_id,
        "expected_revision": 1,
        "idempotency_key": "module-settings:stopped",
        "changes": {"display.mode": "full"},
    })
    with pytest.raises(PermissionError, match="not authorized"):
        command.settings.update(**request)
    assert verifier.matches_unconsumed(
        approval_id=stopped.approval_id,
        capability="module.settings.update", parameters=stopped_parameters,
        now=NOW + timedelta(seconds=2),
    )
