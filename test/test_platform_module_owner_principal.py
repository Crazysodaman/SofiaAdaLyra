"""Verified canonical owner receipts remain usable at module boundaries."""
from datetime import timedelta
from uuid import uuid4

from sofia.platform.modules import ModuleLifecycle
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_platform_module_command_service import NOW, service
from test.test_module_lifecycle_v1 import verified_package


def test_canonical_owner_proof_authorizes_module_transition(canonical_state_path, tmp_path):
    command = service(canonical_state_path, tmp_path)
    package = verified_package(tmp_path)
    found = command.discover(package, now=NOW)
    parameters = {
        "module_id": found.module_id, "version": found.version,
        "package_digest": found.package_digest, "expected_revision": found.revision,
        "target_lifecycle": ModuleLifecycle.APPROVED.value, "profile": None,
    }
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability="module.approve",
        request_fingerprint=execution_fingerprint("module.approve", parameters),
        approved_by="person:sparks", approved_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    verifier = ExecutionApprovalVerifier(canonical_state_path)
    record_verified_owner_approval(verifier, approval)
    updated = command.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approval.approval_id, now=NOW,
    )
    assert updated.lifecycle is ModuleLifecycle.APPROVED
    assert not verifier.matches_unconsumed(
        approval_id=approval.approval_id, capability="module.approve",
        parameters=parameters, now=NOW,
    )


def test_owner_principal_label_without_recorded_proof_cannot_approve(canonical_state_path, tmp_path):
    import pytest

    command = service(canonical_state_path, tmp_path)
    found = command.discover(verified_package(tmp_path), now=NOW)
    with pytest.raises(PermissionError, match="not authorized"):
        command.approve(
            found.module_id, expected_revision=found.revision,
            approval_id="person:sparks", now=NOW,
        )
    assert command.describe(found.module_id) == found


def test_imported_canonical_owner_receipt_uses_stable_audit_actor(tmp_path):
    from contextlib import closing
    from sofia.platform.modules.host_authority import LocalModuleAuthority
    from test.test_platform_module_host_local_state import local_store, import_receipt, NOW as HOST_NOW

    store = local_store(tmp_path)
    store.bind_core("core:test", now=HOST_NOW)
    authority = LocalModuleAuthority(store)
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability="module.approve",
        request_fingerprint=execution_fingerprint("module.approve", {}),
        approved_by="person:sparks", approved_at=HOST_NOW,
        expires_at=HOST_NOW + timedelta(minutes=5),
    )
    import_receipt(store, authority, approval)
    consumed = authority.consume(
        approval_id=approval.approval_id, capability="module.approve",
        parameters={}, now=HOST_NOW,
    )
    assert consumed.principal_id == "person:sparks"
    with closing(store.connect()) as db:
        assert db.execute(
            "SELECT actor_id FROM safe_audit_event WHERE event_type=?",
            ("modulehost.approval.consumed",),
        ).fetchone()[0] == "person:sparks"


def test_canonical_owner_settings_request_consumes_exact_verified_proof(canonical_state_path, tmp_path):
    from sofia.sdk import (
        ModuleSettingApplyClass, ModuleSettingField, ModuleSettingType, ModuleSettingsContract,
    )
    from test.test_module_lifecycle_v1 import verified_custom

    contract = ModuleSettingsContract("sofia.module.settings.v1", 1, (
        ModuleSettingField(
            "display.mode", "Display mode", ModuleSettingType.ENUM,
            ModuleSettingApplyClass.NEXT_OPERATION, enum_values=("compact", "full"),
        ),
    ))
    package = verified_custom(
        tmp_path, directory="canonical-settings", module_id="org.sofia.settings.owner",
        schema_version=3, settings_contract=contract,
    )
    command = service(canonical_state_path, tmp_path)
    found = command.discover(package, now=NOW)
    parameters = {
        "module_id": found.module_id, "package_digest": found.package_digest,
        "lifecycle_revision": found.revision, "expected_settings_revision": 0,
        "principal_id": "person:sparks", "audience_id": "audience:owner-private",
        "changed_fields": ["display.mode"],
    }
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability="module.settings.update",
        request_fingerprint=execution_fingerprint("module.settings.update", parameters),
        approved_by="person:sparks", approved_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    verifier = ExecutionApprovalVerifier(canonical_state_path)
    record_verified_owner_approval(verifier, approval)
    receipt = command.settings.update(
        module_id=found.module_id, expected_package_digest=found.package_digest,
        expected_lifecycle_revision=found.revision, expected_revision=0,
        client_id="client:owner", principal_id="person:sparks",
        audience_id="audience:owner-private", approval_ref=approval.approval_id,
        idempotency_key="settings:canonical-owner", changes={"display.mode": "compact"}, now=NOW,
    )
    assert receipt.revision == 1
    assert not verifier.matches_unconsumed(
        approval_id=approval.approval_id, capability="module.settings.update",
        parameters=parameters, now=NOW,
    )
