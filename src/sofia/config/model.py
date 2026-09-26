from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

from sofia.environment.config import EnvironmentConfiguration


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
class SofiaConfiguration:
    constitution_path: Path
    constitution_hash_path: Path
    identity_path: Path
    personality_path: Path
    avatar_path: Path
    state_path: Path
    provider: ProviderConfiguration
    filesystem_root: Path
    standing_allowed_capabilities: tuple[str, ...] = ()
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

        if not isinstance(self.environment, EnvironmentConfiguration):
            raise TypeError(
                "SofiaConfiguration environment must be an "
                "EnvironmentConfiguration."
            )