from datetime import datetime, timezone
from uuid import UUID, uuid4

from sofia.application.metadata import (
    application_name,
    application_version,
)
from sofia.authority.model import Authority
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
from sofia.embodiment.model import Embodiment
from sofia.embodiment.store import AvatarStore
from sofia.filesystem.inspector import FilesystemInspector
from sofia.identity.model import SofiaIdentity
from sofia.identity.store import IdentityStore
from sofia.memory.system import MemorySystem
from sofia.operational.model import OperationalState
from sofia.personality.model import PersonalityProfile
from sofia.personality.store import PersonalityStore
from sofia.runtime.model import RuntimeState
from sofia.self_model.model import (
    SofiaCoreState,
    create_core_state,
)


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
        configuration: SofiaConfiguration,
    ) -> None:
        self._constitution_store = constitution_store
        self._integrity_verifier = integrity_verifier
        self._identity_store = identity_store
        self._personality_store = personality_store
        self._avatar_store = avatar_store
        self._memory_system = memory_system
        self._cognitive_system = cognitive_system
        self._configuration = configuration

        self._filesystem_inspector = FilesystemInspector(
            root=configuration.filesystem_root,
            authorized=False,
        )

        self._state = RuntimeState.CREATED
        self._constitution: Constitution | None = None
        self._identity: SofiaIdentity | None = None
        self._personality: PersonalityProfile | None = None
        self._embodiment: Embodiment | None = None
        self._core_state: SofiaCoreState | None = None

        self._runtime_id: UUID | None = None
        self._started_at: datetime | None = None

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
    def runtime_id(self) -> UUID | None:
        return self._runtime_id

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    @property
    def filesystem_inspector(self) -> FilesystemInspector:
        return self._filesystem_inspector

    @property
    def operational_state(self) -> OperationalState | None:
        if (
            self._runtime_id is None
            or self._started_at is None
        ):
            return None

        return OperationalState(
            runtime_id=self._runtime_id,
            started_at=self._started_at,
            lifecycle_state=self._state.value,
            application_name=application_name(),
            application_version=application_version(),
            provider=self._configuration.provider.provider,
            model=self._configuration.provider.model,
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

            self._constitution = constitution
            self._identity = identity
            self._personality = personality
            self._embodiment = embodiment
            self._core_state = core_state
            self._runtime_id = runtime_id
            self._started_at = started_at
            self._filesystem_inspector = FilesystemInspector(
                root=self._configuration.filesystem_root,
                authorized=False,
            )
            self._state = RuntimeState.READY

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
    ):
        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime must be READY before responding."
            )

        if not isinstance(request, CognitiveRequest):
            raise TypeError(
                "SofiaRuntime request must be a CognitiveRequest."
            )

        memories = self._memory_system.recall_relevant(
            self._latest_user_content(request)
        )

        operation = CognitiveOperation(
            context=CognitiveContext(
                request=request,
                identity=self._identity,
                personality=self._personality,
                constitution=self._constitution,
                embodiment=self._embodiment,
                core_state=self._core_state,
                memories=memories,
                operational_state=self.operational_state,
            ),
            authority=Authority(),
        )

        return self._cognitive_system.respond(
            operation
        )

    def enable_filesystem_inspection(self) -> None:
        """
        Enable read-only filesystem inspection for the runtime.

        This method is deliberately separate from general action execution.
        """

        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime must be READY before enabling "
                "filesystem inspection."
            )

        self._filesystem_inspector = FilesystemInspector(
            root=self._configuration.filesystem_root,
            authorized=True,
        )

    def disable_filesystem_inspection(self) -> None:
        """
        Disable filesystem inspection for the runtime.
        """

        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime must be READY before disabling "
                "filesystem inspection."
            )

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