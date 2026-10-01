"""Evidence requirements and resolution for matrix-controlled turns."""
from __future__ import annotations

from .model import (
    EvidenceKind,
    EvidenceMatrix,
    EvidenceRecord,
    EvidenceRequirement,
    EvidenceState,
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
    TurnMatrix,
)


class MatrixEvidencePlanner:
    """Derive evidence requirements from domain relevance and intent."""

    def plan(self, turn: TurnMatrix) -> EvidenceMatrix:
        if not isinstance(turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix")

        requirements: list[EvidenceRequirement] = []

        def require(key: str, kind: EvidenceKind, required: bool = True) -> None:
            if not any(item.key == key for item in requirements):
                requirements.append(EvidenceRequirement(key, kind, required))

        if turn.relevance_for(MatrixDomain.ENVIRONMENT) is not MatrixRelevance.NONE:
            require("environment.current", EvidenceKind.CURRENT)
        if turn.relevance_for(MatrixDomain.AVATAR) is not MatrixRelevance.NONE:
            require("avatar.canonical", EvidenceKind.CANONICAL)
        if turn.relevance_for(MatrixDomain.INTERACTION) is not MatrixRelevance.NONE:
            require("interaction.interpretation", EvidenceKind.CANONICAL)
        if turn.relevance_for(MatrixDomain.EMOTION) is not MatrixRelevance.NONE:
            require("emotion.current", EvidenceKind.CURRENT, required=False)
        if turn.relevance_for(MatrixDomain.MEMORY) is not MatrixRelevance.NONE:
            require("memory.retrieval", EvidenceKind.REMEMBERED)
        if turn.relevance_for(MatrixDomain.COGNITION) is not MatrixRelevance.NONE:
            require("cognition.configuration", EvidenceKind.CANONICAL)
        if (
            turn.relevance_for(MatrixDomain.MACHINE) is not MatrixRelevance.NONE
            or turn.relevance_for(MatrixDomain.OPS) is MatrixRelevance.REQUIRED
        ):
            require("operational.measurement", EvidenceKind.MEASURED)
        if turn.relevance_for(MatrixDomain.CONTINUITY) is not MatrixRelevance.NONE:
            require("continuity.current", EvidenceKind.CURRENT)
        if turn.intent is MatrixIntent.ACTION_REQUEST:
            require(
                "action.execution_receipt",
                EvidenceKind.EXECUTION_RECEIPT,
                required=False,
            )

        return EvidenceMatrix(requirements=tuple(requirements), records=())


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
