from datetime import datetime
from pathlib import Path

import pytest

from sofia.authority.model import Authority
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.operation import CognitiveOperation
from sofia.cognition.rules import RuleEngine
from sofia.cognition.system import CognitiveSystem
from sofia.config.model import ProviderConfiguration
from sofia.constitution.integrity import (
    ConstitutionIntegrityError,
    ConstitutionIntegrityVerifier,
)
from sofia.constitution.model import Constitution
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.model import (
    Embodiment,
    PhysicalSelf,
    CurrentEmbodiment,
)
from sofia.embodiment.store import AvatarStore
from sofia.identity.model import SofiaIdentity
from sofia.identity.store import IdentityStore
from sofia.memory.model import MemoryRecord
from sofia.memory.store import MemoryStore
from sofia.memory.system import MemorySystem
from sofia.personality.model import PersonalityProfile
from sofia.personality.store import PersonalityStore
from sofia.runtime.model import RuntimeState
from sofia.runtime.runtime import (
    SofiaRuntime,
    SofiaRuntimeError,
)


def create_runtime(
    identity_path: Path | None = None,
) -> SofiaRuntime:
    constitution_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "sofia"
        / "constitution"
        / "constitution.md"
    )

    constitution_hash_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "sofia"
        / "constitution"
        / "constitution.sha256"
    )

    if identity_path is None:
        identity_path = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "sofia"
            / "identity"
            / "identity.json"
        )

    personality_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "sofia"
        / "personality"
        / "personality.json"
    )

    avatar_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "sofia"
        / "data"
        / "avatar.json"
    )

    constitution_store = ConstitutionStore(
        constitution_path
    )

    integrity_verifier = ConstitutionIntegrityVerifier(
        constitution_hash_path
    )

    identity_store = IdentityStore(
        identity_path
    )

    personality_store = PersonalityStore(
        personality_path
    )

    avatar_store = AvatarStore(
        avatar_path
    )

    memory_store = MemoryStore()

    memory_system = MemorySystem(
        memory_store
    )

    cognitive_system = CognitiveSystem(
        engine=RuleEngine(),
    )

    return SofiaRuntime(
        constitution_store=constitution_store,
        integrity_verifier=integrity_verifier,
        identity_store=identity_store,
        personality_store=personality_store,
        avatar_store=avatar_store,
        memory_system=memory_system,
        cognitive_system=cognitive_system,
    )


def test_runtime_initial_state():
    runtime = create_runtime()

    assert runtime.state is RuntimeState.CREATED
    assert runtime.constitution is None
    assert runtime.identity is None
    assert runtime.personality is None
    assert runtime.embodiment is None


def test_runtime_start_loads_foundational_state():
    runtime = create_runtime()

    runtime.start()

    assert runtime.state is RuntimeState.READY
    assert runtime.constitution is not None
    assert runtime.identity is not None
    assert runtime.personality is not None
    assert runtime.embodiment is not None


def test_runtime_start_is_only_valid_from_created_or_stopped():
    runtime = create_runtime()

    runtime.start()

    with pytest.raises(SofiaRuntimeError):
        runtime.start()


def test_runtime_shutdown():
    runtime = create_runtime()

    runtime.start()
    runtime.shutdown()

    assert runtime.state is RuntimeState.STOPPED
    assert runtime.constitution is None
    assert runtime.identity is None
    assert runtime.personality is None
    assert runtime.embodiment is None


def test_runtime_shutdown_requires_ready_state():
    runtime = create_runtime()

    with pytest.raises(SofiaRuntimeError):
        runtime.shutdown()


def test_runtime_shutdown_cannot_be_called_twice():
    runtime = create_runtime()

    runtime.start()
    runtime.shutdown()

    with pytest.raises(SofiaRuntimeError):
        runtime.shutdown()


def test_runtime_can_restart_after_shutdown():
    runtime = create_runtime()

    runtime.start()
    runtime.shutdown()
    runtime.start()

    assert runtime.state is RuntimeState.READY
    assert runtime.constitution is not None
    assert runtime.identity is not None
    assert runtime.personality is not None
    assert runtime.embodiment is not None


def test_runtime_detects_constitution_integrity_failure():
    runtime = create_runtime()

    class FailingVerifier:
        def verify(self, constitution):
            raise ConstitutionIntegrityError(
                "Integrity failure."
            )

    runtime.integrity_verifier = FailingVerifier()

    with pytest.raises(SofiaRuntimeError):
        runtime.start()

    assert runtime.state is RuntimeState.FAILED
    assert runtime.constitution is None
    assert runtime.identity is None
    assert runtime.personality is None
    assert runtime.embodiment is None


