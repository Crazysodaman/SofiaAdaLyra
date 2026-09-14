from pathlib import Path

import pytest
from pathlib import Path
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)


def create_configuration() -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=Path("constitution.md"),
        constitution_hash_path=Path("constitution.sha256"),
        identity_path=Path("identity.json"),
        personality_path=Path("personality.json"),
        avatar_path=Path("avatar.json"),
        state_path=Path("sofia.db"),
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
    )


def test_configuration_stores_constitution_path():
    configuration = create_configuration()

    assert configuration.constitution_path == Path(
        "constitution.md"
    )


def test_configuration_stores_hash_path():
    configuration = create_configuration()

    assert configuration.constitution_hash_path == Path(
        "constitution.sha256"
    )


def test_configuration_stores_identity_path():
    configuration = create_configuration()

    assert configuration.identity_path == Path(
        "identity.json"
    )


def test_configuration_stores_personality_path():
    configuration = create_configuration()

    assert configuration.personality_path == Path(
        "personality.json"
    )


def test_configuration_stores_avatar_path():
    configuration = create_configuration()

    assert configuration.avatar_path == Path(
        "avatar.json"
    )


def test_configuration_stores_state_path():
    configuration = create_configuration()

    assert configuration.state_path == Path(
        "sofia.db"
    )


def test_configuration_paths_are_path_objects():
    configuration = create_configuration()

    assert isinstance(
        configuration.constitution_path,
        Path,
    )

    assert isinstance(
        configuration.constitution_hash_path,
        Path,
    )

    assert isinstance(
        configuration.identity_path,
        Path,
    )

    assert isinstance(
        configuration.personality_path,
        Path,
    )

    assert isinstance(
        configuration.avatar_path,
        Path,
    )

    assert isinstance(
        configuration.state_path,
        Path,
    )


def test_configuration_is_immutable():
    configuration = create_configuration()

    with pytest.raises(AttributeError):
        configuration.identity_path = Path(
            "changed.json"
        )


def test_configuration_does_not_require_files_to_exist():
    configuration = SofiaConfiguration(
        constitution_path=Path(
            "this-file-does-not-exist.md"
        ),
        constitution_hash_path=Path(
            "this-hash-does-not-exist.sha256"
        ),
        identity_path=Path(
            "this-identity-does-not-exist.json"
        ),
        personality_path=Path(
            "this-personality-does-not-exist.json"
        ),
        avatar_path=Path(
            "this-avatar-does-not-exist.json"
        ),
        state_path=Path(
            "this-state-does-not-exist.db"
        ),
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
    )

    assert configuration.constitution_path == Path(
        "this-file-does-not-exist.md"
    )


def test_provider_configuration_stores_provider():
    provider = ProviderConfiguration(
        provider="test",
        model="test-model",
    )

    assert provider.provider == "test"


def test_provider_configuration_stores_model():
    provider = ProviderConfiguration(
        provider="test",
        model="test-model",
    )

    assert provider.model == "test-model"


def test_provider_configuration_rejects_empty_provider():
    with pytest.raises(
        ValueError,
        match="provider must not be empty",
    ):
        ProviderConfiguration(
            provider="",
            model="test-model",
        )


def test_provider_configuration_rejects_empty_model():
    with pytest.raises(
        ValueError,
        match="model must not be empty",
    ):
        ProviderConfiguration(
            provider="test",
            model="",
        )


def test_sofia_configuration_requires_provider_configuration():
    with pytest.raises(
        TypeError,
        match="ProviderConfiguration",
    ):
        SofiaConfiguration(
            constitution_path=Path("constitution.md"),
            constitution_hash_path=Path(
                "constitution.sha256"
            ),
            identity_path=Path("identity.json"),
            personality_path=Path("personality.json"),
            avatar_path=Path("avatar.json"),
            state_path=Path("sofia.db"),
            provider="not-a-provider-configuration",
        )


def test_sofia_configuration_stores_provider_configuration():
    provider = ProviderConfiguration(
        provider="test",
        model="test-model",
    )

    configuration = SofiaConfiguration(
        constitution_path=Path("constitution.md"),
        constitution_hash_path=Path("constitution.sha256"),
        identity_path=Path("identity.json"),
        personality_path=Path("personality.json"),
        avatar_path=Path("avatar.json"),
        state_path=Path("sofia.db"),
        provider=provider,
    )

    assert configuration.provider is provider


def test_configuration_requires_personality_path():
    configuration = SofiaConfiguration(
        constitution_path=Path("constitution.md"),
        constitution_hash_path=Path("constitution.sha256"),
        identity_path=Path("identity.json"),
        personality_path=Path("personality.json"),
        avatar_path=Path("avatar.json"),
        state_path=Path("sofia.db"),
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
    )

    assert configuration.personality_path == Path(
        "personality.json"
    )



def test_configuration_rejects_empty_state_path():
    with pytest.raises(
        ValueError,
        match="state_path must not be empty",
    ):
        SofiaConfiguration(
            constitution_path=Path("constitution.md"),
            constitution_hash_path=Path(
                "constitution.sha256"
            ),
            identity_path=Path("identity.json"),
            personality_path=Path("personality.json"),
            avatar_path=Path("avatar.json"),
            state_path="",
            provider=ProviderConfiguration(
                provider="test",
                model="test-model",
            ),
        )

def test_configuration_rejects_empty_personality_path():
    with pytest.raises(
        ValueError,
        match="personality_path must not be empty",
    ):
        SofiaConfiguration(
            constitution_path=Path("constitution.md"),
            constitution_hash_path=Path("constitution.sha256"),
            identity_path=Path("identity.json"),
            personality_path="",
            avatar_path=Path("avatar.json"),
            state_path=Path("sofia.db"),
            provider=ProviderConfiguration(
                provider="test",
                model="test-model",
            ),
        )


def test_configuration_rejects_empty_avatar_path():
    with pytest.raises(
        ValueError,
        match="avatar_path must not be empty",
    ):
        SofiaConfiguration(
            constitution_path=Path("constitution.md"),
            constitution_hash_path=Path("constitution.sha256"),
            identity_path=Path("identity.json"),
            personality_path=Path("personality.json"),
            avatar_path="",
            state_path=Path("sofia.db"),
            provider=ProviderConfiguration(
                provider="test",
                model="test-model",
            ),
        )

def test_filesystem_root_must_be_path():
    with pytest.raises(TypeError):
        SofiaConfiguration(
            constitution_path=Path("constitution.md"),
            constitution_hash_path=Path("constitution.sha256"),
            identity_path=Path("identity.json"),
            personality_path=Path("personality.json"),
            avatar_path=Path("avatar.json"),
            state_path=Path("sofia.db"),
            provider=ProviderConfiguration(
                provider="ollama",
                model="qwen3:14b",
            ),
            filesystem_root=".",
        )