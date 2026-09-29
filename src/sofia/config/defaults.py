from pathlib import Path
import os

from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.environment.config import environment_configuration_from_environ
from sofia.config.layout import RuntimeStorageLayout
from sofia.config.user_settings import RuntimeUserSettingsStore


def create_default_configuration(
    *,
    runtime_mode: str | None = None,
) -> SofiaConfiguration:
    """
    Create the standard local configuration for Sofía.

    Paths are resolved relative to the repository root rather than
    the current working directory.
    """

    repository_root = Path(__file__).resolve().parents[3]

    layout = RuntimeStorageLayout.from_environment(
        repository_root,
        mode_override=runtime_mode,
    )
    layout.provision_from_source()

    user_settings = RuntimeUserSettingsStore(
        layout.state_path
    ).load()

    configured_capabilities = tuple(
        value.strip()
        for value in os.environ.get(
            "SOFIA_ALLOWED_CAPABILITIES",
            "",
        ).split(",")
        if value.strip()
    )

    environment_values = user_settings.environment_mapping()
    environment_values.update(
        {
            key: value
            for key, value in os.environ.items()
            if key.startswith("SOFIA_ENVIRONMENT_")
        }
    )
    environment = environment_configuration_from_environ(
        environment_values
    )
    environment_capabilities = tuple(
        capability
        for capability, enabled in (
            ("environment.nws.read", environment.nws_enabled),
            (
                "environment.home_assistant.read",
                environment.home_assistant_enabled,
            ),
        )
        if enabled
    )

    standing_capabilities=tuple(dict.fromkeys((
        "tool.catalog",
        "codebase.inspect",
        "filesystem.changes",
        "process.inspect",
        "system.inspect",
        "network.inspect",
        "service.inspect",
        "hardware.inspect",
        "storage.roots",
        "storage.usage",
        "knowledge.search",
        "knowledge.document",
        "dev.status",
        "machine.list",
        "machine.get",
        "machine.discover.local",
        "ops.fleet.list",
        "ops.fleet.get",
        "ops.telemetry.latest",
        "ops.placement.choose",
        "ops.drift.detect",
        "ops.migration.plan",
        "remote.nodes",
        "remote.process.inspect",
        "remote.system.inspect",
        "remote.network.inspect",
        "remote.service.inspect",
        "remote.hardware.inspect",
        "remote.vm.list",
        "remote.vm.get",
        "remote.container.list",
        "remote.container.get",
        "ollama.models",
        "ollama.running",
        "ollama.model.show",
        "sqlite.state.tables",
        "sqlite.state.query",
        "sqlite.state.integrity",
        *environment_capabilities,
        *configured_capabilities,
    )))

    return SofiaConfiguration(
        constitution_path=layout.constitution_path,
        constitution_hash_path=layout.constitution_hash_path,
        identity_path=layout.identity_path,
        personality_path=layout.personality_path,
        avatar_path=layout.avatar_path,
        state_path=layout.state_path,
        provider=ProviderConfiguration(
            provider="ollama",
            model=user_settings.provider_model,
            context_size=user_settings.provider_context_size,
            thinking=user_settings.provider_thinking,
        ),
        filesystem_root=repository_root,
        identity_bootstrap_mode=layout.identity_bootstrap_mode,
        standing_allowed_capabilities=standing_capabilities,
        environment=environment,
    )


def create_production_configuration() -> SofiaConfiguration:
    """Create the canonical live configuration for Sofía."""
    return create_default_configuration(runtime_mode="production")
