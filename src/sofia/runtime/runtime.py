from sofia.cognition.model import (
    CognitiveRequest,
    CognitiveResponse,
)
from sofia.cognition.system import CognitiveSystem
from sofia.constitution.integrity import ConstitutionIntegrityError
from sofia.constitution.model import Constitution
from sofia.constitution.store import ConstitutionStore
from sofia.identity.model import SofiaIdentity
from sofia.identity.store import IdentityStore
from sofia.runtime.model import RuntimeState
from sofia.memory.system import MemorySystem

class SofiaRuntimeError(Exception):
    """Raised when the Sofia runtime fails to start or operate."""


class SofiaRuntime:
    """
    Owns Sofía's runtime lifecycle and foundational component wiring.
    """

    def __init__(
            self,
            constitution_store: ConstitutionStore,
            integrity_verifier,
            identity_store: IdentityStore,
            memory_system: MemorySystem,
            cognitive_system: CognitiveSystem,
    ):
        self.memory_system = memory_system
        self.constitution_store = constitution_store
        self.integrity_verifier = integrity_verifier
        self.identity_store = identity_store
        self.cognitive_system = cognitive_system

        self.state = RuntimeState.CREATED
        self.constitution: Constitution | None = None
        self.identity: SofiaIdentity | None = None

    def start(self) -> None:
        if self.state is RuntimeState.READY:
            raise SofiaRuntimeError(
                "Sofia runtime is already running."
            )

        self.state = RuntimeState.STARTING
        self.constitution = None
        self.identity = None

        try:
            constitution = self.constitution_store.load()
            self.integrity_verifier.verify(constitution)
            identity = self.identity_store.load()
        except ConstitutionIntegrityError as exc:
            self.state = RuntimeState.FAILED
            raise SofiaRuntimeError(
                "Sofia runtime failed Constitution integrity verification."
            ) from exc
        except Exception as exc:
            self.state = RuntimeState.FAILED
            raise SofiaRuntimeError(
                "Sofia runtime failed during startup."
            ) from exc

        self.constitution = constitution
        self.identity = identity
        self.state = RuntimeState.READY

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        if self.state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "Sofia runtime can only process cognition from READY state."
            )

        return self.cognitive_system.respond(request)

    def shutdown(self) -> None:
        if self.state is not RuntimeState.READY:
            raise SofiaRuntimeError(
                "Sofia runtime can only shut down from READY state."
            )

        self.state = RuntimeState.STOPPED
        self.constitution = None
        self.identity = None