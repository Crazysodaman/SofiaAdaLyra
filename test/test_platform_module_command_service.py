from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.platform.application.module_lifecycle import ModuleLifecycleCommandService
from sofia.platform.capability import Capability, CapabilitySystem
from sofia.platform.modules import ModuleLifecycle, OperationProfileKind
from sofia.platform.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_module_lifecycle_v1 import compatibility, verified_package


NOW = datetime(2026, 10, 24, 15, tzinfo=timezone.utc)


def service(canonical_state_path, tmp_path):
    return ModuleLifecycleCommandService(
        state_path=canonical_state_path,
        store_root=tmp_path / "module-store",
        capability_system=CapabilitySystem(authorization_checker=lambda request: True),
    )


def authorize(
    state_path, *, operation, record, target, profile=None, now=NOW,
    overrides=None,
):
    parameters = {
        "module_id": record.module_id,
        "version": record.version,
        "package_digest": record.package_digest,
        "expected_revision": record.revision,
        "target_lifecycle": target.value,
        "profile": None if profile is None else profile.value,
    }
    parameters.update(overrides or {})
    approval = ExecutionApproval(
        approval_id=str(uuid4()),
        capability=f"module.{operation}",
        request_fingerprint=execution_fingerprint(
            f"module.{operation}", parameters,
        ),
        approved_by="Sparks",
        approved_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    verifier = ExecutionApprovalVerifier(state_path)
    record_verified_owner_approval(verifier, approval)
    return approval.approval_id, parameters


def test_exact_owner_approval_is_consumed_once_for_lifecycle_transition(
    canonical_state_path, tmp_path,
):
    command = service(canonical_state_path, tmp_path)
    package = verified_package(tmp_path)
    found = command.discover(package, now=NOW)
    assert found.lifecycle is ModuleLifecycle.VALIDATED
    assert command.manager.capability_system.capability_names() == ()

    approval_id, parameters = authorize(
        canonical_state_path, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED,
    )
    approved = command.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approval_id, now=NOW,
    )
    assert approved.lifecycle is ModuleLifecycle.APPROVED
    assert not ExecutionApprovalVerifier(canonical_state_path).matches_unconsumed(
        approval_id=approval_id, capability="module.approve",
        parameters=parameters, now=NOW,
    )
    with pytest.raises(PermissionError, match="not authorized"):
        command.approve(
            found.module_id, expected_revision=approved.revision,
            approval_id=approval_id, now=NOW,
        )


def test_wrong_revision_approval_cannot_mutate_or_register_capabilities(
    canonical_state_path, tmp_path,
):
    command = service(canonical_state_path, tmp_path)
    package = verified_package(tmp_path)
    found = command.discover(package, now=NOW)
    approval_id, _ = authorize(
        canonical_state_path, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED,
        overrides={"expected_revision": found.revision + 1},
    )
    with pytest.raises(PermissionError, match="not authorized"):
        command.approve(
            found.module_id, expected_revision=found.revision,
            approval_id=approval_id, now=NOW,
        )
    assert command.describe(found.module_id).lifecycle is ModuleLifecycle.VALIDATED
    assert command.manager.capability_system.capability_names() == ()


def test_operator_stop_blocks_activation_without_consuming_exact_approval(
    canonical_state_path, tmp_path,
):
    command = service(canonical_state_path, tmp_path)
    package = verified_package(tmp_path)
    found = command.discover(package, now=NOW)
    approve_id, _ = authorize(
        canonical_state_path, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED,
    )
    approved = command.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approve_id, now=NOW,
    )
    stage_id, _ = authorize(
        canonical_state_path, operation="stage", record=approved,
        target=ModuleLifecycle.STAGED,
    )
    staged = command.stage(
        package, expected_revision=approved.revision,
        approval_id=stage_id, now=NOW,
    )
    activation_id, parameters = authorize(
        canonical_state_path, operation="activate", record=staged,
        target=ModuleLifecycle.ACTIVE, profile=OperationProfileKind.OBSERVE,
    )
    OperatorStopStore(canonical_state_path).set(
        active=True, updated_by="Sparks", reason="hold module activation",
        at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(PermissionError, match="not authorized"):
        command.activate(
            package, expected_revision=staged.revision,
            profile=OperationProfileKind.OBSERVE,
            compatibility=compatibility(package),
            registrations=((Capability("research.search", "search"), lambda request: {}),),
            approval_id=activation_id, now=NOW + timedelta(seconds=2),
        )
    assert command.describe(staged.module_id).lifecycle is ModuleLifecycle.STAGED
    assert command.manager.capability_system.capability_names() == ()
    assert ExecutionApprovalVerifier(canonical_state_path).matches_unconsumed(
        approval_id=activation_id, capability="module.activate",
        parameters=parameters, now=NOW + timedelta(seconds=2),
    )
