import hashlib
from pathlib import Path

import pytest

from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.providers.test_provider import TestLLMProvider
from sofia.cognition.system import CognitiveSystem
from sofia.composition.root import compose
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.constitution.integrity import ConstitutionIntegrityVerifier
from sofia.constitution.store import ConstitutionStore
from sofia.embodiment.store import AvatarStore
from sofia.memory.system import MemorySystem
from sofia.personality.store import PersonalityStore
from sofia.runtime.model import RuntimeState
from sofia.runtime.runtime import SofiaRuntime


def create_configuration() -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=Path("constitution.md"),
        constitution_hash_path=Path("constitution.sha256"),
        identity_path=Path("identity.json"),
        personality_path=Path("personality.json"),
        avatar_path=Path("avatar.json"),
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
    )


def test_composition_creates_runtime():
    configuration = create_configuration()

    runtime = compose(configuration)

    assert isinstance(runtime, SofiaRuntime)


def test_composition_does_not_start_runtime():
    configuration = create_configuration()

    runtime = compose(configuration)

    assert runtime.state is RuntimeState.CREATED


def test_composition_wires_constitution_store():
    configuration = create_configuration()

    runtime = compose(configuration)

    assert isinstance(
        runtime.constitution_store,
        ConstitutionStore,
    )

    assert (
        runtime.constitution_store.constitution_path
        == configuration.constitution_path
    )


def test_composition_wires_integrity_verifier():
    configuration = create_configuration()

    runtime = compose(configuration)

    assert isinstance(
        runtime.integrity_verifier,
        ConstitutionIntegrityVerifier,
    )

    assert (
        runtime.integrity_verifier.expected_hash_path
        == configuration.constitution_hash_path
    )


def test_composition_wires_personality_store():
    configuration = create_configuration()

    runtime = compose(configuration)

    assert isinstance(
        runtime.personality_store,
        PersonalityStore,
    )

    assert (
        runtime.personality_store._path
        == configuration.personality_path
    )


def test_composition_wires_avatar_store():
    configuration = create_configuration()

    runtime = compose(configuration)

    assert isinstance(
        runtime.avatar_store,
        AvatarStore,
    )

    assert (
        runtime.avatar_store.path
        == configuration.avatar_path
    )


def test_compose_creates_cognitive_system():
    from sofia.cognition.test_engine import TestCognitiveEngine

    configuration = create_configuration()

    runtime = compose(configuration)

    assert isinstance(
        runtime.cognitive_system,
        CognitiveSystem,
    )

    assert isinstance(
        runtime.cognitive_system.engine,
        TestCognitiveEngine,
    )


def test_composition_creates_runtime_with_configured_cognitive_engine(
    tmp_path,
):
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
    )

    configuration.constitution_path.write_text(
        "# Constitution\n",
        encoding="utf-8",
    )

    constitution_hash = hashlib.sha256(
        configuration.constitution_path.read_bytes()
    ).hexdigest().upper()

    configuration.constitution_hash_path.write_text(
        constitution_hash,
        encoding="utf-8",
    )

    configuration.identity_path.write_text(
        '{"name": "Sofía Ada Lyra"}',
        encoding="utf-8",
    )

    configuration.personality_path.write_text(
        (
            '{"name": "Sofía Ada Lyra", '
            '"traits": ["rigorous"], '
            '"communication_style": "direct"}'
        ),
        encoding="utf-8",
    )

    configuration.avatar_path.write_text(
        (
            '{"subject": "Sofía Ada Lyra", '
            '"physical_self": {'
            '"form": "human", '
            '"additional_features": [], '
            '"measurements": {}, '
            '"appearance": {}, '
            '"anatomy": {}'
            '}, '
            '"available": {'
            '"computers": [], '
            '"robots": [], '
            '"avatars": []'
            '}, '
            '"current": {'
            '"computer": null, '
            '"robot": null, '
            '"avatar": null'
            '}}'
        ),
        encoding="utf-8",
    )

    runtime = compose(configuration)

    assert isinstance(
        runtime.cognitive_system,
        CognitiveSystem,
    )

    assert isinstance(
        runtime.cognitive_system.engine,
        CognitiveEngine,
    )


def test_composition_selects_configured_rule_provider(
    tmp_path,
):
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        provider=ProviderConfiguration(
            provider="rule",
            model="rule-engine",
        ),
    )

    runtime = compose(configuration)

    from sofia.cognition.rules import RuleEngine

    assert isinstance(
        runtime.cognitive_system.engine,
        RuleEngine,
    )


def test_composition_rejects_unknown_provider(
    tmp_path,
):
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        provider=ProviderConfiguration(
            provider="unknown-provider",
            model="unknown-model",
        ),
    )

    with pytest.raises(
        ValueError,
        match="Unknown cognitive provider",
    ):
        compose(configuration)


def test_composition_selects_test_provider_engine(
    tmp_path,
):
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
    )

    runtime = compose(configuration)

    from sofia.cognition.test_engine import TestCognitiveEngine

    assert isinstance(
        runtime.cognitive_system.engine,
        TestCognitiveEngine,
    )


def test_composition_passes_provider_configuration_to_test_engine():
    from sofia.cognition.test_engine import TestCognitiveEngine

    configuration = create_configuration()

    runtime = compose(configuration)

    engine = runtime.cognitive_system.engine

    assert isinstance(
        engine,
        TestCognitiveEngine,
    )

    assert engine.configuration is configuration.provider


def test_composition_creates_memory_system():
    configuration = create_configuration()

    runtime = compose(configuration)

    assert isinstance(
        runtime.memory_system,
        MemorySystem,
    )


def test_composition_creates_llm_cognitive_engine():
    configuration = SofiaConfiguration(
        constitution_path="constitution.md",
        constitution_hash_path="constitution.sha256",
        identity_path="identity.json",
        personality_path="personality.json",
        avatar_path="avatar.json",
        provider=ProviderConfiguration(
            provider="test-llm",
            model="test-model",
        ),
    )

    runtime = compose(configuration)

    assert isinstance(
        runtime.cognitive_system.engine,
        LLMCognitiveEngine,
    )


def test_composition_creates_test_llm_provider():
    configuration = SofiaConfiguration(
        constitution_path="constitution.md",
        constitution_hash_path="constitution.sha256",
        identity_path="identity.json",
        personality_path="personality.json",
        avatar_path="avatar.json",
        provider=ProviderConfiguration(
            provider="test-llm",
            model="test-model",
        ),
    )

    runtime = compose(configuration)

    engine = runtime.cognitive_system.engine

    assert isinstance(
        engine.provider,
        TestLLMProvider,
    )


def test_composition_passes_provider_configuration_to_llm_engine():
    configuration = SofiaConfiguration(
        constitution_path="constitution.md",
        constitution_hash_path="constitution.sha256",
        identity_path="identity.json",
        personality_path="personality.json",
        avatar_path="avatar.json",
        provider=ProviderConfiguration(
            provider="test-llm",
            model="test-model",
        ),
    )

    runtime = compose(configuration)

    engine = runtime.cognitive_system.engine

    assert engine.configuration is configuration.provider