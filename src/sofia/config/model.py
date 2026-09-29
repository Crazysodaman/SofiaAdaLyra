from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

CURRENT_CONFIGURATION_SCHEMA_VERSION = 1

from sofia.environment.config import EnvironmentConfiguration
from sofia.identity.model import IdentityBootstrapMode


@dataclass(frozen=True)
class ProviderConfiguration:
    """
    Provider-neutral configuration for the cognitive engine.

    Generation controls are explicit configuration rather than hidden
    provider defaults. A value of None means the provider's configured
    default remains in effect.

    Provider-specific translation belongs in the provider adapter.
    """

    provider: str
    model: str
    temperature: float | None = None
    seed: int | None = None
    context_size: int | None = None
    thinking: bool | str | None = None

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError(
                "ProviderConfiguration provider must not be empty."
            )

        if not self.model:
            raise ValueError(
                "ProviderConfiguration model must not be empty."
            )

        if self.temperature is not None:
            if not isinstance(
                self.temperature,
                (int, float),
            ):
                raise TypeError(
                    "ProviderConfiguration temperature must be numeric or None."
                )

            if self.temperature < 0:
                raise ValueError(
                    "ProviderConfiguration temperature must be >= 0."
                )

        if self.seed is not None:
            if not isinstance(self.seed, int):
                raise TypeError(
                    "ProviderConfiguration seed must be an int or None."
                )

        if self.context_size is not None:
            if not isinstance(self.context_size, int):
                raise TypeError(
                    "ProviderConfiguration context_size must be an int or None."
                )

            if self.context_size <= 0:
                raise ValueError(
                    "ProviderConfiguration context_size must be > 0."
                )

        if self.thinking is not None:
            if not isinstance(
                self.thinking,
                (bool, str),
            ):
                raise TypeError(
                    "ProviderConfiguration thinking must be bool, str, or None."
                )

            if isinstance(self.thinking, str):
                if not self.thinking.strip():
                    raise ValueError(
                        "ProviderConfiguration thinking string must not be empty."
                    )


@dataclass(frozen=True)
class CognitiveRoutingConfiguration:
    """Optional multi-model cognitive routing configuration."""

    enabled: bool = False
    primary: ProviderConfiguration | None = None
    secondary: ProviderConfiguration | None = None
    verify_enabled: bool = True

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise TypeError("routing enabled must be a bool")
        if type(self.verify_enabled) is not bool:
            raise TypeError("routing verify_enabled must be a bool")
        for name in ("primary", "secondary"):
            value = getattr(self, name)
            if value is not None and not isinstance(
                value,
                ProviderConfiguration,
            ):
                raise TypeError(
                    f"routing {name} must be a ProviderConfiguration or None"
                )
        if self.enabled and (
            self.primary is None or self.secondary is None
        ):
            raise ValueError(
                "enabled cognitive routing requires primary and secondary "
                "provider configurations"
            )


@dataclass(frozen=True)
class ModelLifecycleConfiguration:
    """Host-owned lifecycle policy for configured cognitive model roles."""

    enabled: bool = False
    auto_install_missing: bool = False
    idle_unload_seconds: int = 1800
    keep_alive: str = "10m"

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise TypeError("model lifecycle enabled must be a bool")
        if type(self.auto_install_missing) is not bool:
            raise TypeError("model lifecycle auto_install_missing must be a bool")
        if (
            type(self.idle_unload_seconds) is not int
            or not 1 <= self.idle_unload_seconds <= 86400
        ):
            raise ValueError(
                "model lifecycle idle_unload_seconds must be in 1..86400"
            )
        if (
            not isinstance(self.keep_alive, str)
            or not self.keep_alive.strip()
            or len(self.keep_alive) > 64
        ):
            raise ValueError(
                "model lifecycle keep_alive must be a nonempty bounded string"
            )


