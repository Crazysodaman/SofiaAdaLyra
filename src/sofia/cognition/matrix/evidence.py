"""Evidence requirements and resolution for matrix-controlled turns."""
from __future__ import annotations

import re

from .model import (
    EvidenceKind,
    EvidenceMatrix,
    EvidenceRecord,
    EvidenceRequirement,
    EvidenceState,
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
    TurnEnvelope,
    TurnMatrix,
)


_WEATHER = re.compile(
    r"\b(?:weather|temperature|forecast|humidity|rain|snow|wind|outside)\b",
    re.IGNORECASE,
)
_CLOCK = re.compile(
    r"(?:\b(?:what\s+time|time\s+is\s+it|timezone|date|day\s+is\s+it)\b"
    r"|^\s*time\s*[?!.]*\s*$)",
    re.IGNORECASE,
)
_LOCATION = re.compile(
    r"\b(?:where\s+am\s+i|where\s+are\s+you|location|located)\b",
    re.IGNORECASE,
)
_CALENDAR = re.compile(
    r"\b(?:season|daylight|sunrise|sunset)\b",
    re.IGNORECASE,
)


class MatrixEvidencePlanner:
    """Derive evidence requirements from domain relevance and intent."""

    def plan(
        self,
        turn: TurnMatrix,
        envelope: TurnEnvelope | None = None,
    ) -> EvidenceMatrix:
        if not isinstance(turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix")
        if envelope is not None and not isinstance(envelope, TurnEnvelope):
            raise TypeError("envelope must be TurnEnvelope or None")

        requirements: list[EvidenceRequirement] = []

        def require(
            key: str,
            kind: EvidenceKind,
            required: bool = True,
        ) -> None:
            if not any(item.key == key for item in requirements):
                requirements.append(
                    EvidenceRequirement(key, kind, required)
                )

        environment_relevance = turn.relevance_for(MatrixDomain.ENVIRONMENT)
        if environment_relevance is not MatrixRelevance.NONE:
            text = "" if envelope is None else envelope.content
            environment_required = (
                environment_relevance is MatrixRelevance.REQUIRED
            )
            if envelope is None:
                require(
                    "environment.current",
                    EvidenceKind.CURRENT,
                    required=environment_required,
                )
            else:
                matched = False
                if _WEATHER.search(text):
                    require(
                        "environment.weather.current",
                        EvidenceKind.CURRENT,
                        required=environment_required,
                    )
                    matched = True
                if _CLOCK.search(text):
                    require(
                        "environment.clock.current",
                        EvidenceKind.CURRENT,
                        required=environment_required,
                    )
                    matched = True
                if _LOCATION.search(text):
                    require(
                        "environment.location.current",
                        EvidenceKind.CURRENT,
                        required=environment_required,
                    )
                    matched = True
                if _CALENDAR.search(text):
                    require(
                        "environment.calendar.current",
                        EvidenceKind.CURRENT,
                        required=environment_required,
                    )
                    matched = True
                if not matched:
                    require(
                        "environment.current",
                        EvidenceKind.CURRENT,
                        required=environment_required,
                    )

        avatar_relevance = turn.relevance_for(MatrixDomain.AVATAR)
        if avatar_relevance is not MatrixRelevance.NONE:
            require(
                "avatar.canonical",
                EvidenceKind.CANONICAL,
                required=(
                    avatar_relevance is MatrixRelevance.REQUIRED
                    or turn.intent is MatrixIntent.ACTION_REQUEST
                ),
            )

        interaction_relevance = turn.relevance_for(MatrixDomain.INTERACTION)
        if interaction_relevance is not MatrixRelevance.NONE:
            require(
                "interaction.interpretation",
                EvidenceKind.CANONICAL,
                required=interaction_relevance is MatrixRelevance.REQUIRED,
            )

        emotion_relevance = turn.relevance_for(MatrixDomain.EMOTION)
        if emotion_relevance is not MatrixRelevance.NONE:
            require(
                "emotion.current",
                EvidenceKind.CURRENT,
                required=emotion_relevance is MatrixRelevance.REQUIRED,
            )
        memory_relevance = turn.relevance_for(MatrixDomain.MEMORY)
        if memory_relevance is not MatrixRelevance.NONE:
            require(
                "memory.retrieval",
                EvidenceKind.REMEMBERED,
                required=memory_relevance is MatrixRelevance.REQUIRED,
            )
        rel_relevance = turn.relevance_for(MatrixDomain.REL)
        if rel_relevance is not MatrixRelevance.NONE:
            require(
                "relationship.prior_contact",
                EvidenceKind.REMEMBERED,
                required=rel_relevance is MatrixRelevance.REQUIRED,
            )
        habit_relevance = turn.relevance_for(MatrixDomain.HABIT)
        if habit_relevance is not MatrixRelevance.NONE:
            require(
                "habit.patterns",
                EvidenceKind.REMEMBERED,
                required=habit_relevance is MatrixRelevance.REQUIRED,
            )
        voice_relevance = turn.relevance_for(MatrixDomain.VOICE)
        if voice_relevance is not MatrixRelevance.NONE:
            require(
                "voice.runtime.current",
                EvidenceKind.CURRENT,
                required=voice_relevance is MatrixRelevance.REQUIRED,
            )

        cognition_relevance = turn.relevance_for(MatrixDomain.COGNITION)
        if cognition_relevance is not MatrixRelevance.NONE:
            require(
                "cognition.configuration",
                EvidenceKind.CANONICAL,
                required=cognition_relevance is MatrixRelevance.REQUIRED,
            )
        machine_relevance = turn.relevance_for(MatrixDomain.MACHINE)
        ops_relevance = turn.relevance_for(MatrixDomain.OPS)
        if (
            machine_relevance is not MatrixRelevance.NONE
            or ops_relevance is not MatrixRelevance.NONE
        ):
            require(
                "operational.measurement",
                EvidenceKind.MEASURED,
                required=(
                    machine_relevance is MatrixRelevance.REQUIRED
                    or ops_relevance is MatrixRelevance.REQUIRED
                ),
            )
        continuity_relevance = turn.relevance_for(MatrixDomain.CONTINUITY)
        if continuity_relevance is not MatrixRelevance.NONE:
            require(
                "continuity.current",
                EvidenceKind.CURRENT,
                required=continuity_relevance is MatrixRelevance.REQUIRED,
            )
        if turn.intent is MatrixIntent.ACTION_REQUEST:
            require(
                "action.execution_receipt",
                EvidenceKind.EXECUTION_RECEIPT,
                required=False,
            )

        return EvidenceMatrix(
            requirements=tuple(requirements),
            records=(),
        )


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
            value = availability.get(
                requirement.key,
                EvidenceState.UNKNOWN,
            )
            if isinstance(value, EvidenceRecord):
                record = value
            elif isinstance(value, EvidenceState):
                record = EvidenceRecord(requirement.key, value)
            else:
                raise TypeError(
                    "availability values must be EvidenceRecord "
                    "or EvidenceState"
                )
            if record.key != requirement.key:
                raise ValueError(
                    "evidence record key does not match requirement"
                )
            records.append(record)

        return EvidenceMatrix(
            requirements=matrix.requirements,
            records=tuple(records),
        )
