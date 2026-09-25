from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import metadata
from pathlib import Path
from uuid import UUID, uuid4

from sofia.authority.model import Authority
from sofia.authorization.model import (
    AuthorizationDecision,
    AuthorizationDomain,
    FilesystemAuthorization,
    FilesystemAuthorizationOperation,
)
from sofia.capability.system import CapabilitySystem
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import CognitiveRequest
from sofia.cognition.operation import CognitiveOperation
from sofia.cognition.system import CognitiveSystem
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
from sofia.embodiment.store import AvatarStore
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
from sofia.operational.model import (
    OperationalState,
    RuntimeContinuity,
)
from sofia.operational.store import OperationalStore
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
        capability_system: CapabilitySystem,
        configuration: SofiaConfiguration,
        operational_store: OperationalStore | None = None,
        filesystem_observation_store: (
            FilesystemObservationStore | None
        ) = None,
    ) -> None:
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
        self._memory_system = memory_system
        self._cognitive_system = cognitive_system
        self._capability_system = capability_system
        self._configuration = configuration

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
        self._measurement_query_resolver = MeasurementQueryResolver()

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
    def memory_system(self) -> MemorySystem:
        return self._memory_system

    @property
    def cognitive_system(self) -> CognitiveSystem:
        return self._cognitive_system

    @property
    def capability_system(self) -> CapabilitySystem:
        return self._capability_system

    @property
    def configuration(self) -> SofiaConfiguration:
        return self._configuration

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

        return OperationalState(
            runtime_id=self._runtime_id,
            started_at=self._started_at,
            lifecycle_state=self._state.value,
            application_name=_application_name(),
            application_version=_application_version(),
            provider=self._configuration.provider.provider,
            model=self._configuration.provider.model,
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

    def respond(
        self,
        request: CognitiveRequest,
        filesystem_results: tuple[FilesystemResult, ...] = (),
    ):
        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime must be READY before responding."
            )

        if not isinstance(request, CognitiveRequest):
            raise TypeError(
                "SofiaRuntime request must be a CognitiveRequest."
            )

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

        memories = self._memory_system.recall_relevant(
            user_content
        )

        measurement_query = None

        if self._embodiment is not None:
            measurement_query = self._measurement_query_resolver.resolve(
                query=user_content,
                embodiment=self._embodiment,
            )

        operation = CognitiveOperation(
            context=CognitiveContext(
                request=request,
                identity=self._identity,
                personality=self._personality,
                constitution=self._constitution,
                embodiment=self._embodiment,
                measurement_query=measurement_query,
                core_state=self._core_state,
                memories=memories,
                operational_state=self.operational_state,
                runtime_continuity=self._runtime_continuity,
                filesystem_results=filesystem_results,
                workspace_changes=self._workspace_changes,
                operational_self_model=self.operational_self_model,
            ),
            authority=self._operation_authority(),
        )

        return self._cognitive_system.respond(
            operation
        )

    def _operation_authority(self) -> Authority:
        allowed = [
            "process.inspect",
            "system.inspect",
            "network.inspect",
            "service.inspect",
            "machine.inspect",
        ]
        filesystem_allowed = (
            self._filesystem_authorization is not None
            and self._filesystem_authorization.decision
            is AuthorizationDecision.ALLOW
        )
        if filesystem_allowed:
            allowed.extend(
                (
                    "codebase.inspect",
                    "knowledge.source.read",
                    "knowledge.search",
                )
            )
        return Authority(
            can_respond=True,
            can_propose_actions=True,
            can_execute_actions=False,
            can_inspect_filesystem=filesystem_allowed,
            allowed_capabilities=tuple(allowed),
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

        self._clear_runtime_state()
        self._state = RuntimeState.STOPPED

    def _clear_runtime_state(self) -> None:
        self._constitution = None
        self._identity = None
        self._personality = None
        self._embodiment = None
        self._core_state = None
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
    def _latest_user_content(
        request: CognitiveRequest,
    ) -> str:
        for message in reversed(
            request.messages
        ):
            if message.role.value == "user":
                return message.content

        return ""