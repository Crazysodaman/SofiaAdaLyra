from sofia.authority.model import Authority
from sofia.cognition.context import CognitiveContext
from sofia.cognition.operation import CognitiveOperation
from sofia.cognition.model import CognitiveRequest
from sofia.cognition.system import CognitiveSystem
from sofia.constitution.integrity import (
    ConstitutionIntegrityError,
    ConstitutionIntegrityVerifier,
)
from sofia.constitution.model import Constitution
from sofia.constitution.store import ConstitutionStore
from sofia.identity.model import SofiaIdentity
from sofia.identity.store import IdentityStore
from sofia.memory.system import MemorySystem
from sofia.personality.store import PersonalityStore
from sofia.runtime.model import RuntimeState


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
        memory_system: MemorySystem,
        cognitive_system: CognitiveSystem,
    ) -> None:
        self._constitution_store = constitution_store
        self._integrity_verifier = integrity_verifier
        self._identity_store = identity_store
        self._personality_store = personality_store
        self._memory_system = memory_system
        self._cognitive_system = cognitive_system

        self._state = RuntimeState.CREATED
        self._constitution: Constitution | None = None
        self._identity: SofiaIdentity | None = None

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
    def integrity_verifier(self) -> ConstitutionIntegrityVerifier:
        return self._integrity_verifier

    @integrity_verifier.setter
    def integrity_verifier(self, verifier) -> None:
        self._integrity_verifier = verifier

    @property
    def identity(self) -> SofiaIdentity | None:
        return self._identity

    @property
    def identity_store(self) -> IdentityStore:
        return self._identity_store

    @property
    def personality_store(self) -> PersonalityStore:
        return self._personality_store

    @property
    def memory_system(self) -> MemorySystem:
        return self._memory_system

    @property
    def cognitive_system(self) -> CognitiveSystem:
        return self._cognitive_system

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
            constitution = self._constitution_store.load()

            self._integrity_verifier.verify(
                constitution
            )

            identity = self._identity_store.load()

            self._constitution = constitution
            self._identity = identity
            self._state = RuntimeState.READY

        except ConstitutionIntegrityError as exc:
            self._constitution = None
            self._identity = None
            self._state = RuntimeState.FAILED

            raise SofiaRuntimeError(
                "Sofía Constitution integrity verification failed."
            ) from exc

        except Exception as exc:
            self._constitution = None
            self._identity = None
            self._state = RuntimeState.FAILED

            raise SofiaRuntimeError(
                "Sofía runtime failed during startup."
            ) from exc

    def respond(self, request: CognitiveRequest):
        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime must be READY before responding."
            )

        if not isinstance(request, CognitiveRequest):
            raise TypeError(
                "SofiaRuntime request must be a CognitiveRequest."
            )

        operation = CognitiveOperation(
            context=CognitiveContext(
                request=request,
                identity=self._identity,
                constitution=self._constitution,
            ),
            authority=Authority(),
        )

        return self._cognitive_system.respond(operation)

    def shutdown(self) -> None:
        if self._state is RuntimeState.STOPPED:
            raise SofiaRuntimeError(
                "SofiaRuntime is already stopped."
            )

        if self._state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "SofiaRuntime can only shut down from the READY state."
            )

        self._constitution = None
        self._identity = None
        self._state = RuntimeState.STOPPED