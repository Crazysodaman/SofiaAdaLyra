from dataclasses import dataclass


@dataclass(frozen=True)
class SofiaConfiguration:
    constitution_path: str
    constitution_hash_path: str
    identity_path: str
    provider: "ProviderConfiguration"


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