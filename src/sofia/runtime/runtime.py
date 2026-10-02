from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import metadata
from pathlib import Path
from uuid import UUID, uuid4

from sofia.avatar.presentation import (
    AudienceScope,
    PresentationAuthority,
    PresentationProjection,
    PrivatePresentationGrant,
)
from sofia.avatar.self_fact_query import AvatarSelfFactResolver
from sofia.authority.model import Authority
from sofia.authorization.model import (
    AuthorizationDecision,
    AuthorizationDomain,
    FilesystemAuthorization,
    FilesystemAuthorizationOperation,
)
from sofia.capability.system import CapabilitySystem
from sofia.cognition.context import CognitiveContext
from sofia.cognition.matrix import (
    ContextPlan,
    EvidenceRecord,
    EvidenceState,
    HistoryPolicy,
    MatrixDomain,
)
from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.cognition.model_lifecycle import ModelLifecycleManager
from sofia.cognition.routing import RoutingCognitiveEngine, RoutingExecution
from sofia.cognition.operation import CognitiveOperation
from sofia.cognition.system import CognitiveSystem
from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.config.model import SofiaConfiguration
from sofia.config.state_store import StatePlaneConfigurationStore
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
from sofia.embodiment.store import AvatarStore
from sofia.environment.model import EnvironmentFreshness
from sofia.environment.prompt import environment_details_relevant
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
from sofia.dev.release_store import ReleaseStateStore
from sofia.operational.model import (
    OperationalState,
    RuntimeContinuity,
)
from sofia.operational.store import OperationalStore
from sofia.operational.status_queries import OperationalStatusQueryResolver
from sofia.personality.model import PersonalityProfile
from sofia.personality.store import PersonalityStore
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
from sofia.verify.semantic_integrity import SemanticIntegrityVerifier


_PACKAGE_NAME = "sofia-ada-lyra"


def _application_name() -> str:
    try:
        value = metadata(_PACKAGE_NAME)["Name"]
    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"Application package metadata not found: {_PACKAGE_NAME!r}."
        ) from exc

    if not value:
        raise RuntimeError(
            "Application package metadata contains no package name."
        )

    return value


