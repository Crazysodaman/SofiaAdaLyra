from pathlib import Path

from sofia.action.executor import TestActionExecutor
from sofia.action.system import ActionSystem
from sofia.authorization.model import (
    AuthorizationDecision,
    AuthorizationDomain,
    FilesystemAuthorizationOperation,
)
from sofia.capability.gateway import CapabilityGateway
from sofia.capability.system import CapabilitySystem
from sofia.codebase.codebase import CodebaseCapability
from sofia.codebase.inspector import CodebaseInspector
from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.conversation_assembler import ConversationalContextAssembler
from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.providers.factory import create_llm_provider
from sofia.cognition.rules import RuleEngine
from sofia.cognition.system import CognitiveSystem
from sofia.cognition.test_engine import TestCognitiveEngine
from sofia.cognition.tools import (
    CognitiveToolDispatcher,
    create_default_tool_bindings,
    create_system_tool_bindings,
)
from sofia.config.model import SofiaConfiguration
from sofia.constitution.integrity import ConstitutionIntegrityVerifier
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.store import AvatarStore
from sofia.filesystem.capability import FilesystemCapability
from sofia.filesystem.observation import FilesystemObservationStore
from sofia.identity.store import IdentityStore
from sofia.memory.store import MemoryStore
from sofia.memory.system import MemorySystem
from sofia.operational.store import OperationalStore
from sofia.personality.store import PersonalityStore
from sofia.runtime.runtime import SofiaRuntime
from sofia.system.capability import create_local_system_capabilities


def _create_cognitive_engine(configuration: SofiaConfiguration):
    if configuration.provider.provider == "test":
        return TestCognitiveEngine(
            configuration=configuration.provider
        )

    if configuration.provider.provider == "rule":
        return RuleEngine()

    if configuration.provider.provider == "test-llm":
        provider = create_llm_provider(
            configuration.provider
        )

        return LLMCognitiveEngine(
            configuration=configuration.provider,
            provider=provider,
        )

    if configuration.provider.provider == "ollama":
        provider = create_llm_provider(
            configuration.provider
        )

        return LLMCognitiveEngine(
            configuration=configuration.provider,
            provider=provider,
        )

    raise ValueError(
        f"Unknown cognitive provider: "
        f"{configuration.provider.provider}"
    )


def compose(
    configuration: SofiaConfiguration,
) -> SofiaRuntime:
    constitution_store = ConstitutionStore(
        Path(configuration.constitution_path)
    )

    integrity_verifier = ConstitutionIntegrityVerifier(
        Path(configuration.constitution_hash_path)
    )

    identity_store = IdentityStore(
        Path(configuration.identity_path)
    )

    personality_store = PersonalityStore(
        Path(configuration.personality_path)
    )

    avatar_store = AvatarStore(
        Path(configuration.avatar_path)
    )

    memory_store = MemoryStore(
        configuration.state_path
    )

    memory_system = MemorySystem(
        memory_store
    )

    operational_store = OperationalStore(
        configuration.state_path
    )

    filesystem_observation_store = FilesystemObservationStore(
        configuration.state_path
    )

    codebase_inspector = CodebaseInspector(
        root=configuration.filesystem_root,
    )

    codebase_capability = CodebaseCapability(
        inspector=codebase_inspector,
    )

    runtime_holder: dict[str, SofiaRuntime] = {}

    def filesystem_inspector_provider():
        runtime = runtime_holder.get("runtime")

        if runtime is None:
            raise RuntimeError(
                "Filesystem capability requested before runtime "
                "composition completed."
            )

        return runtime.filesystem_inspector

    filesystem_capability = FilesystemCapability(
        inspector_provider=filesystem_inspector_provider,
    )

    def capability_authorized(
        request,
    ) -> bool:
        runtime = runtime_holder.get("runtime")

        if runtime is None:
            return False

        if request.capability.name != "filesystem.inspect":
            return request.capability.name in configuration.standing_allowed_capabilities

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
            configuration.filesystem_root.resolve()
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

    capability_system = CapabilitySystem(
        authorization_checker=capability_authorized,
    )

    capability_system.register(
        capability=codebase_capability.capability,
        handler=codebase_capability.execute,
    )

    capability_system.register(
        capability=filesystem_capability.capability,
        handler=filesystem_capability.execute,
    )

    for system_capability in create_local_system_capabilities():
        capability_system.register(
            capability=system_capability.capability,
            handler=system_capability.execute,
        )

    capability_gateway = CapabilityGateway(
        capability_system=capability_system,
    )

    tool_dispatcher = CognitiveToolDispatcher(
        gateway=capability_gateway,
        bindings=(
            create_default_tool_bindings(
                configuration.filesystem_root
            )
            + create_system_tool_bindings()
        ),
    )

    cognitive_engine = _create_cognitive_engine(
        configuration
    )

    # Normal Ollama conversation uses a compact projection of the verified
    # Constitution. Full assembly remains the default for other providers,
    # constitutional questions, and any operation with exposed tools.
    context_assembler = (
        ConversationalContextAssembler()
        if configuration.provider.provider == "ollama"
        else CognitiveContextAssembler()
    )

    action_executor = TestActionExecutor()

    action_system = ActionSystem(
        executor=action_executor,
    )

    cognitive_system = CognitiveSystem(
        engine=cognitive_engine,
        context_assembler=context_assembler,
        action_system=action_system,
        tool_dispatcher=tool_dispatcher,
    )

    runtime = SofiaRuntime(
        constitution_store=constitution_store,
        integrity_verifier=integrity_verifier,
        identity_store=identity_store,
        personality_store=personality_store,
        avatar_store=avatar_store,
        memory_system=memory_system,
        cognitive_system=cognitive_system,
        capability_system=capability_system,
        configuration=configuration,
        operational_store=operational_store,
        filesystem_observation_store=filesystem_observation_store,
    )

    runtime_holder["runtime"] = runtime

    return runtime