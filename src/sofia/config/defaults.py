from dataclasses import replace
from pathlib import Path
import os

from sofia.config.model import (
    CognitiveRoutingConfiguration,
    FleetBootstrapConfiguration,
    FleetCognitionConfiguration,
    FleetDiscoveryConfiguration,
    ModelLifecycleConfiguration,
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.environment.config import environment_configuration_from_environ
from sofia.config.layout import RuntimeStorageLayout
from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.safe.permissions import automatic_capabilities


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


def _nonnegative_environment_int(name: str, *, default: int = 0) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _environment_csv(name: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value.strip()
            for value in os.environ.get(name, "").split(",")
            if value.strip()
        )
    )


def _fleet_cognition_configuration_from_environ() -> FleetCognitionConfiguration:
    return FleetCognitionConfiguration(
        enabled=_environment_flag(
            "SOFIA_COGNITION_FLEET_ENABLED",
            default=False,
        ),
        local_fallback=_environment_flag(
            "SOFIA_COGNITION_FLEET_LOCAL_FALLBACK",
            default=True,
        ),
        min_ram_bytes=_nonnegative_environment_int(
            "SOFIA_COGNITION_FLEET_MIN_RAM_BYTES",
        ),
        min_vram_bytes=_nonnegative_environment_int(
            "SOFIA_COGNITION_FLEET_MIN_VRAM_BYTES",
        ),
        gpu_required=_environment_flag(
            "SOFIA_COGNITION_FLEET_GPU_REQUIRED",
            default=False,
        ),
        auto_provision_models=_environment_flag(
            "SOFIA_COGNITION_FLEET_AUTO_PROVISION_MODELS",
            default=False,
        ),
        allowed_host_ids=_environment_csv(
            "SOFIA_COGNITION_FLEET_ALLOWED_HOST_IDS"
        ),
        denied_host_ids=_environment_csv(
            "SOFIA_COGNITION_FLEET_DENIED_HOST_IDS"
        ),
    )


def _fleet_bootstrap_configuration_from_environ() -> FleetBootstrapConfiguration:
    sha256 = os.environ.get(
        "SOFIA_FLEET_BOOTSTRAP_PACKAGE_SHA256",
        "",
    ).strip() or None
    source = os.environ.get(
        "SOFIA_FLEET_BOOTSTRAP_PACKAGE_SOURCE",
        "",
    ).strip() or None
    signer = os.environ.get(
        "SOFIA_FLEET_BOOTSTRAP_SIGNER_KEY_ID",
        "",
    ).strip() or None
    return FleetBootstrapConfiguration(
        enabled=_environment_flag(
            "SOFIA_FLEET_BOOTSTRAP_ENABLED",
            default=False,
        ),
        authority=os.environ.get(
            "SOFIA_FLEET_BOOTSTRAP_AUTHORITY",
            "none",
        ).strip().lower(),
        package_id=os.environ.get(
            "SOFIA_FLEET_BOOTSTRAP_PACKAGE_ID",
            "sofia-fleet-agent",
        ).strip(),
        package_version=os.environ.get(
            "SOFIA_FLEET_BOOTSTRAP_PACKAGE_VERSION",
            "0.1.0",
        ).strip(),
        package_sha256=sha256,
        package_source=source,
        protocol_version=os.environ.get(
            "SOFIA_FLEET_BOOTSTRAP_PROTOCOL_VERSION",
            "1.0",
        ).strip(),
        signer_key_id=signer,
    )


def _fleet_discovery_configuration_from_environ(
    user_settings,
    *,
    allow_environment_overrides: bool = True,
) -> FleetDiscoveryConfiguration:
    raw_targets = (
        _environment_csv("SOFIA_FLEET_DISCOVERY_TARGETS")
        if allow_environment_overrides and "SOFIA_FLEET_DISCOVERY_TARGETS" in os.environ
        else user_settings.fleet_discovery_targets
    )
    raw_scopes = (
        _environment_csv("SOFIA_FLEET_DISCOVERY_SCOPES")
        if allow_environment_overrides and "SOFIA_FLEET_DISCOVERY_SCOPES" in os.environ
        else user_settings.fleet_discovery_scopes
    )
    return FleetDiscoveryConfiguration(
        enabled=(
            _environment_flag(
                "SOFIA_FLEET_DISCOVERY_ENABLED",
                default=user_settings.fleet_discovery_enabled,
            )
            if allow_environment_overrides and "SOFIA_FLEET_DISCOVERY_ENABLED" in os.environ
            else user_settings.fleet_discovery_enabled
        ),
        interval_seconds=(
            _positive_environment_int(
                "SOFIA_FLEET_DISCOVERY_INTERVAL_SECONDS",
                default=user_settings.fleet_discovery_interval_seconds,
            )
            if allow_environment_overrides and "SOFIA_FLEET_DISCOVERY_INTERVAL_SECONDS" in os.environ
            else user_settings.fleet_discovery_interval_seconds
        ),
        targets=raw_targets,
        scopes=raw_scopes,
        max_hosts_per_scope=(
            _positive_environment_int(
                "SOFIA_FLEET_DISCOVERY_MAX_HOSTS_PER_SCOPE",
                default=user_settings.fleet_discovery_max_hosts_per_scope,
            )
            if allow_environment_overrides and "SOFIA_FLEET_DISCOVERY_MAX_HOSTS_PER_SCOPE" in os.environ
            else user_settings.fleet_discovery_max_hosts_per_scope
        ),
    )


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
        max_output_tokens=base.max_output_tokens,
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
        max_output_tokens=base.max_output_tokens,
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
        parallel_enabled=_environment_flag(
            "SOFIA_COGNITION_PARALLEL_ENABLED",
            default=True,
        ),
        fallback_enabled=_environment_flag(
            "SOFIA_COGNITION_FALLBACK_ENABLED",
            default=False,
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
        auto_install_missing=_environment_flag(
            "SOFIA_COGNITION_MODEL_AUTO_INSTALL",
            default=user_settings.cognitive_model_auto_install,
        ),
        idle_unload_seconds=_positive_environment_int(
            "SOFIA_COGNITION_MODEL_IDLE_UNLOAD_SECONDS",
            default=user_settings.cognitive_model_idle_unload_seconds,
        ),
        keep_alive=keep_alive,
        residency_mode=os.environ.get(
            "SOFIA_COGNITION_MODEL_RESIDENCY_MODE",
            user_settings.cognitive_model_residency_mode,
        ).strip().casefold(),
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

    environment_values = user_settings.environment_mapping()
    if runtime_mode != "production":
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
    standing_capabilities=automatic_capabilities()

    provider_configuration = ProviderConfiguration(
        provider="ollama",
        model=user_settings.provider_model,
        context_size=user_settings.provider_context_size,
        max_output_tokens=user_settings.provider_max_output_tokens,
        thinking=user_settings.provider_thinking,
        temperature=user_settings.provider_temperature,
        seed=user_settings.provider_seed,
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
        fleet_cognition=user_settings.fleet_cognition or _fleet_cognition_configuration_from_environ(),
        fleet_discovery=_fleet_discovery_configuration_from_environ(
            user_settings,
            allow_environment_overrides=runtime_mode != "production",
        ),
        fleet_bootstrap=user_settings.fleet_bootstrap or _fleet_bootstrap_configuration_from_environ(),
        environment=environment,
        avatar_private_adult_verified=_environment_flag(
            "SOFIA_AVATAR_PRIVATE_ADULT_VERIFIED",
            default=False,
        ),
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
