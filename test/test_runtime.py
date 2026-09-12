from pathlib import Path

import pytest

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.rules import RuleEngine
from sofia.cognition.system import CognitiveSystem
from sofia.constitution.integrity import (
    ConstitutionIntegrityError,
    ConstitutionIntegrityVerifier,
)
from sofia.constitution.store import ConstitutionStore
from sofia.identity.model import SofiaIdentity
from sofia.identity.store import IdentityStore
from sofia.memory.store import MemoryStore
from sofia.memory.system import MemorySystem
from sofia.personality.store import PersonalityStore
from sofia.runtime.model import RuntimeState
from sofia.runtime.runtime import SofiaRuntime, SofiaRuntimeError


CONSTITUTION_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

HASH_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)

IDENTITY_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "identity"
    / "identity.json"
)

PERSONALITY_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "personality"
    / "personality.json"
)


def create_runtime(
    identity_path: Path = IDENTITY_PATH,
) -> SofiaRuntime:
    store = ConstitutionStore(CONSTITUTION_PATH)

    verifier = ConstitutionIntegrityVerifier(HASH_PATH)

    identity_store = IdentityStore(identity_path)

    personality_store = PersonalityStore(
        PERSONALITY_PATH,
    )

    memory_store = MemoryStore()

    memory_system = MemorySystem(
        memory_store,
    )

    cognitive_system = CognitiveSystem(
        engine=RuleEngine(),
    )

    return SofiaRuntime(
        constitution_store=store,
        integrity_verifier=verifier,
        identity_store=identity_store,
        personality_store=personality_store,
        memory_system=memory_system,
        cognitive_system=cognitive_system,
    )


def test_new_runtime_starts_created():
    runtime = create_runtime()

    assert runtime.state is RuntimeState.CREATED


def test_start_with_valid_constitution_reaches_ready():
    runtime = create_runtime()

    runtime.start()

    assert runtime.state is RuntimeState.READY
    assert runtime.constitution is not None


def test_start_with_invalid_constitution_fails(tmp_path: Path):
    store = ConstitutionStore(CONSTITUTION_PATH)

    identity_store = IdentityStore(
        tmp_path / "identity.json",
    )

    personality_store = PersonalityStore(
        PERSONALITY_PATH,
    )

    class FailingVerifier:
        def verify(self, constitution):
            raise ConstitutionIntegrityError(
                "Constitution integrity verification failed."
            )

    memory_store = MemoryStore()

    memory_system = MemorySystem(
        memory_store,
    )

    cognitive_system = CognitiveSystem(
        engine=RuleEngine(),
    )

    runtime = SofiaRuntime(
        constitution_store=store,
        integrity_verifier=FailingVerifier(),
        identity_store=identity_store,
        personality_store=personality_store,
        memory_system=memory_system,
        cognitive_system=cognitive_system,
    )

    with pytest.raises(SofiaRuntimeError) as exc_info:
        runtime.start()

    assert runtime.state is RuntimeState.FAILED
    assert isinstance(
        exc_info.value.__cause__,
        ConstitutionIntegrityError,
    )
    assert runtime.constitution is None


def test_shutdown_from_ready_reaches_stopped():
    runtime = create_runtime()

    runtime.start()
    runtime.shutdown()

    assert runtime.state is RuntimeState.STOPPED


def test_restart_from_stopped_performs_fresh_start():
    runtime = create_runtime()

    runtime.start()
    runtime.shutdown()
    runtime.start()

    assert runtime.state is RuntimeState.READY
    assert runtime.constitution is not None


def test_start_while_ready_is_rejected():
    runtime = create_runtime()

    runtime.start()

    with pytest.raises(SofiaRuntimeError):
        runtime.start()

    assert runtime.state is RuntimeState.READY


def test_shutdown_from_created_is_rejected():
    runtime = create_runtime()

    with pytest.raises(SofiaRuntimeError):
        runtime.shutdown()

    assert runtime.state is RuntimeState.CREATED


