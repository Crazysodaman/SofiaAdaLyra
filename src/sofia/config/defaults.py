from pathlib import Path
import os

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

    extra_capabilities=tuple(
        part.strip()
        for part in os.environ.get("SOFIA_ALLOWED_CAPABILITIES","").split(",")
        if part.strip()
    )
    standing_capabilities=tuple(dict.fromkeys((
        "tool.catalog",
        "codebase.inspect",
        "process.inspect",
        "system.inspect",
        "network.inspect",
        "service.inspect",
        "hardware.inspect",
        "storage.usage",
        "knowledge.search",
        "knowledge.document",
        "dev.status",
        *extra_capabilities,
    )))

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
            # Preserve the current context until we test full-runtime requirements.
            context_size=20000,
            thinking=False,
        ),
        filesystem_root=repository_root,
        standing_allowed_capabilities=standing_capabilities,
    )