"""Host capability authorization wiring and operator-stop policy."""
from pathlib import Path
from sofia.authorization.model import (
    AuthorizationDecision,
    AuthorizationDomain,
    FilesystemAuthorizationOperation,
)
from sofia.config.model import SofiaConfiguration
from sofia.safe.operator_stop import OperatorStopStore


_STOP_SAFE_CAPABILITIES = frozenset({
    'tool.catalog',
    'codebase.inspect',
    'filesystem.changes',
    'filesystem.inspect',
    'process.inspect',
    'system.inspect',
    'network.inspect',
    'service.inspect',
    'hardware.inspect',
    'storage.roots',
    'storage.usage',
    'storage.list',
    'storage.read_text',
    'knowledge.search',
    'knowledge.document',
    'dev.status',
    'machine.list',
    'machine.get',
    'machine.discover.local',
    'ops.fleet.list',
    'ops.fleet.get',
    'ops.telemetry.latest',
    'ops.placement.choose',
    'ops.drift.detect',
    'ops.migration.plan',
    'remote.nodes',
    'remote.process.inspect',
    'remote.system.inspect',
    'remote.network.inspect',
    'remote.service.inspect',
    'remote.hardware.inspect',
    'remote.vm.list',
    'remote.vm.get',
    'remote.container.list',
    'remote.container.get',
    'remote.ollama.inference_policy',
    'remote.ollama.models',
    'remote.ollama.running',
    'remote.ollama.show',
    'ollama.models',
    'ollama.running',
    'ollama.model.show',
    'sqlite.state.tables',
    'sqlite.state.query',
    'sqlite.state.integrity',
    'home_assistant.services',
    'home_assistant.states',
    'home_assistant.state',
    'portainer.endpoints',
    'portainer.containers',
    'portainer.container',
    'jmri.power',
    'jmri.roster',
    'jmri.object',
    'github.repository',
    'github.issues',
    'github.file',
    'github.pull_requests',
    'discord.status',
})


def create_capability_authorizer(
    *,
    runtime_provider,
    configuration: SofiaConfiguration,
    operator_stop: OperatorStopStore,
):
    """Resolve the current runtime at each authorization check; fail closed."""
    filesystem_root = Path(configuration.filesystem_root)
    def capability_authorized(
        request,
    ) -> bool:
        runtime = runtime_provider()

        if runtime is None:
            return False

        if (
            operator_stop.current().active
            and request.capability.name not in _STOP_SAFE_CAPABILITIES
        ):
            return False

        if request.capability.name == "codebase.inspect":
            if (
                request.capability.name
                not in configuration.standing_allowed_capabilities
            ):
                return False

            requested_scope = request.requested_scope

            if requested_scope is None:
                return True

            if not isinstance(requested_scope, Path):
                return False

            try:
                return (
                    requested_scope.resolve()
                    == filesystem_root.resolve()
                )
            except (OSError, RuntimeError):
                return False

        if request.capability.name != "filesystem.inspect":
            return (
                request.capability.name
                in configuration.standing_allowed_capabilities
            )

        authorization = runtime.filesystem_authorization

        if authorization is None:
            return False

        if (
            authorization.domain
            is not AuthorizationDomain.FILESYSTEM
        ):
            return False

        if (
            authorization.decision
            is not AuthorizationDecision.ALLOW
        ):
            return False

        configured_root = (
            filesystem_root.resolve()
        )

        if (
            authorization.scope.resolve()
            != configured_root
        ):
            return False

        requested_scope = request.requested_scope

        if requested_scope is not None:
            if not isinstance(
                requested_scope,
                Path,
            ):
                return False

            try:
                resolved_requested_scope = (
                    requested_scope.resolve()
                )
            except (
                OSError,
                RuntimeError,
            ):
                return False

            if (
                resolved_requested_scope
                != authorization.scope.resolve()
            ):
                return False

        if request.capability.name == "filesystem.inspect":
            operation = request.parameters.get(
                "operation"
            )

            operation_map = {
                "list_directory": (
                    FilesystemAuthorizationOperation.LIST_DIRECTORY
                ),
                "inspect_path": (
                    FilesystemAuthorizationOperation.INSPECT_PATH
                ),
                "read_file": (
                    FilesystemAuthorizationOperation.READ_FILE
                ),
                "search_files": (
                    FilesystemAuthorizationOperation.SEARCH_FILES
                ),
            }

            authorized_operation = operation_map.get(
                operation
            )

            if authorized_operation is None:
                return False

            if authorized_operation not in authorization.operations:
                return False

        return True

    return capability_authorized