def test_runtime_clears_state_when_startup_fails():
    runtime = create_runtime()

    class FailingIdentityStore:
        def load(self):
            raise RuntimeError(
                "Identity load failed."
            )

    runtime._identity_store = FailingIdentityStore()

    with pytest.raises(SofiaRuntimeError):
        runtime.start()

    assert runtime.state is RuntimeState.FAILED
    assert runtime.constitution is None
    assert runtime.identity is None
    assert runtime.personality is None
    assert runtime.embodiment is None


def test_runtime_exposes_foundational_subsystems():
    runtime = create_runtime()

    assert isinstance(
        runtime.constitution_store,
        ConstitutionStore,
    )

    assert isinstance(
        runtime.identity_store,
        IdentityStore,
    )

    assert isinstance(
        runtime.personality_store,
        PersonalityStore,
    )

    assert isinstance(
        runtime.avatar_store,
        AvatarStore,
    )

    assert isinstance(
        runtime.memory_system,
        MemorySystem,
    )

    assert isinstance(
        runtime.cognitive_system,
        CognitiveSystem,
    )


def test_runtime_loads_identity_on_start(tmp_path: Path):
    identity_path = tmp_path / "identity.json"

    identity_store = IdentityStore(
        identity_path
    )

    saved_identity = SofiaIdentity(
        name="Nyx",
    )

    identity_store.save(
        saved_identity
    )

    runtime = create_runtime(
        identity_path
    )

    runtime.start()

    assert runtime.identity is not None
    assert runtime.identity.name == "Nyx"
    assert (
        runtime.identity.instance_id
        == saved_identity.instance_id
    )


def test_runtime_clears_identity_on_shutdown(tmp_path: Path):
    identity_path = tmp_path / "identity.json"

    identity_store = IdentityStore(
        identity_path
    )

    identity_store.save(
        SofiaIdentity(
            name="Nyx",
        )
    )

    runtime = create_runtime(
        identity_path
    )

    runtime.start()

    assert runtime.identity is not None

    runtime.shutdown()

    assert runtime.identity is None


def test_runtime_reload_identity_on_restart(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"

    identity_store = IdentityStore(
        identity_path
    )

    first_identity = SofiaIdentity(
        name="Nyx",
    )

    identity_store.save(
        first_identity
    )

    runtime = create_runtime(
        identity_path
    )

    runtime.start()

    assert runtime.identity is not None
    assert runtime.identity.name == "Nyx"
    assert (
        runtime.identity.instance_id
        == first_identity.instance_id
    )

    runtime.shutdown()

    second_identity = SofiaIdentity(
        name="Sofía Ada Lyra",
        instance_id=first_identity.instance_id,
    )

    identity_store.save(
        second_identity
    )

    runtime.start()

    assert runtime.identity is not None
    assert runtime.identity.name == "Sofía Ada Lyra"
    assert (
        runtime.identity.instance_id
        == first_identity.instance_id
    )


def test_runtime_respond_requires_ready_state():
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


def test_runtime_respond_requires_cognitive_request():
    runtime = create_runtime()

    runtime.start()

    with pytest.raises(TypeError):
        runtime.respond("Hello, Sofía.")


def test_runtime_responds_through_cognitive_system():
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

    response = runtime.respond(
        request
    )

    assert isinstance(
        response,
        CognitiveResponse,
    )

    assert response.content == "Hello, Sparks."


def test_runtime_injects_identity_into_cognition():
    runtime = create_runtime()

    runtime.start()

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="What is your name?",
            ),
        ),
    )

    response = runtime.respond(
        request
    )

    assert response.content == "I am Sofía Ada Lyra."


def test_runtime_retrieves_relevant_memory_before_cognition():
    runtime = create_runtime()

    memory = MemoryRecord(
        id="memory-1",
        content=(
            "Sparks prefers architecture-first development."
        ),
        created_at=datetime.now(),
    )

    runtime.memory_system.remember(
        memory
    )

    runtime.start()

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content=(
                    "What does Sparks prefer about development?"
                ),
            ),
        ),
    )

    relevant = (
        runtime.memory_system.recall_relevant(
            request.messages[-1].content
        )
    )

    assert relevant == (
        memory,
    )