@dataclass(frozen=True)
class FleetCognitionConfiguration:
    """Optional production placement of cognitive roles onto trusted Fleet nodes."""

    enabled: bool = False
    local_fallback: bool = True
    min_ram_bytes: int = 0
    min_vram_bytes: int = 0
    gpu_required: bool = False
    auto_provision_models: bool = False
    allowed_host_ids: tuple[str, ...] = ()
    denied_host_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "enabled",
            "local_fallback",
            "gpu_required",
            "auto_provision_models",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"fleet cognition {name} must be a bool")
        for name in ("min_ram_bytes", "min_vram_bytes"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(
                    f"fleet cognition {name} must be a nonnegative int"
                )
        for name in ("allowed_host_ids", "denied_host_ids"):
            values = getattr(self, name)
            if not isinstance(values, tuple):
                raise TypeError(f"fleet cognition {name} must be a tuple")
            if any(
                not isinstance(value, str) or not value.strip()
                for value in values
            ):
                raise ValueError(
                    f"fleet cognition {name} must contain nonempty host IDs"
                )


@dataclass(frozen=True)
class SofiaConfiguration:
    constitution_path: Path
    constitution_hash_path: Path
    identity_path: Path
    personality_path: Path
    avatar_path: Path
    state_path: Path
    provider: ProviderConfiguration
    filesystem_root: Path
    identity_bootstrap_mode: IdentityBootstrapMode = IdentityBootstrapMode.FIRST_BOOTSTRAP
    standing_allowed_capabilities: tuple[str, ...] = ()
    routing: CognitiveRoutingConfiguration | None = None
    model_lifecycle: ModelLifecycleConfiguration = field(
        default_factory=ModelLifecycleConfiguration
    )
    fleet_cognition: FleetCognitionConfiguration = field(
        default_factory=FleetCognitionConfiguration
    )
    environment: EnvironmentConfiguration = field(
        default_factory=EnvironmentConfiguration
    )

    def __post_init__(self) -> None:
        if not isinstance(self.provider, ProviderConfiguration):
            raise TypeError(
                "SofiaConfiguration provider must be a "
                "ProviderConfiguration."
            )

        if not isinstance(self.filesystem_root, Path):
            raise TypeError(
                "SofiaConfiguration filesystem_root must be a Path."
            )

        if not isinstance(self.identity_bootstrap_mode, IdentityBootstrapMode):
            raise TypeError(
                "SofiaConfiguration identity_bootstrap_mode must be an "
                "IdentityBootstrapMode."
            )

        if not self.personality_path:
            raise ValueError(
                "SofiaConfiguration personality_path must not be empty."
            )

        if not self.avatar_path:
            raise ValueError(
                "SofiaConfiguration avatar_path must not be empty."
            )

        if not isinstance(self.standing_allowed_capabilities, tuple):
            raise TypeError(
                "SofiaConfiguration standing_allowed_capabilities must be a tuple."
            )
        for capability in self.standing_allowed_capabilities:
            if not isinstance(capability, str) or not capability.strip():
                raise ValueError(
                    "standing_allowed_capabilities must contain nonempty strings."
                )

        if not self.state_path:
            raise ValueError(
                "SofiaConfiguration state_path must not be empty."
            )

        if self.routing is not None and not isinstance(
            self.routing,
            CognitiveRoutingConfiguration,
        ):
            raise TypeError(
                "SofiaConfiguration routing must be a "
                "CognitiveRoutingConfiguration or None."
            )

        if not isinstance(
            self.model_lifecycle,
            ModelLifecycleConfiguration,
        ):
            raise TypeError(
                "SofiaConfiguration model_lifecycle must be a "
                "ModelLifecycleConfiguration."
            )

        if not isinstance(
            self.fleet_cognition,
            FleetCognitionConfiguration,
        ):
            raise TypeError(
                "SofiaConfiguration fleet_cognition must be a "
                "FleetCognitionConfiguration."
            )

        if not isinstance(self.environment, EnvironmentConfiguration):
            raise TypeError(
                "SofiaConfiguration environment must be an "
                "EnvironmentConfiguration."
            )