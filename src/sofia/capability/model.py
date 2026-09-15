from dataclasses import dataclass
from enum import Enum
from typing import Any


class CapabilityResultKind(Enum):
    SUCCESS = "success"
    UNAUTHORIZED = "unauthorized"
    DENIED = "denied"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Capability:
    name: str
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Capability name must be a non-empty string.")

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Capability description must be a non-empty string.")


@dataclass(frozen=True)
class CapabilityRequest:
    capability: Capability
    parameters: dict[str, Any]
    requested_scope: Any
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.capability, Capability):
            raise TypeError("capability must be a Capability.")

        if not isinstance(self.parameters, dict):
            raise TypeError("parameters must be a dictionary.")

        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("Capability request rationale must be a non-empty string.")


@dataclass(frozen=True)
class CapabilityResult:
    capability: str
    kind: CapabilityResultKind
    evidence: Any
    error: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("Capability result name must be a non-empty string.")

        if not isinstance(self.kind, CapabilityResultKind):
            raise TypeError("kind must be a CapabilityResultKind.")

        if self.error is not None and not isinstance(self.error, str):
            raise TypeError("error must be a string or None.")