from pathlib import Path

from sofia.application.conversation_service import ConversationService
from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.providers.factory import create_llm_provider
from sofia.cognition.rules import RuleEngine
from sofia.cognition.system import CognitiveSystem
from sofia.cognition.test_engine import TestCognitiveEngine
from sofia.config.model import SofiaConfiguration
from sofia.constitution.integrity import ConstitutionIntegrityVerifier
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.store import AvatarStore
from sofia.identity.store import IdentityStore
from sofia.memory.store import MemoryStore
from sofia.memory.system import MemorySystem
from sofia.personality.store import PersonalityStore
from sofia.conversation.store import ConversationStore
from sofia.runtime.runtime import SofiaRuntime


def _create_cognitive_engine(configuration: SofiaConfiguration):
    if configuration.provider.provider == "test":
        return TestCognitiveEngine(configuration=configuration.provider)

    if configuration.provider.provider == "rule":
        return RuleEngine()

    if configuration.provider.provider == "test-llm":
        provider = create_llm_provider(configuration.provider)
        return LLMCognitiveEngine(
            configuration=configuration.provider,
            provider=provider,
        )

    if configuration.provider.provider == "ollama":
        provider = create_llm_provider(configuration.provider)
        return LLMCognitiveEngine(
            configuration=configuration.provider,
            provider=provider,
        )

    raise ValueError(
        f"Unknown cognitive provider: "
        f"{configuration.provider.provider}"
    )


def compose(configuration: SofiaConfiguration) -> SofiaRuntime:
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

    cognitive_engine = _create_cognitive_engine(
        configuration
    )

    cognitive_system = CognitiveSystem(
        engine=cognitive_engine
    )

    memory_store = MemoryStore(
        configuration.state_path
    )

    memory_system = MemorySystem(
        memory_store
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


def compose_conversation_service(
    configuration: SofiaConfiguration,
    runtime: SofiaRuntime,
) -> ConversationService:
    conversation_store = ConversationStore(
        configuration.state_path
    )

    return ConversationService(
        runtime=runtime,
        conversation_store=conversation_store,
    )