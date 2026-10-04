"""Wire configured subsystem instances into one foundational runtime."""
from dataclasses import replace
from pathlib import Path

from sofia.action.executor import FailClosedActionExecutor
from sofia.action.system import ActionSystem
from sofia.capability.gateway import CapabilityGateway
from sofia.capability.catalog import ToolCatalogCapability,create_tool_catalog_binding
from sofia.capability.system import CapabilitySystem
from sofia.codebase.codebase import CodebaseCapability
from sofia.codebase.inspector import CodebaseInspector
from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.conversation_assembler import ConversationalContextAssembler
from sofia.cognition.system import CognitiveSystem
from sofia.cognition.tools import (
    CognitiveToolDispatcher,
    create_default_tool_bindings,
    create_system_tool_bindings,
)
from sofia.composition.authorization import create_capability_authorizer
from sofia.composition.engines import create_cognitive_engine, create_model_lifecycle
from sofia.config.model import SofiaConfiguration
from sofia.config.reviewed_projection import apply_reviewed_configuration
from sofia.constitution.integrity import ConstitutionIntegrityVerifier
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.store import EmbodimentStore
from sofia.environment.config import ConfiguredLocation
from sofia.environment.factory import create_environment_service
from sofia.environment.model import LocationSubject
from sofia.distributed.capability import create_configured_remote_fleet_tools
from sofia.distributed.inference_client import (
    create_configured_remote_inference_client,
)
from sofia.dev.capability import DevCapabilitySet,DevToolService,create_dev_tool_bindings
from sofia.filesystem.capability import FilesystemCapability
from sofia.filesystem.change_capability import FilesystemChangesCapability,create_filesystem_changes_binding
from sofia.filesystem.observation import FilesystemObservationStore
from sofia.identity.store import IdentityStore
from sofia.integrations.capabilities import create_configured_integration_tools
from sofia.memory.chatgpt_export_store import ChatGPTExportEvidenceStore
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.store import MemoryStore
from sofia.knowledge.access import KnowledgeAccessStore
from sofia.knowledge.capability import KnowledgeCapabilitySet,create_knowledge_tool_bindings
from sofia.knowledge.lifecycle import SQLiteKnowledgeLifecycle
from sofia.knowledge.persistence import SQLiteKnowledgeStore
from sofia.knowledge.service import KnowledgeService
from sofia.memory.system import MemorySystem
from sofia.machine.capability import HardwareInspectionCapability,MachineCapabilitySet,MachineToolService,create_machine_tool_bindings
from sofia.machine.discovery import create_machine_discovery
from sofia.machine.location import MachineLocationRegistry
from sofia.ops.capability import OpsCapabilitySet,OpsToolService,create_ops_tool_bindings
from sofia.safe.capability_policy import protected_capability_extras
from sofia.safe.dev_approval import DevApprovalVerifier
from sofia.safe.execution_approval import ExecutionApprovalVerifier
from sofia.safe.operator_stop import OperatorStopStore
from sofia.operational.store import OperationalStore
from sofia.personality.store import PersonalityStore
from sofia.runtime.runtime import SofiaRuntime
from sofia.system.capability import create_local_system_capabilities
from sofia.state.sqlite_plane import SQLiteStatePlane


def _configuration_with_persistent_host_location(
    configuration: SofiaConfiguration,
    state_plane: SQLiteStatePlane | None = None,
) -> SofiaConfiguration:
    """Use durable machine location unless an explicit process override exists."""
    if configuration.environment.host_location is not None:
        return configuration

    state_path = Path(configuration.state_path)
    registry_path = state_path.parent / "machine-locations.json"

    try:
        identity = create_machine_discovery().discover().identity
        record = MachineLocationRegistry(
            state_plane if state_plane is not None else SQLiteStatePlane(state_path),
            legacy_path=registry_path,
        ).get(identity.machine_id)
    except (OSError, RuntimeError, TypeError, ValueError):
        return configuration

    if record is None:
        return configuration

    host_location = ConfiguredLocation(
        label=record.label,
        timezone=record.timezone,
        subject=LocationSubject.HOST,
        latitude=record.latitude,
        longitude=record.longitude,
        source_id=f"machine.location:{record.machine_id}",
    )
    environment = replace(
        configuration.environment,
        host_location=host_location,
    )
    return replace(
        configuration,
        environment=environment,
    )


