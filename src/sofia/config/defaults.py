from pathlib import Path

from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)


def create_default_configuration() -> SofiaConfiguration:
    """
    Create the standard local configuration for Sofía.

    Paths are resolved relative to the repository root rather than
    the current working directory.
    """

    repository_root = Path(__file__).resolve().parents[3]

    state_directory = repository_root / "state"
    state_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return SofiaConfiguration(
        constitution_path=(
            repository_root
            / "src"
            / "sofia"
            / "constitution"
            / "constitution.md"
        ),
        constitution_hash_path=(
            repository_root
            / "src"
            / "sofia"
            / "constitution"
            / "constitution.sha256"
        ),
        identity_path=(
            repository_root
            / "src"
            / "sofia"
            / "identity"
            / "identity.json"
        ),
        personality_path=(
            repository_root
            / "src"
            / "sofia"
            / "personality"
            / "personality.json"
        ),
        avatar_path=(
            repository_root
            / "src"
            / "sofia"
            / "data"
            / "avatar.json"
        ),
        state_path=(
            state_directory
            / "sofia.db"
        ),
        provider=ProviderConfiguration(
            provider="ollama",
            model="qwen3:14b",
        ),
        filesystem_root=repository_root,
    )