def _application_version() -> str:
    try:
        value = metadata(_PACKAGE_NAME)["Version"]
    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"Application package metadata not found: {_PACKAGE_NAME!r}."
        ) from exc

    if not value:
        raise RuntimeError(
            "Application package metadata contains no package version."
        )

    return value


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
        avatar_store: AvatarStore,
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
        self._avatar_store = avatar_store
        if not isinstance(ops_service, OpsToolService):
            raise TypeError(
                "SofiaRuntime ops_service must be an OpsToolService."
            )
        self._memory_system = memory_system
        self._ops_service = ops_service
        self._cognitive_system = cognitive_system
        self._capability_system = capability_system
        self._configuration = configuration
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
        self._configuration_store = StatePlaneConfigurationStore(state_plane)
        self._release_state_store = ReleaseStateStore(state_plane)
        self._semantic_integrity = SemanticIntegrityVerifier(
            configuration.state_path,
            state_plane=state_plane,
        )
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
        self._measurement_query_resolver = MeasurementQueryResolver()
        self._avatar_self_fact_resolver = AvatarSelfFactResolver()
        self._environment_query_resolver = EnvironmentQueryResolver()
        self._operational_status_query_resolver = OperationalStatusQueryResolver()

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
    def identity_store(self) -> IdentityStore:
        return self._identity_store

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
    def avatar_store(self) -> AvatarStore:
        return self._avatar_store

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
    def configuration_store(self) -> StatePlaneConfigurationStore:
        return self._configuration_store

    @property
    def release_state_store(self) -> ReleaseStateStore:
        return self._release_state_store

    @property
    def semantic_integrity(self) -> SemanticIntegrityVerifier:
        return self._semantic_integrity

    @property
    def environment_service(self) -> EnvironmentService:
        return self._environment_service

    @property
    def operational_store(self) -> OperationalStore:
        return self._operational_store

    @property
    def filesystem_observation_store(
        self,
    ) -> FilesystemObservationStore:
        return self._filesystem_observation_store

    @property
    def filesystem_observer(
        self,
    ) -> FilesystemObserver:
        return self._filesystem_observer

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
            application_name=_application_name(),
            application_version=_application_version(),
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

        # STOPPED releases all owned SQLite handles. Starting the same runtime
        # object must symmetrically reopen those resources before continuity,
        # observation, or memory work touches them.
        self._operational_store.open()
        self._filesystem_observation_store.open()
        self._memory_system.open()

        environment_service = getattr(self, "_environment_service", None)
        if environment_service is not None:
            environment_service.invalidate()

        runtime_id = uuid4()
        started_at = datetime.now(timezone.utc)

        try:
            constitution = self._constitution_store.load()

            self._integrity_verifier.verify(
                constitution
            )

            identity = self._identity_store.load()
            personality = self._personality_store.load()
            embodiment = self._avatar_store.load()

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
            self._clear_runtime_state()
            self._state = RuntimeState.FAILED

            raise SofiaRuntimeError(
                "Sofía Constitution integrity verification failed."
            ) from exc

        except Exception as exc:
            self._clear_runtime_state()
            self._state = RuntimeState.FAILED

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
        """Project only host-owned evidence requested by the matrix layer."""
        if required_keys is not None:
            if not isinstance(required_keys, tuple):
                raise TypeError("required_keys must be a tuple or None")
            if any(
                not isinstance(key, str) or not key.strip()
                for key in required_keys
            ):
                raise ValueError(
                    "required_keys must contain nonempty strings"
                )
            wanted = set(required_keys)
        else:
            wanted = {
                "avatar.canonical",
                "memory.retrieval",
                "cognition.configuration",
                "continuity.current",
                "interaction.interpretation",
                "emotion.current",
                "operational.measurement",
                "action.execution_receipt",
                "environment.current",
                "environment.weather.current",
                "environment.clock.current",
                "environment.location.current",
                "environment.calendar.current",
            }

        all_static: dict[str, EvidenceRecord | EvidenceState] = {
            "avatar.canonical": EvidenceRecord(
                "avatar.canonical",
                (
                    EvidenceState.AVAILABLE
                    if self._embodiment is not None
                    else EvidenceState.MISSING
                ),
                (
                    "runtime:embodiment"
                    if self._embodiment is not None
                    else None
                ),
            ),
            "memory.retrieval": EvidenceRecord(
                "memory.retrieval",
                EvidenceState.AVAILABLE,
                "runtime:memory-system",
            ),
            "cognition.configuration": EvidenceRecord(
                "cognition.configuration",
                EvidenceState.AVAILABLE,
                "runtime:cognitive-configuration",
            ),
            "continuity.current": EvidenceRecord(
                "continuity.current",
                (
                    EvidenceState.AVAILABLE
                    if self._runtime_continuity is not None
                    else EvidenceState.MISSING
                ),
                (
                    "runtime:continuity"
                    if self._runtime_continuity is not None
                    else None
                ),
            ),
            "interaction.interpretation": EvidenceState.UNKNOWN,
            "emotion.current": EvidenceState.UNKNOWN,
            "operational.measurement": EvidenceState.MISSING,
            "action.execution_receipt": EvidenceState.MISSING,
        }
        availability = {
            key: value
            for key, value in all_static.items()
            if key in wanted
        }

        environment_keys = {
            "environment.current",
            "environment.weather.current",
            "environment.location.current",
            "environment.calendar.current",
        }
        snapshot = (
            self._environment_service.snapshot(refresh_providers=False)
            if wanted & environment_keys
            else None
        )

        if "environment.clock.current" in wanted:
            availability["environment.clock.current"] = EvidenceRecord(
                "environment.clock.current",
                EvidenceState.AVAILABLE,
                "runtime:clock",
            )

        if snapshot is not None:
            if (
                snapshot.weather is not None
                and snapshot.weather_freshness
                is EnvironmentFreshness.CURRENT
            ):
                weather_state: EvidenceRecord | EvidenceState = (
                    EvidenceRecord(
                        "environment.weather.current",
                        EvidenceState.AVAILABLE,
                        f"environment:{snapshot.weather.source_id}",
                    )
                )
            elif snapshot.weather_freshness is EnvironmentFreshness.STALE:
                weather_state = EvidenceState.STALE
            else:
                weather_state = EvidenceState.MISSING

            if "environment.weather.current" in wanted:
                availability["environment.weather.current"] = weather_state

            if "environment.current" in wanted:
                availability["environment.current"] = (
                    EvidenceRecord(
                        "environment.current",
                        EvidenceState.AVAILABLE,
                        "environment:snapshot",
                    )
                )

            if "environment.location.current" in wanted:
                if (
                    snapshot.current_location is not None
                    and snapshot.current_location_freshness
                    is EnvironmentFreshness.CURRENT
                ):
                    availability["environment.location.current"] = (
                        EvidenceRecord(
                            "environment.location.current",
                            EvidenceState.AVAILABLE,
                            (
                                "environment:"
                                + snapshot.current_location.source_id
                            ),
                        )
                    )
                elif (
                    snapshot.current_location_freshness
                    is EnvironmentFreshness.STALE
                ):
                    availability["environment.location.current"] = (
                        EvidenceState.STALE
                    )
                else:
                    availability["environment.location.current"] = (
                        EvidenceState.MISSING
                    )

            if "environment.calendar.current" in wanted:
                availability["environment.calendar.current"] = (
                    EvidenceRecord(
                        "environment.calendar.current",
                        EvidenceState.AVAILABLE,
                        "runtime:calendar",
                    )
                    if (
                        snapshot.season is not None
                        or snapshot.daylight is not None
                    )
                    else EvidenceState.MISSING
                )

        if response is not None and "operational.measurement" in wanted:
            if not isinstance(response, CognitiveResponse):
                raise TypeError(
                    "matrix evidence response must be CognitiveResponse or None"
                )
            operational_refs = tuple(
                ref
                for ref in response.evidence_refs
                if ref.startswith(
                    (
                        "capability:system.inspect",
                        "capability:process.inspect",
                        "capability:network.inspect",
                        "capability:hardware.inspect",
                        "capability:service.inspect",
                        "capability:ops.",
                        "capability:telemetry.",
                    )
                )
            )
            if operational_refs:
                availability["operational.measurement"] = EvidenceRecord(
                    "operational.measurement",
                    EvidenceState.AVAILABLE,
                    operational_refs[0],
                )

        if response is not None and "action.execution_receipt" in wanted:
            execution_refs = tuple(
                ref
                for ref in response.evidence_refs
                if ref.startswith("execution-receipt:")
            )
            if execution_refs:
                availability["action.execution_receipt"] = EvidenceRecord(
                    "action.execution_receipt",
                    EvidenceState.AVAILABLE,
                    execution_refs[0],
                )

        return availability

    def respond(
        self,
        request: CognitiveRequest,
        filesystem_results: tuple[FilesystemResult, ...] = (),
        *,
        principal: PrincipalContext | None = None,
        context_plan: ContextPlan | None = None,
    ):
        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime must be READY before responding."
            )

        if not isinstance(request, CognitiveRequest):
            raise TypeError(
                "SofiaRuntime request must be a CognitiveRequest."
            )

        if principal is not None and not isinstance(principal, PrincipalContext):
            raise TypeError(
                "SofiaRuntime principal must be a PrincipalContext or None."
            )

        if context_plan is not None and not isinstance(
            context_plan, ContextPlan
        ):
            raise TypeError(
                "SofiaRuntime context_plan must be a ContextPlan or None."
            )

        selective_context = (
            context_plan is not None
            and context_plan.history_policy
            in (HistoryPolicy.NONE, HistoryPolicy.RETRIEVE_SPECIFIC)
        )

        def include_domain(*domains: MatrixDomain) -> bool:
            if not selective_context or context_plan is None:
                return True
            included = set(context_plan.included_domains)
            return any(domain in included for domain in domains)

        if not isinstance(filesystem_results, tuple):
            raise TypeError(
                "SofiaRuntime filesystem_results must be a tuple."
            )

        for result in filesystem_results:
            if not isinstance(result, FilesystemResult):
                raise TypeError(
                    "SofiaRuntime filesystem_results must contain "
                    "FilesystemResult instances."
                )

        user_content = self._latest_user_content(request)
        environment_query = user_content
        if (
            user_content
            and self._environment_query_resolver.is_generic_source_followup(
                user_content
            )
        ):
            previous_user_content = self._previous_user_content(request)
            if (
                previous_user_content
                and self._environment_query_resolver.is_weather_or_forecast_query(
                    previous_user_content
                )
            ):
                environment_query = "what is your weather source"

        if user_content:
            status_answer = self._operational_status_query_resolver.resolve(
                user_content,
                selection=CognitiveModelSelection.from_configuration(
                    self._configuration
                ),
            )
            if status_answer.recognized:
                return CognitiveResponse(content=status_answer.content)

        presentation = self.avatar_projection_for(
            principal=principal,
        )
        if (
            user_content
            and self._embodiment is not None
            and presentation is not None
            and self._avatar_presentation is not None
        ):
            self_fact = self._avatar_self_fact_resolver.resolve(
                user_content,
                embodiment=self._embodiment,
                presentation=presentation,
                available_outfit_ids=self._avatar_presentation.available_outfit_ids,
            )
            if self_fact.recognized:
                return CognitiveResponse(content=self_fact.content)

        environment_snapshot = None
        environment_details_needed = environment_details_relevant(
            user_content or None
        )
        environment_service = getattr(
            self,
            "_environment_service",
            None,
        )
        if (
            environment_service is not None
            and environment_query
            and self._environment_query_resolver.might_match(
                environment_query
            )
        ):
            environment_snapshot = (
                environment_service.snapshot(
                    refresh_providers=environment_details_needed,
                )
            )
            environment_answer = (
                self._environment_query_resolver.resolve(
                    environment_query,
                    snapshot=environment_snapshot,
                )
            )
            if environment_answer.recognized:
                return CognitiveResponse(
                    content=environment_answer.content
                )

        if include_domain(MatrixDomain.MEMORY):
            memories = self._memory_system.recall_relevant(
                user_content,
                principal=principal,
            )
            historical_conversation_evidence = (
                self._memory_system.recall_historical_evidence(
                    user_content,
                    principal=principal,
                )
            )
        else:
            memories = ()
            historical_conversation_evidence = ()

        measurement_query = None

        if (
            self._embodiment is not None
            and include_domain(MatrixDomain.AVATAR)
        ):
            measurement_query = self._measurement_query_resolver.resolve(
                query=user_content,
                embodiment=self._embodiment,
            )

        if (
            environment_snapshot is None
            and environment_service is not None
            and include_domain(MatrixDomain.ENVIRONMENT)
        ):
            environment_snapshot = (
                environment_service.snapshot(
                    refresh_providers=environment_details_needed,
                )
            )

        operation = CognitiveOperation(
            context=CognitiveContext(
                request=request,
                identity=self._identity,
                personality=self._personality,
                constitution=self._constitution,
                embodiment=(
                    self._embodiment
                    if include_domain(
                        MatrixDomain.AVATAR,
                        MatrixDomain.INTERACTION,
                    )
                    else None
                ),
                measurement_query=measurement_query,
                core_state=self._core_state,
                memories=memories,
                historical_conversation_evidence=(
                    historical_conversation_evidence
                ),
                operational_state=(
                    self.operational_state
                    if include_domain(
                        MatrixDomain.COGNITION,
                        MatrixDomain.MACHINE,
                        MatrixDomain.OPS,
                        MatrixDomain.AUTHORITY,
                        MatrixDomain.CONTINUITY,
                    )
                    else None
                ),
                runtime_continuity=(
                    self._runtime_continuity
                    if include_domain(MatrixDomain.CONTINUITY)
                    else None
                ),
                filesystem_results=filesystem_results,
                workspace_changes=(
                    self._workspace_changes
                    if include_domain(MatrixDomain.CONTINUITY)
                    else None
                ),
                operational_self_model=(
                    self.operational_self_model
                    if include_domain(
                        MatrixDomain.COGNITION,
                        MatrixDomain.MACHINE,
                        MatrixDomain.OPS,
                    )
                    else None
                ),
                avatar_presentation=(
                    self.avatar_projection_for(principal=principal)
                    if include_domain(
                        MatrixDomain.AVATAR,
                        MatrixDomain.INTERACTION,
                    )
                    else None
                ),
                environment_snapshot=(
                    environment_snapshot
                    if include_domain(MatrixDomain.ENVIRONMENT)
                    else None
                ),
                principal=principal,
            ),
            authority=self.current_authority(),
        )

        return self._cognitive_system.respond(
            operation
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

    def enable_filesystem_inspection(self) -> None:
        raise SofiaRuntimeError(
            "Direct filesystem inspection enabling is no longer "
            "supported. Explicit filesystem authorization is required."
        )

    def disable_filesystem_inspection(self) -> None:
        self.revoke_filesystem_authorization()

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
        try:
            self._memory_system.close()
        finally:
            try:
                self._filesystem_observation_store.close()
            finally:
                self._operational_store.close()

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

    @staticmethod
    def _previous_user_content(
        request: CognitiveRequest,
    ) -> str:
        seen_latest = False
        for message in reversed(request.messages):
            if message.role.value != "user":
                continue
            if not seen_latest:
                seen_latest = True
                continue
            return message.content
        return ""

    @staticmethod
    def _latest_user_content(
        request: CognitiveRequest,
    ) -> str:
        for message in reversed(
            request.messages
        ):
            if message.role.value == "user":
                return message.content

        return ""