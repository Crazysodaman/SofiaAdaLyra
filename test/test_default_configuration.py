from pathlib import Path

from sofia.config import (
    create_default_configuration,
)
from sofia.config.model import ProviderConfiguration


def test_default_configuration_uses_repository_paths():
    configuration = create_default_configuration()

    assert isinstance(
        configuration,
        object,
    )

    assert Path(
        configuration.constitution_path
    ).name == "constitution.md"

    assert Path(
        configuration.constitution_hash_path
    ).name == "constitution.sha256"

    assert Path(
        configuration.identity_path
    ).name == "identity.json"

    assert Path(
        configuration.personality_path
    ).name == "personality.json"

    assert Path(
        configuration.avatar_path
    ).name == "avatar.json"


def test_default_configuration_uses_ollama():
    configuration = create_default_configuration()

    assert configuration.provider == ProviderConfiguration(
        provider="ollama",
        model="qwen3:14b",
        context_size=20000,
        thinking=False,
    )


def test_default_configuration_creates_state_directory():
    configuration = create_default_configuration()

    state_path = Path(
        configuration.state_path
    )

    assert state_path.parent.is_dir()
    assert state_path.name == "sofia.db"
