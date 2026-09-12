from pathlib import Path

import pytest

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
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
    )


def test_configuration_stores_constitution_path():
    configuration = create_configuration()

    assert configuration.constitution_path == Path("constitution.md")


def test_configuration_stores_hash_path():
    configuration = create_configuration()

    assert configuration.constitution_hash_path == Path(
        "constitution.sha256"
    )


def test_configuration_stores_identity_path():
    configuration = create_configuration()

    assert configuration.identity_path == Path("identity.json")


def test_configuration_paths_are_path_objects():
    configuration = create_configuration()

    assert isinstance(configuration.constitution_path, Path)
    assert isinstance(configuration.constitution_hash_path, Path)
    assert isinstance(configuration.identity_path, Path)
    assert isinstance(configuration.personality_path, Path)


def test_configuration_is_immutable():
    configuration = create_configuration()

    with pytest.raises(AttributeError):
        configuration.identity_path = Path("changed.json")


def test_configuration_does_not_require_files_to_exist():
    configuration = SofiaConfiguration(
        constitution_path=Path("this-file-does-not-exist.md"),
        constitution_hash_path=Path("this-hash-does-not-exist.sha256"),
        identity_path=Path("this-identity-does-not-exist.json"),
        personality_path=Path("this-personality-does-not-exist.json"),
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
            constitution_hash_path=Path("constitution.sha256"),
            identity_path=Path("identity.json"),
            personality_path=Path("personality.json"),
            provider="not-a-provider-configuration",
        )


def test_sofia_configuration_stores_provider_configuration():
    provider = ProviderConfiguration(
        provider="test",
        model="test-model",
    )

    configuration = SofiaConfiguration(
        constitution_path="constitution.md",
        constitution_hash_path="constitution.sha256",
        identity_path="identity.json",
        personality_path="personality.json",
        provider=provider,
    )

    assert configuration.provider is provider


def test_configuration_requires_personality_path():
    configuration = SofiaConfiguration(
        constitution_path="constitution.md",
        constitution_hash_path="constitution.sha256",
        identity_path="identity.json",
        personality_path="personality.json",
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
    )

    assert configuration.personality_path == "personality.json"


def test_configuration_rejects_empty_personality_path():
    with pytest.raises(
        ValueError,
        match="personality_path must not be empty",
    ):
        SofiaConfiguration(
            constitution_path="constitution.md",
            constitution_hash_path="constitution.sha256",
            identity_path="identity.json",
            personality_path="",
            provider=ProviderConfiguration(
                provider="test",
                model="test-model",
            ),
        )