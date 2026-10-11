"""Host capability authorization wired to the unified permission policy."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sofia.safe.execution_approval import ExecutionApprovalVerifier

from sofia.config.model import SofiaConfiguration
from sofia.safe.operator_stop import OperatorStopStore
from sofia.safe.permissions import (
    PermissionLevel,
    PermissionStore,
    capability_permission_policy,
)


# Only these production handlers consume the generic execution-approval receipt.
# DEV, EVOLVE and Fleet have independent downstream verifier contracts.
_EXACT_EXECUTION_APPROVAL_CAPABILITIES = frozenset({
    "notification.send",
    "portainer.container.restart",
    "jmri.power.set",
    "github.issue.create",
    "github.pull_request.create",
    "github.pull_request.merge",
    "discord.pause",
    "discord.resume",
    "discord.revoke",
    "local.service.start",
    "local.service.stop",
    "local.service.restart",
    "local.host.reboot",
    "local.package.update",
    "hyperv.vm.start",
    "hyperv.vm.stop",
    "storage.write_text",
    "storage.mkdir",
    "storage.copy",
    "storage.move",
    "storage.delete",
    "knowledge.document.write",
    "home_assistant.service.call",
})


_FILESYSTEM_READ_OPERATIONS = frozenset({
    "list_directory",
    "inspect_path",
    "read_file",
    "search_files",
})


def _inside_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def create_capability_authorizer(
    *,
    runtime_provider,
    configuration: SofiaConfiguration,
    operator_stop: OperatorStopStore,
):
    """Resolve runtime authority at execution time and fail closed."""
    filesystem_root = Path(configuration.filesystem_root)
    permission_store = PermissionStore(configuration.state_path)
    execution_approvals = ExecutionApprovalVerifier(configuration.state_path)

    def capability_authorized(request) -> bool:
        if runtime_provider() is None:
            return False

        name = request.capability.name
        policy = capability_permission_policy(name)

        # Emergency stop blocks every side effect while leaving observation alive.
        if (
            operator_stop.current().active
            and policy.level is not PermissionLevel.OBSERVE_READ
        ):
            return False

        # Read-only code/filesystem exploration is automatic, but confined to
        # Sofía's configured project root. Conversation text can never widen it.
        if name == "codebase.inspect":
            requested_scope = request.requested_scope
            if requested_scope is None:
                return True
            if not isinstance(requested_scope, Path):
                return False
            try:
                return requested_scope.resolve() == filesystem_root.resolve()
            except (OSError, RuntimeError):
                return False

        if name == "filesystem.inspect":
            requested_scope = request.requested_scope
            if requested_scope is not None:
                if not isinstance(requested_scope, Path):
                    return False
                if not _inside_root(requested_scope, filesystem_root):
                    return False
            operation = request.parameters.get("operation")
            return operation in _FILESYSTEM_READ_OPERATIONS

        if policy.level in (
            PermissionLevel.OBSERVE_READ,
            PermissionLevel.SAFE_AUTONOMOUS,
        ):
            return True

        # Level 5 is a hard host boundary. Environment configuration, legacy
        # standing capability lists, model output, and standing grants can
        # never turn authority-changing operations into self-authorized tools.
        if policy.level is PermissionLevel.NEVER_SELF_AUTHORIZED:
            return False

        parameters = dict(request.parameters)
        approval_id = parameters.get("approval_id")
        standing_parameters = {
            key: value
            for key, value in parameters.items()
            if key != "approval_id"
        }

        if policy.level is PermissionLevel.REVERSIBLE_SCOPED:
            if permission_store.allows_standing(name, standing_parameters):
                return True

        if policy.level in (
            PermissionLevel.REVERSIBLE_SCOPED,
            PermissionLevel.PROTECTED,
        ):
            if name in _EXACT_EXECUTION_APPROVAL_CAPABILITIES:
                # A generic handler requires its precise durable receipt.
                # Its effect boundary still performs the atomic consume.
                return execution_approvals.matches_unconsumed(
                    approval_id=approval_id,
                    capability=name,
                    parameters=parameters,
                    now=datetime.now(timezone.utc),
                )
            # DEV, EVOLVE, OPS and Fleet verify different signed/leased
            # approvals within their own effect handlers. Do not mistake
            # these IDs for generic execution approvals.
            return isinstance(approval_id, str) and bool(approval_id.strip())

        # Legacy standing capability configuration is intentionally ignored.
        # The canonical permission store and exact approval verifiers are the
        # only mutation authorities.
        return False

    return capability_authorized
