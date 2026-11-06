"""Inert host-owned tool-to-capability binding; never an authorization decision."""
from dataclasses import dataclass
from typing import Any

from sofia.sdk.cognition_model import CognitiveToolDefinition


@dataclass(frozen=True)
class CognitiveToolBinding:
    """
    Binds a provider-visible cognitive tool to a canonical capability.

    The binding is host-owned. The cognitive provider cannot modify it.
    """

    definition: CognitiveToolDefinition
    capability_name: str
    requested_scope: Any = None
    fixed_parameters: tuple[tuple[str, Any], ...] = ()
    include_principal_metadata: bool = False
    produces_execution_receipt: bool = False
    execution_receipt_evidence_match: tuple[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.definition,
            CognitiveToolDefinition,
        ):
            raise TypeError(
                "CognitiveToolBinding definition must be a "
                "CognitiveToolDefinition."
            )

        if not isinstance(self.capability_name, str):
            raise TypeError(
                "CognitiveToolBinding capability_name must be a string."
            )

        if not self.capability_name.strip():
            raise ValueError(
                "CognitiveToolBinding capability_name must not be empty."
            )

        if not isinstance(self.include_principal_metadata, bool):
            raise TypeError(
                "CognitiveToolBinding include_principal_metadata must be boolean."
            )

        if not isinstance(self.produces_execution_receipt, bool):
            raise TypeError(
                "CognitiveToolBinding produces_execution_receipt must be boolean."
            )

        if self.execution_receipt_evidence_match is not None:
            match = self.execution_receipt_evidence_match
            if (
                not isinstance(match, tuple)
                or len(match) != 2
                or not isinstance(match[0], str)
                or not match[0].strip()
            ):
                raise TypeError(
                    "CognitiveToolBinding execution_receipt_evidence_match "
                    "must be None or a (nonempty str, value) pair."
                )
            if not self.produces_execution_receipt:
                raise ValueError(
                    "execution_receipt_evidence_match requires "
                    "produces_execution_receipt=True."
                )

        if not isinstance(self.fixed_parameters, tuple):
            raise TypeError(
                "CognitiveToolBinding fixed_parameters must be a tuple."
            )

        for item in self.fixed_parameters:
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
            ):
                raise TypeError(
                    "CognitiveToolBinding fixed_parameters must contain "
                    "(str, value) pairs."
                )