def test_shutdown_from_failed_is_rejected(tmp_path: Path):
    store = ConstitutionStore(CONSTITUTION_PATH)

    identity_store = IdentityStore(
        tmp_path / "identity.json",
    )

    personality_store = PersonalityStore(
        PERSONALITY_PATH,
    )

    class FailingVerifier:
        def verify(self, constitution):
            raise ConstitutionIntegrityError(
                "Constitution integrity verification failed."
            )

    memory_store = MemoryStore()

    memory_system = MemorySystem(
        memory_store,
    )

    cognitive_system = CognitiveSystem(
        engine=RuleEngine(),
    )

    runtime = SofiaRuntime(
        constitution_store=store,
        integrity_verifier=FailingVerifier(),
        identity_store=identity_store,
        personality_store=personality_store,
        memory_system=memory_system,
        cognitive_system=cognitive_system,
    )

    with pytest.raises(SofiaRuntimeError):
        runtime.start()

    with pytest.raises(SofiaRuntimeError):
        runtime.shutdown()

    assert runtime.state is RuntimeState.FAILED


def test_shutdown_while_stopped_is_rejected():
    runtime = create_runtime()

    runtime.start()
    runtime.shutdown()

    with pytest.raises(SofiaRuntimeError):
        runtime.shutdown()

    assert runtime.state is RuntimeState.STOPPED


def test_failed_restart_clears_previous_constitution():
    runtime = create_runtime()

    runtime.start()

    assert runtime.constitution is not None

    runtime.shutdown()

    class FailingVerifier:
        def verify(self, constitution):
            raise ConstitutionIntegrityError(
                "Constitution integrity verification failed."
            )

    runtime.integrity_verifier = FailingVerifier()

    with pytest.raises(SofiaRuntimeError):
        runtime.start()

    assert runtime.state is RuntimeState.FAILED
    assert runtime.constitution is None


def test_runtime_identity_is_none_before_start(tmp_path: Path):
    runtime = create_runtime(
        tmp_path / "identity.json",
    )

    assert runtime.identity is None


def test_runtime_loads_identity_on_start(tmp_path: Path):
    identity_path = tmp_path / "identity.json"

    identity_store = IdentityStore(identity_path)

    identity_store.save(
        SofiaIdentity(
            name="Nyx",
        )
    )

    runtime = create_runtime(identity_path)

    runtime.start()

    assert runtime.identity == SofiaIdentity(
        name="Nyx",
    )


def test_runtime_clears_identity_on_shutdown(tmp_path: Path):
    identity_path = tmp_path / "identity.json"

    identity_store = IdentityStore(identity_path)

    identity_store.save(
        SofiaIdentity(
            name="Nyx",
        )
    )

    runtime = create_runtime(identity_path)

    runtime.start()

    assert runtime.identity.name == "Nyx"

    runtime.shutdown()

    assert runtime.identity is None


def test_runtime_reload_identity_on_restart(tmp_path: Path):
    identity_path = tmp_path / "identity.json"

    identity_store = IdentityStore(identity_path)

    identity_store.save(
        SofiaIdentity(
            name="Nyx",
        )
    )

    runtime = create_runtime(identity_path)

    runtime.start()
    runtime.shutdown()

    identity_store.save(
        SofiaIdentity(
            name="Sofía Ada Lyra",
        )
    )

    runtime.start()

    assert runtime.identity == SofiaIdentity(
        name="Sofía Ada Lyra",
    )


def test_ready_runtime_can_process_cognitive_request():
    runtime = create_runtime()

    runtime.start()

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
        ),
    )

    response = runtime.respond(request)

    assert response == CognitiveResponse(
        content="Hello, Sparks.",
    )


def test_runtime_cannot_process_cognitive_request_before_start():
    runtime = create_runtime()

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
        ),
    )

    with pytest.raises(SofiaRuntimeError):
        runtime.respond(request)