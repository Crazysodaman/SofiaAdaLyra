from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CapabilityProposal:
    """
    Structured proposal produced by cognition.

    A proposal describes an intended capability invocation.
    It does not authorize, approve, or execute the capability.
    """

    capability_name: str
    parameters: dict[str, Any]
    rationale: str
    requested_scope: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability_name, str):
            raise TypeError(
                "CapabilityProposal capability_name must be a string."
            )

        if not self.capability_name.strip():
            raise ValueError(
                "CapabilityProposal capability_name must not be empty."
            )

        if not isinstance(self.parameters, dict):
            raise TypeError(
                "CapabilityProposal parameters must be a dict."
            )

        if not isinstance(self.rationale, str):
            raise TypeError(
                "CapabilityProposal rationale must be a string."
            )

        if not self.rationale.strip():
            raise ValueError(
                "CapabilityProposal rationale must not be empty."
            )