def compose(
    configuration: SofiaConfiguration,
) -> SofiaRuntime:
    state_path = Path(configuration.state_path)
    state_plane = SQLiteStatePlane(state_path)
    configuration = apply_reviewed_configuration(
        configuration,
        state_plane,
    )
    protected_extras = protected_capability_extras(state_plane)
    if protected_extras:
        configuration = replace(
            configuration,
            standing_allowed_capabilities=tuple(
                dict.fromkeys(
                    configuration.standing_allowed_capabilities
                    + protected_extras
                )
            ),
        )
    configuration = _configuration_with_persistent_host_location(
        configuration,
        state_plane,
    )
    filesystem_root = Path(configuration.filesystem_root)

    constitution_store = ConstitutionStore(
        Path(configuration.constitution_path)
    )

    integrity_verifier = ConstitutionIntegrityVerifier(
        Path(configuration.constitution_hash_path)
    )

    identity_store = IdentityStore(
        Path(configuration.identity_path),
        bootstrap_mode=configuration.identity_bootstrap_mode,
    )

    personality_store = PersonalityStore(
        Path(configuration.personality_path)
    )

    embodiment_store = EmbodimentStore(
        Path(configuration.avatar_path)
    )

    memory_store = MemoryStore(
        configuration.state_path
    )

    memory_candidate_store = DurableMemoryCandidateStore(
        configuration.state_path
    )

    memory_system = MemorySystem(
        memory_store,
        candidate_store=memory_candidate_store,
        historical_store=ChatGPTExportEvidenceStore(
            configuration.state_path
        ),
    )

    operational_store = OperationalStore(
        configuration.state_path
    )

    filesystem_observation_store = FilesystemObservationStore(
        configuration.state_path
    )

    environment_service = create_environment_service(
        configuration
    )

    knowledge_store = SQLiteKnowledgeStore(
        state_path,
        legacy_path=state_path.parent / "knowledge.json",
    )
    knowledge_lifecycle = SQLiteKnowledgeLifecycle(
        state_path,
        legacy_path=state_path.parent / "knowledge-lifecycle.json",
    )
    knowledge_service = KnowledgeService(
        filesystem_root,
        knowledge_store,
        knowledge_lifecycle,
        KnowledgeAccessStore(state_path),
    )
    execution_approval_verifier = ExecutionApprovalVerifier(state_path)
    knowledge_capabilities = KnowledgeCapabilitySet(
        knowledge_service,
        approval_verifier=execution_approval_verifier,
    )

    dev_approval_verifier = DevApprovalVerifier(state_path)
    dev_service = DevToolService(
        filesystem_root,
        state_path,
        approval_verifier=dev_approval_verifier,
        state_plane=state_plane,
    )
    dev_capabilities = DevCapabilitySet(
        dev_service
    )

    machine_service = MachineToolService(
        state_path,
        state_plane=state_plane,
    )
    machine_capabilities = MachineCapabilitySet(
        machine_service
    )

    ops_service = OpsToolService(
        state_path,
        state_plane=state_plane,
    )
    ops_capabilities = OpsCapabilitySet(
        ops_service
    )

    codebase_inspector = CodebaseInspector(
        root=filesystem_root,
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
    filesystem_changes_capability = FilesystemChangesCapability(
        filesystem_root,
        filesystem_observation_store,
    )

    operator_stop = OperatorStopStore(state_path)
    capability_authorized = create_capability_authorizer(
        runtime_provider=lambda: runtime_holder.get("runtime"),
        configuration=configuration,
        operator_stop=operator_stop,
    )

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
    capability_system.register(
        capability=filesystem_changes_capability.capability,
        handler=filesystem_changes_capability.execute,
    )

    for system_capability in create_local_system_capabilities():
        capability_system.register(
            capability=system_capability.capability,
            handler=system_capability.execute,
        )

    hardware_capability = HardwareInspectionCapability()
    capability_system.register(
        capability=hardware_capability.capability,
        handler=hardware_capability.execute,
    )

    for knowledge_capability in knowledge_capabilities.capabilities():
        capability_system.register(
            capability=knowledge_capability,
            handler=knowledge_capabilities.execute,
        )

    for dev_capability in dev_capabilities.capabilities():
        capability_system.register(
            capability=dev_capability,
            handler=dev_capabilities.execute,
        )

    for machine_capability in machine_capabilities.capabilities():
        capability_system.register(
            capability=machine_capability,
            handler=machine_capabilities.execute,
        )

    for ops_capability in ops_capabilities.capabilities():
        capability_system.register(
            capability=ops_capability,
            handler=ops_capabilities.execute,
        )

    integration_tools = create_configured_integration_tools(
        filesystem_root=filesystem_root,
        state_path=state_path,
    )
    remote_fleet_tools = create_configured_remote_fleet_tools(
        state_path
    )
    for registration in integration_tools:
        capability_system.register(
            capability=registration.capability,
            handler=registration.handler,
        )
    for registration in remote_fleet_tools:
        capability_system.register(
            capability=registration.capability,
            handler=registration.handler,
        )

    tool_catalog_capability = ToolCatalogCapability(
        capability_system,
        configuration.standing_allowed_capabilities,
    )
    capability_system.register(
        capability=tool_catalog_capability.capability,
        handler=tool_catalog_capability.execute,
    )

    capability_gateway = CapabilityGateway(
        capability_system=capability_system,
    )

    tool_dispatcher = CognitiveToolDispatcher(
        gateway=capability_gateway,
        bindings=(
            (create_tool_catalog_binding(),create_filesystem_changes_binding())
            + create_default_tool_bindings(
                filesystem_root
            )
            + create_system_tool_bindings()
            + create_knowledge_tool_bindings()
            + create_dev_tool_bindings()
            + create_machine_tool_bindings()
            + create_ops_tool_bindings()
            + tuple(registration.binding for registration in integration_tools)
            + tuple(registration.binding for registration in remote_fleet_tools)
        ),
    )

    model_lifecycle = create_model_lifecycle(
        configuration
    )
    remote_inference_client = None
    local_host_id = None
    if configuration.fleet_cognition.enabled:
        remote_inference_client = create_configured_remote_inference_client(
            state_path
        )
        if remote_inference_client is None:
            raise ValueError(
                "Fleet cognition is enabled but pinned-mTLS remote transport "
                "is not configured"
            )
        local_host_id = (
            create_machine_discovery().discover().identity.machine_id
        )
    cognitive_engine = create_cognitive_engine(
        configuration,
        lifecycle=model_lifecycle,
        ops_service=ops_service,
        local_host_id=local_host_id,
        remote_inference_client=remote_inference_client,
    )

    # Normal Ollama conversation uses a compact projection of the verified
    # Constitution. Full assembly remains the default for other providers,
    # constitutional questions, and any operation with exposed tools.
    routed_primary = (
        configuration.routing.primary
        if (
            configuration.routing is not None
            and configuration.routing.enabled
        )
        else None
    )
    uses_ollama = (
        configuration.provider.provider == "ollama"
        or (
            routed_primary is not None
            and routed_primary.provider == "ollama"
        )
    )
    context_assembler = (
        ConversationalContextAssembler()
        if uses_ollama
        else CognitiveContextAssembler()
    )

    action_executor = FailClosedActionExecutor()

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
        embodiment_store=embodiment_store,
        memory_system=memory_system,
        cognitive_system=cognitive_system,
        ops_service=ops_service,
        capability_system=capability_system,
        configuration=configuration,
        state_plane=state_plane,
        environment_service=environment_service,
        operational_store=operational_store,
        filesystem_observation_store=filesystem_observation_store,
        model_lifecycle=model_lifecycle,
    )

    runtime_holder["runtime"] = runtime

    return runtime
