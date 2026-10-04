"""Host capability authorization wired to the unified permission policy."""
from __future__ import annotations

from pathlib import Path

from sofia.config.model import SofiaConfiguration
from sofia.safe.operator_stop import OperatorStopStore
from sofia.safe.permissions import (
    PermissionLevel,
    PermissionStore,
    capability_permission_policy,
)


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

        parameters = dict(request.parameters)
        approval_id = parameters.get("approval_id")
        standing_parameters = {
            key: value
            for key, value in parameters.items()
            if key != "approval_id"
        }

        if policy.level is PermissionLevel.REVERSIBLE_SCOPED:
            if permission_store.allows_standing(
                name,
                standing_parameters,
            ):
                return True
            if isinstance(approval_id, str) and approval_id.strip():
                return True

        if policy.level is PermissionLevel.PROTECTED:
            if isinstance(approval_id, str) and approval_id.strip():
                return True

        # Preserve explicitly configured legacy exposure while subsystem-specific
        # approval verifiers are migrated to the unified store. This does not
        # bypass integration/DEV exact-approval checks.
        if name in configuration.standing_allowed_capabilities:
            return True

        # Level 5 has no cognitive self-authorization path.
        return False

    return capability_authorized
