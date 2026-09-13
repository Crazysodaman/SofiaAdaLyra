from pathlib import Path

from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.providers.factory import create_llm_provider
from sofia.cognition.rules import RuleEngine
from sofia.cognition.system import CognitiveSystem
from sofia.cognition.test_engine import TestCognitiveEngine
from sofia.config.model import SofiaConfiguration
from sofia.constitution.integrity import ConstitutionIntegrityVerifier
from sofia.constitution.store import ConstitutionStore
from sofia.identity.store import IdentityStore
from sofia.memory.store import MemoryStore
from sofia.memory.system import MemorySystem
from sofia.personality.store import PersonalityStore
from sofia.runtime.runtime import SofiaRuntime


def _create_cognitive_engine(
    configuration: SofiaConfiguration,
):
    """
    Construct the configured cognitive engine.
    """

    if configuration.provider.provider == "test":
        return TestCognitiveEngine(
            configuration=configuration.provider,
        )

    if configuration.provider.provider == "rule":
        return RuleEngine()

    if configuration.provider.provider == "test-llm":
        provider = create_llm_provider(
            configuration.provider,
        )

        return LLMCognitiveEngine(
            configuration=configuration.provider,
            provider=provider,
        )

    if configuration.provider.provider == "ollama":
        provider = create_llm_provider(
            configuration.provider,
        )

        return LLMCognitiveEngine(
            configuration=configuration.provider,
            provider=provider,
        )

    raise ValueError(
        f"Unknown cognitive provider: "
        f"{configuration.provider.provider}"
    )


def compose(
    configuration: SofiaConfiguration,
) -> SofiaRuntime:
    """
    Construct Sofía's foundational runtime dependencies.

    Configuration owns external representation.
    Composition converts that representation into
    the concrete dependency types required by the system.
    """

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

    cognitive_engine = _create_cognitive_engine(
        configuration
    )

    cognitive_system = CognitiveSystem(
        engine=cognitive_engine,
    )

    memory_store = MemoryStore()

    memory_system = MemorySystem(
        memory_store,
    )

    return SofiaRuntime(
        constitution_store=constitution_store,
        integrity_verifier=integrity_verifier,
        identity_store=identity_store,
        personality_store=personality_store,
        memory_system=memory_system,
        cognitive_system=cognitive_system,
    )