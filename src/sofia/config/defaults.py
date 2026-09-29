from dataclasses import replace
from pathlib import Path
import os

from sofia.config.model import (
    CognitiveRoutingConfiguration,
    ModelLifecycleConfiguration,
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.environment.config import environment_configuration_from_environ
from sofia.config.layout import RuntimeStorageLayout
from sofia.config.user_settings import RuntimeUserSettingsStore


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _environment_flag(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean flag")


def _positive_environment_int(name: str, *, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _routing_configuration_from_environ(
    base: ProviderConfiguration,
    user_settings,
) -> CognitiveRoutingConfiguration | None:
    if not _environment_flag(
        "SOFIA_COGNITION_ROUTING_ENABLED",
        default=user_settings.cognitive_routing_enabled,
    ):
        return None

    provider_name = os.environ.get(
        "SOFIA_COGNITION_ROUTING_PROVIDER",
        base.provider,
    ).strip()
    primary_model = os.environ.get(
        "SOFIA_COGNITION_PRIMARY_MODEL",
        user_settings.cognitive_primary_model,
    ).strip()
    secondary_model = os.environ.get(
        "SOFIA_COGNITION_SECONDARY_MODEL",
        user_settings.cognitive_secondary_model,
    ).strip()

    primary = ProviderConfiguration(
        provider=provider_name,
        model=primary_model,
        temperature=base.temperature,
        seed=base.seed,
        context_size=_positive_environment_int(
            "SOFIA_COGNITION_PRIMARY_CONTEXT_SIZE",
            default=user_settings.cognitive_primary_context_size,
        ),
        thinking=base.thinking,
    )
    secondary = ProviderConfiguration(
        provider=provider_name,
        model=secondary_model,
        temperature=base.temperature,
        seed=base.seed,
        context_size=_positive_environment_int(
            "SOFIA_COGNITION_SECONDARY_CONTEXT_SIZE",
            default=user_settings.cognitive_secondary_context_size,
        ),
        thinking=False,
    )
    return CognitiveRoutingConfiguration(
        enabled=True,
        primary=primary,
        secondary=secondary,
        verify_enabled=_environment_flag(
            "SOFIA_COGNITION_VERIFY_ENABLED",
            default=user_settings.cognitive_verify_enabled,
        ),
    )


def _model_lifecycle_configuration_from_environ(
    user_settings,
) -> ModelLifecycleConfiguration:
    keep_alive = os.environ.get(
        "SOFIA_COGNITION_MODEL_KEEP_ALIVE",
        user_settings.cognitive_model_keep_alive,
    ).strip()
    return ModelLifecycleConfiguration(
        enabled=_environment_flag(
            "SOFIA_COGNITION_MODEL_AUTO_MANAGE",
            default=user_settings.cognitive_model_auto_manage,
        ),
        idle_unload_seconds=_positive_environment_int(
            "SOFIA_COGNITION_MODEL_IDLE_UNLOAD_SECONDS",
            default=user_settings.cognitive_model_idle_unload_seconds,
        ),
        keep_alive=keep_alive,
    )


def production_storage_layout(
    *,
    state_path: Path | str | None = None,
) -> RuntimeStorageLayout:
    """Resolve canonical production storage without provisioning it."""
    repository_root = _repository_root()
    layout = RuntimeStorageLayout.from_environment(
        repository_root,
        mode_override="production",
    )
    if state_path is None:
        return layout
    if not isinstance(state_path, (Path, str)):
        raise TypeError("state_path must be a Path, string, or None")

    state = Path(state_path)
    state_root = state.parent
    protected_root = state_root / "protected"
    return replace(
        layout,
        state_root=state_root,
        protected_root=protected_root,
        state_path=state,
        constitution_path=protected_root / "constitution.md",
        constitution_hash_path=protected_root / "constitution.sha256",
        identity_path=protected_root / "identity.json",
        personality_path=state_root / "personality.json",
        avatar_path=state_root / "avatar.json",
    )


def production_state_path() -> Path:
    """Return the canonical live SQLite path without creating files."""
    return production_storage_layout().state_path


def create_default_configuration(
    *,
    runtime_mode: str | None = None,
    state_path: Path | str | None = None,
) -> SofiaConfiguration:
    """
    Create the standard local configuration for Sofía.

    Paths are resolved relative to the repository root rather than
    the current working directory.
    """

    repository_root = _repository_root()

    if runtime_mode == "production":
        layout = production_storage_layout(
            state_path=state_path,
        )
    else:
        if state_path is not None:
            raise ValueError(
                "explicit state_path is supported only for production "
                "configuration"
            )
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

    provider_configuration = ProviderConfiguration(
        provider="ollama",
        model=user_settings.provider_model,
        context_size=user_settings.provider_context_size,
        thinking=user_settings.provider_thinking,
    )

    return SofiaConfiguration(
        constitution_path=layout.constitution_path,
        constitution_hash_path=layout.constitution_hash_path,
        identity_path=layout.identity_path,
        personality_path=layout.personality_path,
        avatar_path=layout.avatar_path,
        state_path=layout.state_path,
        provider=provider_configuration,
        filesystem_root=repository_root,
        identity_bootstrap_mode=layout.identity_bootstrap_mode,
        standing_allowed_capabilities=standing_capabilities,
        routing=_routing_configuration_from_environ(
            provider_configuration,
            user_settings,
        ),
        model_lifecycle=_model_lifecycle_configuration_from_environ(
            user_settings,
        ),
        environment=environment,
    )


def create_production_configuration(
    *,
    state_path: Path | str | None = None,
) -> SofiaConfiguration:
    """Create the canonical live configuration for Sofía."""
    return create_default_configuration(
        runtime_mode="production",
        state_path=state_path,
    )
