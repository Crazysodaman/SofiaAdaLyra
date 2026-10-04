"""Foundational runtime lifecycle and canonical subsystem ownership."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sofia.package_metadata import application_name, application_version
from sofia.avatar.presentation import (
    AudienceScope,
    PresentationAuthority,
    PresentationProjection,
    PrivatePresentationGrant,
)
from sofia.avatar.self_fact_query import AvatarSelfFactResolver
from sofia.avatar.private_grant import PrivatePresentationGrantResolver
from sofia.authority.model import Authority
from sofia.authorization.model import (
    AuthorizationDecision,
    AuthorizationDomain,
    FilesystemAuthorization,
    FilesystemAuthorizationOperation,
)
from sofia.capability.system import CapabilitySystem
from sofia.cognition.matrix import ContextPlan, EvidenceRecord, EvidenceState, PrivacyProjectionPlan
from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.cognition.model_lifecycle import ModelLifecycleManager
from sofia.cognition.routing import RoutingCognitiveEngine, RoutingExecution
from sofia.cognition.system import CognitiveSystem
from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.config.model import SofiaConfiguration
from sofia.constitution.integrity import (
    ConstitutionIntegrityError,
    ConstitutionIntegrityVerifier,
)
from sofia.constitution.model import Constitution
from sofia.constitution.store import ConstitutionStore
from sofia.continuity.model import (
    ContinuityEvent,
    ContinuityEventKind,
    create_continuity_event,
)
from sofia.embodiment.model import Embodiment
from sofia.embodiment.measurement_query import MeasurementQueryResolver
from sofia.embodiment.store import EmbodimentStore
from sofia.environment.query import EnvironmentQueryResolver
from sofia.environment.service import EnvironmentService
from sofia.filesystem.changes import (
    FilesystemChangeEvent,
    detect_changes,
)
from sofia.filesystem.inspector import FilesystemInspector
from sofia.filesystem.model import FilesystemResult
from sofia.filesystem.observation import (
    FilesystemObservationStore,
    FilesystemObserver,
)
from sofia.identity.model import SofiaIdentity
from sofia.identity.store import IdentityStore
from sofia.memory.system import MemorySystem
from sofia.ops.capability import OpsToolService
from sofia.operational.model import (
    OperationalState,
    RuntimeContinuity,
)
from sofia.operational.store import OperationalStore
from sofia.operational.status_queries import OperationalStatusQueryResolver
from sofia.personality.influence import ContinuityInfluence
from sofia.personality.model import PersonalityProfile
from sofia.personality.reflection_query import ReflectionQueryResolver
from sofia.personality.store import PersonalityStore
from sofia.runtime.evidence import project_matrix_evidence
from sofia.runtime.response import respond_with_runtime_context
from sofia.runtime.model import RuntimeState
from sofia.self_model.model import (
    SofiaCoreState,
    create_core_state,
)
from sofia.self_model.operational import (
    SofiaOperationalSelfModel,
)
from sofia.social.model import PrincipalContext
from sofia.state.plane import StatePlane


class SofiaRuntimeError(Exception):
    """
    Raised when Sofía's runtime cannot complete
    an operational lifecycle transition.
    """


class SofiaRuntime:
    """
    Owns Sofía's foundational runtime lifecycle and
    subsystem coordination.
    """

    def __init__(
        self,
        constitution_store: ConstitutionStore,
        integrity_verifier: ConstitutionIntegrityVerifier,
        identity_store: IdentityStore,
        personality_store: PersonalityStore,
        embodiment_store: EmbodimentStore,
        memory_system: MemorySystem,
        cognitive_system: CognitiveSystem,
        ops_service: OpsToolService,
        capability_system: CapabilitySystem,
        configuration: SofiaConfiguration,
        state_plane: StatePlane,
        environment_service: EnvironmentService | None = None,
        operational_store: OperationalStore | None = None,
        filesystem_observation_store: (
            FilesystemObservationStore | None
        ) = None,
        model_lifecycle: ModelLifecycleManager | None = None,
    ) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError(
                "SofiaRuntime state_plane must be a StatePlane."
            )

        if not isinstance(
            capability_system,
            CapabilitySystem,
        ):
            raise TypeError(
                "SofiaRuntime capability_system must be a "
                "CapabilitySystem."
            )

        self._constitution_store = constitution_store
        self._integrity_verifier = integrity_verifier
        self._identity_store = identity_store
        self._personality_store = personality_store
        self._embodiment_store = embodiment_store
        if not isinstance(ops_service, OpsToolService):
            raise TypeError(
                "SofiaRuntime ops_service must be an OpsToolService."
            )
        self._memory_system = memory_system
        self._ops_service = ops_service
        self._cognitive_system = cognitive_system
        self._capability_system = capability_system
        self._configuration = configuration
        self._private_presentation_grants = PrivatePresentationGrantResolver(
            state_path=configuration.state_path,
            adult_verified=configuration.avatar_private_adult_verified,
        )
        if (
            model_lifecycle is not None
            and not isinstance(model_lifecycle, ModelLifecycleManager)
        ):
            raise TypeError(
                "SofiaRuntime model_lifecycle must be a "
                "ModelLifecycleManager or None."
            )
        self._model_lifecycle = model_lifecycle
        self._state_plane = state_plane
        self._environment_service = (
            environment_service
            if environment_service is not None
            else EnvironmentService(configuration.environment)
        )
        if not isinstance(
            self._environment_service,
            EnvironmentService,
        ):
            raise TypeError(
                "SofiaRuntime environment_service must be an "
                "EnvironmentService."
            )

        self._operational_store = (
            operational_store
            if operational_store is not None
            else OperationalStore(configuration.state_path)
        )

        self._filesystem_observation_store = (
            filesystem_observation_store
            if filesystem_observation_store is not None
            else FilesystemObservationStore(
                configuration.state_path
            )
        )

        if not isinstance(
            self._operational_store,
            OperationalStore,
        ):
            raise TypeError(
                "SofiaRuntime operational_store must be an "
                "OperationalStore."
            )

        if not isinstance(
            self._filesystem_observation_store,
            FilesystemObservationStore,
        ):
            raise TypeError(
                "SofiaRuntime filesystem_observation_store must be "
                "a FilesystemObservationStore."
            )

        self._filesystem_observer = FilesystemObserver(
            root=configuration.filesystem_root,
        )

        self._filesystem_inspector = FilesystemInspector(
            root=configuration.filesystem_root,
            authorized=False,
        )

        self._filesystem_authorization: (
            FilesystemAuthorization | None
        ) = None

        self._state = RuntimeState.CREATED
        self._constitution: Constitution | None = None
        self._identity: SofiaIdentity | None = None
        self._personality: PersonalityProfile | None = None
        self._embodiment: Embodiment | None = None
        self._core_state: SofiaCoreState | None = None
        self._avatar_presentation: PresentationAuthority | None = None
        self._avatar_matrix_builder = None
        self._measurement_query_resolver = MeasurementQueryResolver()
        self._avatar_self_fact_resolver = AvatarSelfFactResolver()
        self._environment_query_resolver = EnvironmentQueryResolver()
        self._operational_status_query_resolver = OperationalStatusQueryResolver()
        self._reflection_query_resolver = ReflectionQueryResolver()

        self._runtime_id: UUID | None = None
        self._started_at: datetime | None = None
        self._runtime_continuity: RuntimeContinuity | None = None
        self._workspace_changes: FilesystemChangeEvent | None = None
        self._pending_continuity_event: ContinuityEvent | None = None

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def constitution(self) -> Constitution | None:
        return self._constitution

    @property
    def constitution_store(self) -> ConstitutionStore:
        return self._constitution_store

    @property
    def integrity_verifier(
        self,
    ) -> ConstitutionIntegrityVerifier:
        return self._integrity_verifier

    @integrity_verifier.setter
    def integrity_verifier(
        self,
        verifier,
    ) -> None:
        self._integrity_verifier = verifier

    @property
    def identity(self) -> SofiaIdentity | None:
        return self._identity


    @property
    def personality(
        self,
    ) -> PersonalityProfile | None:
        return self._personality

    @property
    def personality_store(
        self,
    ) -> PersonalityStore:
        return self._personality_store

    @property
    def embodiment(self) -> Embodiment | None:
        return self._embodiment

    @property
    def core_state(self) -> SofiaCoreState | None:
        return self._core_state

    @property
    def avatar_presentation(self) -> PresentationAuthority | None:
        return self._avatar_presentation

    @property
    def avatar_presentation_projection(self) -> PresentationProjection | None:
        """Public-safe projection retained for compatibility and UI themes."""
        if self._avatar_presentation is None:
            return None
        return self._avatar_presentation.projection(AudienceScope.PUBLIC)

    def avatar_projection_for(
        self,
        *,
        principal: PrincipalContext | None,
        private_grant: PrivatePresentationGrant | None = None,
    ) -> PresentationProjection | None:
        """
        Resolve AVATAR state for one authenticated audience.

        Private presentation requires both an authenticated private principal
        and a separate current host grant. Principal identity alone never
        unlocks private presentation.
        """
        if self._avatar_presentation is None:
            return None
        if principal is None:
            return self._avatar_presentation.projection(AudienceScope.PUBLIC)
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext or None")
        if (
            principal.audience_kind.value == "private"
            and private_grant is not None
        ):
            if not isinstance(private_grant, PrivatePresentationGrant):
                raise TypeError(
                    "private_grant must be a PrivatePresentationGrant or None"
                )
            return self._avatar_presentation.projection(
                AudienceScope.PRIVATE,
                grant=private_grant,
            )
        return self._avatar_presentation.projection(AudienceScope.PUBLIC)

    def set_avatar_matrix_builder(self, builder) -> None:
        """Attach the catalog-backed matrix projector used for self-facts."""
        if builder is not None and not callable(builder):
            raise TypeError("avatar matrix builder must be callable or None")
        self._avatar_matrix_builder = builder

    def _avatar_matrix_for(self, presentation: PresentationProjection):
        builder = self._avatar_matrix_builder
        if builder is None:
            return None
        return builder(presentation.item_ids)

    def set_avatar_presentation(self, authority: PresentationAuthority) -> None:
        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "Sofía runtime must be READY before attaching AVATAR presentation."
            )
        if not isinstance(authority, PresentationAuthority):
            raise TypeError("avatar presentation must be PresentationAuthority")
        self._avatar_presentation = authority

    @property
    def ops_service(self) -> OpsToolService:
        return self._ops_service

    @property
    def memory_system(self) -> MemorySystem:
        return self._memory_system

    @property
    def cognitive_system(self) -> CognitiveSystem:
        return self._cognitive_system

    @property
    def model_lifecycle(self) -> ModelLifecycleManager | None:
        return getattr(self, "_model_lifecycle", None)

    def cognition_routing_execution(self) -> RoutingExecution | None:
        """Return the most recent actual dual-engine execution, if routed."""
        engine = self._cognitive_system.engine
        if not isinstance(engine, RoutingCognitiveEngine):
            return None
        return engine.last_execution

    @property
    def capability_system(self) -> CapabilitySystem:
        return self._capability_system

    @property
    def configuration(self) -> SofiaConfiguration:
        return self._configuration

    @property
    def state_plane(self) -> StatePlane:
        return self._state_plane


    @property
    def environment_service(self) -> EnvironmentService:
        return self._environment_service

    def replace_environment_service(
        self,
        service: EnvironmentService,
    ) -> None:
        """Replace only the live ENVIRONMENT service at an app-owned boundary."""
        if not isinstance(service, EnvironmentService):
            raise TypeError(
                "service must be an EnvironmentService"
            )
        previous = self._environment_service
        if previous is service:
            return
        service.invalidate()
        self._environment_service = service

    @property
    def operational_store(self) -> OperationalStore:
        return self._operational_store

    @property
    def filesystem_observation_store(
        self,
    ) -> FilesystemObservationStore:
        return self._filesystem_observation_store


    @property
    def runtime_id(self) -> UUID | None:
        return self._runtime_id

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    @property
    def runtime_continuity(self) -> RuntimeContinuity | None:
        return self._runtime_continuity

    @property
    def workspace_changes(
        self,
    ) -> FilesystemChangeEvent | None:
        return self._workspace_changes

    @property
    def pending_continuity_event(
        self,
    ) -> ContinuityEvent | None:
        return self._pending_continuity_event

    @property
    def filesystem_inspector(self) -> FilesystemInspector:
        return self._filesystem_inspector

    @property
    def filesystem_authorization(
        self,
    ) -> FilesystemAuthorization | None:
        return self._filesystem_authorization

    @property
    def operational_state(
        self,
    ) -> OperationalState | None:
        if (
            self._runtime_id is None
            or self._started_at is None
        ):
            return None

        model_selection = CognitiveModelSelection.from_configuration(
            self._configuration
        )
        provider_configuration = model_selection.primary

        return OperationalState(
            runtime_id=self._runtime_id,
            started_at=self._started_at,
            lifecycle_state=self._state.value,
            application_name=application_name(),
            application_version=application_version(),
            provider=provider_configuration.provider,
            model=provider_configuration.model,
        )

    @property
    def operational_self_model(
        self,
    ) -> SofiaOperationalSelfModel | None:
        operational_state = self.operational_state

        if (
            operational_state is None
            or self._runtime_continuity is None
        ):
            return None

        return SofiaOperationalSelfModel(
            operational_state=operational_state,
            continuity=self._runtime_continuity,
            workspace_changes=self._workspace_changes,
        )

    def start(self) -> None:
        if self._state not in (
            RuntimeState.CREATED,
            RuntimeState.STOPPED,
        ):
            raise SofiaRuntimeError(
                "SofiaRuntime can only start from the CREATED or STOPPED state."
            )

        self._state = RuntimeState.STARTING

        try:
            # Restart reopens the same owned stores. A partial reopen failure
            # must follow the same FAILED transition as any other startup error.
            self._operational_store.open()
            self._filesystem_observation_store.open()
            self._memory_system.open()
            self._environment_service.invalidate()

            runtime_id = uuid4()
            started_at = datetime.now(timezone.utc)

            constitution = self._constitution_store.load()

            self._integrity_verifier.verify(
                constitution
            )

            identity = self._identity_store.load()
            personality = self._personality_store.load()
            embodiment = self._embodiment_store.load()

            core_state = create_core_state(
                identity=identity,
                constitution=constitution,
            )

            continuity = (
                self._operational_store.continuity_for(
                    current_runtime_id=runtime_id,
                    current_started_at=started_at,
                )
            )

            current_observation = (
                self._filesystem_observer.observe()
            )

            previous_observation = (
                self._filesystem_observation_store.latest(
                    self._configuration.filesystem_root
                )
            )

            workspace_changes = detect_changes(
                previous=previous_observation,
                current=current_observation,
            )

            continuity_event = create_continuity_event(
                runtime_continuity=continuity,
                workspace_changes=workspace_changes,
            )

            self._constitution = constitution
            self._identity = identity
            self._personality = personality
            self._embodiment = embodiment
            self._core_state = core_state
            self._runtime_id = runtime_id
            self._started_at = started_at
            self._runtime_continuity = continuity
            self._workspace_changes = workspace_changes

            if continuity_event.kind in {
                ContinuityEventKind.RUNTIME_RESUMED,
                ContinuityEventKind.WORKSPACE_CHANGED,
                ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED,
            }:
                self._pending_continuity_event = continuity_event
            else:
                self._pending_continuity_event = None

            self._filesystem_inspector = FilesystemInspector(
                root=self._configuration.filesystem_root,
                authorized=False,
            )
            self._filesystem_authorization = None
            self._state = RuntimeState.READY

            self._operational_store.record_started(
                runtime_id=runtime_id,
                started_at=started_at,
            )

            self._filesystem_observation_store.record(
                current_observation
            )

        except ConstitutionIntegrityError as exc:
            self._rollback_failed_start(exc)

            raise SofiaRuntimeError(
                "Sofía Constitution integrity verification failed."
            ) from exc

        except Exception as exc:
            self._rollback_failed_start(exc)

            raise SofiaRuntimeError(
                "Sofía runtime failed during startup."
            ) from exc

    def current_authority(self) -> Authority:
        """Return the host authority used for a current cognitive operation."""
        return Authority(
            can_inspect_filesystem=(
                self._filesystem_authorization is not None
                and self._filesystem_inspector.authorized
            ),
            allowed_capabilities=(
                self._configuration.standing_allowed_capabilities
            ),
        )

    def matrix_evidence_availability(
        self,
        *,
        required_keys: tuple[str, ...] | None = None,
        response: CognitiveResponse | None = None,
    ) -> dict[str, EvidenceRecord | EvidenceState]:
        return project_matrix_evidence(
            self, required_keys=required_keys, response=response,
        )

    def respond(
        self,
        request: CognitiveRequest,
        filesystem_results: tuple[FilesystemResult, ...] = (),
        *,
        principal: PrincipalContext | None = None,
        context_plan: ContextPlan | None = None,
        privacy_plan: PrivacyProjectionPlan | None = None,
        contextual_influence: ContinuityInfluence | None = None,
    ) -> CognitiveResponse:
        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime must be READY before responding."
            )
        return respond_with_runtime_context(
            self, request, filesystem_results,
            principal=principal, context_plan=context_plan,
            privacy_plan=privacy_plan, contextual_influence=contextual_influence,
        )

    def consume_continuity_awareness(self) -> ContinuityEvent | None:
        event = self._pending_continuity_event
        self._pending_continuity_event = None
        return event

    def authorize_filesystem(
        self,
        authorization: FilesystemAuthorization,
    ) -> None:
        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime must be READY before authorizing "
                "filesystem inspection."
            )

        if not isinstance(
            authorization,
            FilesystemAuthorization,
        ):
            raise TypeError(
                "SofiaRuntime filesystem authorization must be "
                "a FilesystemAuthorization."
            )

        if authorization.domain is not AuthorizationDomain.FILESYSTEM:
            raise SofiaRuntimeError(
                "Filesystem authorization must target the filesystem domain."
            )

        if authorization.decision is not AuthorizationDecision.ALLOW:
            raise SofiaRuntimeError(
                "Filesystem authorization must have an ALLOW decision."
            )

        configured_root = (
            self._configuration.filesystem_root.resolve()
        )

        if authorization.scope.resolve() != configured_root:
            raise SofiaRuntimeError(
                "Filesystem authorization scope does not match "
                "the configured filesystem root."
            )

        allowed_operations = {
            FilesystemAuthorizationOperation.LIST_DIRECTORY,
            FilesystemAuthorizationOperation.INSPECT_PATH,
            FilesystemAuthorizationOperation.READ_FILE,
            FilesystemAuthorizationOperation.SEARCH_FILES,
        }

        if not set(authorization.operations).issubset(
            allowed_operations
        ):
            raise SofiaRuntimeError(
                "Filesystem authorization contains an unsupported "
                "operation."
            )

        if authorization.target is not None:
            try:
                target = authorization.target.resolve(
                    strict=False
                )
                target.relative_to(
                    configured_root
                )
            except (
                OSError,
                RuntimeError,
                ValueError,
            ) as exc:
                raise SofiaRuntimeError(
                    "Filesystem authorization target is outside "
                    "the configured filesystem root."
                ) from exc

        self._filesystem_authorization = authorization

        self._filesystem_inspector = FilesystemInspector(
            root=configured_root,
            authorized=True,
        )

    def revoke_filesystem_authorization(self) -> None:
        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime must be READY before revoking "
                "filesystem inspection."
            )

        self._filesystem_authorization = None

        self._filesystem_inspector = FilesystemInspector(
            root=self._configuration.filesystem_root,
            authorized=False,
        )


    def shutdown(self) -> None:
        if self._state is RuntimeState.STOPPED:
            raise SofiaRuntimeError(
                "SofiaRuntime is already stopped."
            )

        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime can only shut down from the READY state."
            )

        runtime_id = self._runtime_id

        if runtime_id is None:
            raise SofiaRuntimeError(
                "SofiaRuntime READY state is missing a runtime ID."
            )

        stopped_at = datetime.now(timezone.utc)

        self._operational_store.record_stopped(
            runtime_id=runtime_id,
            stopped_at=stopped_at,
        )

        # Runtime owns these persistent SQLite resources. Closing them here is
        # part of the STOPPED transition, not a test-only cleanup detail.
        # This is especially important on Windows, where an open SQLite handle
        # prevents state-file replacement, recovery, and disposable test cleanup.
        self._clear_runtime_state()
        self._state = RuntimeState.STOPPED
        self._close_runtime_resources()

    def _close_runtime_resources(self) -> None:
        """Attempt every owned close, including after a partial reopen."""
        try:
            self._memory_system.close()
        finally:
            try:
                self._filesystem_observation_store.close()
            finally:
                self._operational_store.close()

    def _rollback_failed_start(self, failure: Exception) -> None:
        self._state = RuntimeState.FAILED
        try:
            self._clear_runtime_state()
        except Exception as cleanup_error:
            failure.add_note(f"Runtime state cleanup failed: {cleanup_error}")
        try:
            self._close_runtime_resources()
        except Exception as cleanup_error:
            failure.add_note(f"Runtime resource cleanup failed: {cleanup_error}")

    def _clear_runtime_state(self) -> None:
        self._constitution = None
        self._identity = None
        self._personality = None
        self._embodiment = None
        self._core_state = None
        self._avatar_presentation = None
        self._environment_service.invalidate()
        self._runtime_id = None
        self._started_at = None
        self._runtime_continuity = None
        self._workspace_changes = None
        self._pending_continuity_event = None
        self._filesystem_authorization = None
        self._filesystem_inspector = FilesystemInspector(
            root=self._configuration.filesystem_root,
            authorized=False,
        )
