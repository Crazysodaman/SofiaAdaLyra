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


def test_configuration_is_immutable():
    configuration = create_configuration()

    with pytest.raises(AttributeError):
        configuration.identity_path = Path("other.json")


def test_configuration_does_not_require_files_to_exist():
    configuration = SofiaConfiguration(
        constitution_path=Path("this-file-does-not-exist.md"),
        constitution_hash_path=Path("this-hash-does-not-exist.sha256"),
        identity_path=Path("this-identity-does-not-exist.json"),
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
    )

    assert configuration.constitution_path == Path(
        "this-file-does-not-exist.md"
    )
    assert configuration.constitution_hash_path == Path(
        "this-hash-does-not-exist.sha256"
    )
    assert configuration.identity_path == Path(
        "this-identity-does-not-exist.json"
    )


def test_provider_configuration_stores_provider_and_model():
    provider = ProviderConfiguration(
        provider="test",
        model="test-model",
    )

    assert provider.provider == "test"
    assert provider.model == "test-model"


def test_provider_configuration_is_immutable():
    provider = ProviderConfiguration(
        provider="test",
        model="test-model",
    )

    with pytest.raises(AttributeError):
        provider.provider = "changed"


def test_provider_configuration_requires_provider():
    with pytest.raises(ValueError):
        ProviderConfiguration(
            provider="",
            model="test-model",
        )


def test_provider_configuration_requires_model():
    with pytest.raises(ValueError):
        ProviderConfiguration(
            provider="test",
            model="",
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
        provider=provider,
    )

    assert configuration.provider is provider


def test_sofia_configuration_requires_provider_configuration():
    with pytest.raises(TypeError):
        SofiaConfiguration(
            constitution_path="constitution.md",
            constitution_hash_path="constitution.sha256",
            identity_path="identity.json",
        )