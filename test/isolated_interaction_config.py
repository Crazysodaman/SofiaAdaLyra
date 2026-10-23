"""Read-only source assets for synthetic interaction probes.

No config bootstrap, user settings load, canonical state creation, external
model installation or production database lookup is performed here.
"""
from pathlib import Path

from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.core.identity.model import IdentityBootstrapMode


def isolated_interaction_configuration(disposable_root: Path) -> SofiaConfiguration:
    checkout = Path(__file__).resolve().parents[1]
    source = checkout / "src" / "sofia"
    return SofiaConfiguration(
        constitution_path=source / "constitution" / "constitution.md",
        constitution_hash_path=source / "constitution" / "constitution.sha256",
        identity_path=source / "identity" / "identity.json",
        personality_path=source / "personality" / "personality.json",
        avatar_path=source / "embodiment" / "avatar.json",
        state_path=disposable_root / "synthetic-interaction-unopened.db",
        provider=ProviderConfiguration(provider="ollama", model="synthetic-offline:fixture"),
        filesystem_root=disposable_root,
        identity_bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
    )
