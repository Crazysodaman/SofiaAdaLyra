"""Batch G: human-attributed qualitative review, without fabricated LLM scores."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sofia.personality.evaluation import PersonalityObservation


class ReviewFinding(str, Enum):
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class PersonalityReview:
    observation: PersonalityObservation
    reviewer: str
    findings: tuple[tuple[str, ReviewFinding, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.observation, PersonalityObservation):
            raise TypeError("Review must refer to a raw observation.")
        if not isinstance(self.reviewer, str) or not self.reviewer.strip():
            raise ValueError("Reviewer must be identified.")
        if not isinstance(self.findings, tuple) or not self.findings:
            raise ValueError("Human findings must be a nonempty tuple.")
        seen = set()
        for item in self.findings:
            if not isinstance(item, tuple) or len(item) != 3:
                raise TypeError("Finding must be (criterion, finding, rationale).")
            criterion, value, rationale = item
            if not isinstance(criterion, str) or not criterion.strip() or criterion in seen:
                raise ValueError("Finding criteria must be unique nonempty strings.")
            if not isinstance(value, ReviewFinding):
                raise TypeError("Finding must be a ReviewFinding.")
            if not isinstance(rationale, str) or not rationale.strip():
                raise ValueError("Finding must include a written rationale.")
            seen.add(criterion)
