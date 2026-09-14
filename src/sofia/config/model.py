from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProviderConfiguration:
    provider: str
    model: str

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError(
                "ProviderConfiguration provider must not be empty."
            )

        if not self.model:
            raise ValueError(
                "ProviderConfiguration model must not be empty."
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

        if not self.state_path:
            raise ValueError(
                "SofiaConfiguration state_path must not be empty."
            )