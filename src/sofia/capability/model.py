from dataclasses import dataclass
from enum import Enum
from typing import Any


class CapabilityResultKind(str, Enum):
    SUCCESS = "success"
    UNAUTHORIZED = "unauthorized"
    DENIED = "denied"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class CapabilityExecutionError(Exception):
    """Raised when capability execution cannot be completed."""


class CapabilityResolutionError(Exception):
    """Raised when a requested capability cannot be resolved."""


@dataclass(frozen=True)
class Capability:
    name: str
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                "Capability name must be a string."
            )

        if not self.name.strip():
            raise ValueError(
                "Capability name must not be empty."
            )

        if not isinstance(self.description, str):
            raise TypeError(
                "Capability description must be a string."
            )

        if not self.description.strip():
            raise ValueError(
                "Capability description must not be empty."
            )


@dataclass(frozen=True)
class CapabilityRequest:
    capability: Capability
    parameters: dict[str, Any]
    requested_scope: Any
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.capability, Capability):
            raise TypeError(
                "CapabilityRequest capability must be a Capability."
            )

        if not isinstance(self.parameters, dict):
            raise TypeError(
                "CapabilityRequest parameters must be a dict."
            )

        if not isinstance(self.rationale, str):
            raise TypeError(
                "CapabilityRequest rationale must be a string."
            )

        if not self.rationale.strip():
            raise ValueError(
                "CapabilityRequest rationale must not be empty."
            )


@dataclass(frozen=True)
class CapabilityResult:
    capability: str
    kind: CapabilityResultKind
    evidence: Any = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str):
            raise TypeError(
                "CapabilityResult capability must be a string."
            )

        if not self.capability.strip():
            raise ValueError(
                "CapabilityResult capability must not be empty."
            )

        if not isinstance(
            self.kind,
            CapabilityResultKind,
        ):
            raise TypeError(
                "CapabilityResult kind must be a "
                "CapabilityResultKind."
            )

        if (
            self.error is not None
            and not isinstance(self.error, str)
        ):
            raise TypeError(
                "CapabilityResult error must be a string or None."
            )