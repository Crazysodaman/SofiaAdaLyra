from sofia.cognition.rules import RuleEngine
from sofia.cognition.system import CognitiveSystem
from sofia.cognition.test_engine import TestCognitiveEngine
from sofia.config.model import SofiaConfiguration
from sofia.constitution.integrity import ConstitutionIntegrityVerifier
from sofia.constitution.store import ConstitutionStore
from sofia.identity.store import IdentityStore
from sofia.runtime.runtime import SofiaRuntime


def _create_cognitive_engine(configuration: SofiaConfiguration):
    """
    Construct the configured cognitive engine.
    """

    if configuration.provider.provider == "test":
        return TestCognitiveEngine(
            configuration=configuration.provider,
        )

    if configuration.provider.provider == "rule":
        return RuleEngine()

    raise ValueError(
        f"Unknown cognitive provider: "
        f"{configuration.provider.provider}"
    )


def compose(configuration: SofiaConfiguration) -> SofiaRuntime:
    """
    Construct Sofía's foundational runtime dependencies.
    """

    constitution_store = ConstitutionStore(
        configuration.constitution_path
    )

    integrity_verifier = ConstitutionIntegrityVerifier(
        configuration.constitution_hash_path
    )

    identity_store = IdentityStore(
        configuration.identity_path
    )

    cognitive_engine = _create_cognitive_engine(
        configuration
    )

    cognitive_system = CognitiveSystem(
        engine=cognitive_engine,
    )

    return SofiaRuntime(
        constitution_store=constitution_store,
        integrity_verifier=integrity_verifier,
        identity_store=identity_store,
        cognitive_system=cognitive_system,
    )