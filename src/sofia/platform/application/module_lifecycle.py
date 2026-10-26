"""Application-owned command boundary for signed Platform modules.

The package verifier proves bytes and publisher identity.  It does not grant
authority.  Every state-changing command below consumes one exact canonical
SAFE approval immediately before the lifecycle manager touches package state
or capability registration.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sofia.platform.capability.model import Capability
from sofia.platform.capability.system import CapabilityHandler, CapabilitySystem
from sofia.platform.modules.compatibility import ModuleCompatibilityReport
from sofia.platform.modules.lifecycle import (
    ModuleChangePlan,
    ModuleInstallPlan,
    ModuleLifecycleAuthorization,
    ModuleLifecycleHealth,
    ModuleLifecycleManager,
    ModuleLifecycleRecord,
    ModuleTransitionReceipt,
)
from sofia.platform.modules.package import OperationProfileKind, VerifiedModulePackage
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.operator_stop import OperatorStopStore


_SAFETY_REDUCING_OPERATIONS = frozenset({"pause", "disable", "quarantine"})


class ModuleLifecycleCommandService:
    """Bind PLAT-05 lifecycle commands to canonical SAFE and CapabilitySystem."""

    def __init__(
        self, *, state_path: Path, store_root: Path,
        capability_system: CapabilitySystem,
    ) -> None:
        if not isinstance(state_path, Path) or not isinstance(store_root, Path):
            raise TypeError("state_path and store_root must be Path")
        if not isinstance(capability_system, CapabilitySystem):
            raise TypeError("capability_system must be CapabilitySystem")
        self._approvals = ExecutionApprovalVerifier(state_path)
        self._operator_stop = OperatorStopStore(state_path)
        self._manager = ModuleLifecycleManager(
            state_path=state_path,
            store_root=store_root,
            capability_system=capability_system,
            authorizer=self._consume_exact_authority,
        )

    @property
    def manager(self) -> ModuleLifecycleManager:
        """Expose the canonical manager for read-only projections and diagnostics."""
        return self._manager

    def _consume_exact_authority(
        self, request: ModuleLifecycleAuthorization,
    ) -> bool:
        if not isinstance(request, ModuleLifecycleAuthorization):
            return False
        if request.actor != "Sparks":
            return False
        if (
            self._operator_stop.current().active
            and request.operation not in _SAFETY_REDUCING_OPERATIONS
        ):
            return False
        try:
            approval = self._approvals.consume(
                approval_id=request.operation_ref,
                capability=request.capability,
                parameters=request.parameters,
                now=request.occurred_at,
            )
        except (LookupError, PermissionError, TypeError, ValueError):
            return False
        return approval.approved_by == "Sparks"

    def discover(
        self, package: VerifiedModulePackage, *, now: datetime,
    ) -> ModuleLifecycleRecord:
        """Record a verified package without approving, staging, or executing it."""
        return self._manager.discover(package, now=now)

    def describe(self, module_id: str) -> ModuleLifecycleRecord | None:
        return self._manager.describe(module_id)

    def health(self, module_id: str) -> ModuleLifecycleHealth:
        return self._manager.health(module_id)

    def transition_receipt(
        self, module_id: str, revision: int,
    ) -> ModuleTransitionReceipt:
        return self._manager.transition_receipt(module_id, revision)

    def history(
        self, module_id: str, *, limit: int = 100,
    ) -> tuple[ModuleTransitionReceipt, ...]:
        return self._manager.history(module_id, limit=limit)

    def plan_install(
        self, package: VerifiedModulePackage, *, profile: OperationProfileKind,
    ) -> ModuleInstallPlan:
        return self._manager.plan_install(package, profile=profile)

    def plan_update(
        self, module_id: str, package: VerifiedModulePackage,
    ) -> ModuleChangePlan:
        return self._manager.plan_update(module_id, package)

    def plan_remove(self, module_id: str) -> ModuleChangePlan:
        return self._manager.plan_remove(module_id)

    def approve(
        self, module_id: str, *, expected_revision: int,
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.approve(
            module_id, expected_revision=expected_revision,
            operation_ref=approval_id, actor="Sparks", now=now,
        )

    def stage(
        self, package: VerifiedModulePackage, *, expected_revision: int,
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.stage(
            package, expected_revision=expected_revision,
            operation_ref=approval_id, actor="Sparks", now=now,
        )

    def activate(
        self, package: VerifiedModulePackage, *, expected_revision: int,
        profile: OperationProfileKind,
        compatibility: ModuleCompatibilityReport,
        registrations: tuple[tuple[Capability, CapabilityHandler], ...],
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.activate(
            package, expected_revision=expected_revision, profile=profile,
            compatibility=compatibility, registrations=registrations,
            operation_ref=approval_id, actor="Sparks", now=now,
        )

    def begin_activation(
        self, package: VerifiedModulePackage, *, expected_revision: int,
        profile: OperationProfileKind,
        compatibility: ModuleCompatibilityReport,
        registrations: tuple[tuple[Capability, CapabilityHandler], ...],
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.begin_activation(
            package, expected_revision=expected_revision, profile=profile,
            compatibility=compatibility, registrations=registrations,
            operation_ref=approval_id, actor="Sparks", now=now,
        )

    def complete_activation(
        self, package: VerifiedModulePackage, *, expected_revision: int,
        profile: OperationProfileKind,
        compatibility: ModuleCompatibilityReport,
        registrations: tuple[tuple[Capability, CapabilityHandler], ...],
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.complete_activation(
            package, expected_revision=expected_revision, profile=profile,
            compatibility=compatibility, registrations=registrations,
            operation_ref=approval_id, actor="Sparks", now=now,
        )

    def resume(
        self, package: VerifiedModulePackage, *, expected_revision: int,
        profile: OperationProfileKind,
        compatibility: ModuleCompatibilityReport,
        registrations: tuple[tuple[Capability, CapabilityHandler], ...],
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.resume(
            package, expected_revision=expected_revision, profile=profile,
            compatibility=compatibility, registrations=registrations,
            operation_ref=approval_id, actor="Sparks", now=now,
        )

    def pause(
        self, module_id: str, *, expected_revision: int,
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.pause(
            module_id, expected_revision=expected_revision,
            operation_ref=approval_id, actor="Sparks", now=now,
        )

    def begin_process_pause(
        self, module_id: str, *, expected_revision: int,
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.begin_process_pause(
            module_id, expected_revision=expected_revision,
            operation_ref=approval_id, actor="Sparks", now=now,
        )

    def complete_process_pause(
        self, module_id: str, *, expected_revision: int,
        operation_ref: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.complete_process_pause(
            module_id, expected_revision=expected_revision,
            operation_ref=operation_ref, now=now,
        )

    def disable(
        self, module_id: str, *, expected_revision: int,
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.disable(
            module_id, expected_revision=expected_revision,
            operation_ref=approval_id, actor="Sparks", now=now,
        )

    def quarantine(
        self, module_id: str, *, expected_revision: int,
        approval_id: str, reason: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.quarantine(
            module_id, expected_revision=expected_revision,
            operation_ref=approval_id, actor="Sparks", reason=reason, now=now,
        )

    def update(
        self, package: VerifiedModulePackage, *, expected_revision: int,
        profile: OperationProfileKind,
        compatibility: ModuleCompatibilityReport,
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.update(
            package, expected_revision=expected_revision, profile=profile,
            compatibility=compatibility, operation_ref=approval_id,
            actor="Sparks", now=now,
        )

    def rollback(
        self, package: VerifiedModulePackage, *, expected_revision: int,
        profile: OperationProfileKind,
        compatibility: ModuleCompatibilityReport,
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.rollback(
            package, expected_revision=expected_revision, profile=profile,
            compatibility=compatibility, operation_ref=approval_id,
            actor="Sparks", now=now,
        )

    def remove(
        self, module_id: str, *, expected_revision: int,
        approval_id: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        return self._manager.remove(
            module_id, expected_revision=expected_revision,
            operation_ref=approval_id, actor="Sparks", now=now,
        )
