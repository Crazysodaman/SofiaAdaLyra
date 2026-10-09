"""Host-only resolution for evidence needs planned by Cognition v2."""
from __future__ import annotations

from .model import EvidenceMatrix, EvidenceRecord, EvidenceState


class MatrixEvidenceResolver:
    """Resolve requirements from host-supplied evidence states.

    The resolver accepts only host-produced availability. It does not infer
    facts from the user's words or from model output.
    """

    def resolve(
        self,
        matrix: EvidenceMatrix,
        availability: dict[str, EvidenceRecord | EvidenceState],
    ) -> EvidenceMatrix:
        if not isinstance(matrix, EvidenceMatrix):
            raise TypeError("matrix must be EvidenceMatrix")
        if not isinstance(availability, dict):
            raise TypeError("availability must be a dict")

        records: list[EvidenceRecord] = []
        for requirement in matrix.requirements:
            value = availability.get(requirement.key, EvidenceState.UNKNOWN)
            if isinstance(value, EvidenceRecord):
                record = value
            elif isinstance(value, EvidenceState):
                record = EvidenceRecord(requirement.key, value)
            else:
                raise TypeError(
                    "availability values must be EvidenceRecord or EvidenceState"
                )
            if record.key != requirement.key:
                raise ValueError("evidence record key does not match requirement")
            records.append(record)

        return EvidenceMatrix(
            requirements=matrix.requirements,
            records=tuple(records),
        )
