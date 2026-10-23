"""Sofía's held convictions and her owner's stated positions.

A conviction is a bounded, evidence-linked, revision-tracked stance. The
holder distinction keeps Sofía's own positions separate from positions her
owner stated, so owner statements can be attributed rather than absorbed.
This package stores durable personal state; it never executes anything and
never grants authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class BeliefHolder(str, Enum):
    """Who holds the position described by a record."""

    SOFIA = "sofia"
    OWNER = "owner"


class BeliefStance(str, Enum):
    """The current posture on one topic."""

    SUPPORT = "support"
    OPPOSE = "oppose"
    UNCERTAIN = "uncertain"
    WITHDRAWN = "withdrawn"


class BeliefVisibility(str, Enum):
    """Audience disclosure scope recorded in the store."""

    OWNER_AUDIENCE_ONLY = "owner_audience_only"
    DISCLOSURE_SCOPED = "disclosure_scoped"


class BeliefChangeKind(str, Enum):
    """Why one revision exists."""

    ORIGIN = "origin"
    RESTATE = "restate"
    REVISE = "revise"
    RECONSIDER = "reconsider"
    RETRACT = "retract"


class BeliefStoreError(Exception):
    """Raised when stored conviction data is invalid."""


class BeliefConcurrencyError(RuntimeError):
    """Raised when a revision does not match the stored revision."""


@dataclass(frozen=True, slots=True)
class BeliefRecord:
    """One stored revision of a held-or-attributed position."""

    conviction_id: str
    revision: int
    holder: BeliefHolder
    topic: str
    statement: str
    stance: BeliefStance
    confidence: float
    reason: str
    evidence_refs: tuple[str, ...]
    counterevidence_refs: tuple[str, ...]
    audience_id: str
    visibility: BeliefVisibility
    change_kind: BeliefChangeKind
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.conviction_id, str) or not (
            8 <= len(self.conviction_id) <= 120
        ):
            raise ValueError("conviction_id must be bounded text")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        if not isinstance(self.holder, BeliefHolder):
            raise TypeError("holder must be a BeliefHolder")
        topic = self.topic.strip()
        if not 1 <= len(topic) <= 120:
            raise ValueError("topic must be bounded text of 1..120 characters")
        statement = self.statement.strip()
        if not 1 <= len(statement) <= 600:
            raise ValueError(
                "statement must be bounded text of 1..600 characters"
            )
        if not isinstance(self.stance, BeliefStance):
            raise TypeError("stance must be a BeliefStance")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0.0 <= float(self.confidence) <= 1.0
        ):
            raise ValueError("confidence must be a number in 0..1")
        reason = self.reason.strip()
        if not 1 <= len(reason) <= 600:
            raise ValueError("reason must be bounded text of 1..600 characters")
        if not self._refs_are_valid(self.evidence_refs):
            raise ValueError(
                "evidence_refs must be 1..8 bounded `source:value` references"
            )
        if not self._refs_are_valid(
            self.counterevidence_refs,
            allow_empty=True,
        ):
            raise ValueError(
                "counterevidence_refs must be 0..8 bounded "
                "`source:value` references"
            )
        if not isinstance(self.audience_id, str) or not (
            1 <= len(self.audience_id) <= 120
        ):
            raise ValueError("audience_id must be bounded text")
        if not isinstance(self.visibility, BeliefVisibility):
            raise TypeError("visibility must be a BeliefVisibility")
        if not isinstance(self.change_kind, BeliefChangeKind):
            raise TypeError("change_kind must be a BeliefChangeKind")
        if (
            self.revision == 1
            and self.change_kind is not BeliefChangeKind.ORIGIN
        ):
            raise ValueError("the first revision must have change_kind origin")
        if self.revision > 1 and self.change_kind is BeliefChangeKind.ORIGIN:
            raise ValueError("only the first revision may have change_kind origin")
        if self.stance is BeliefStance.WITHDRAWN and self.change_kind not in {
            BeliefChangeKind.RETRACT,
        }:
            raise ValueError("withdrawn stance requires the retract change kind")
        if self.change_kind is BeliefChangeKind.RETRACT and (
            self.stance is not BeliefStance.WITHDRAWN
        ):
            raise ValueError("the retract change kind requires a withdrawn stance")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")

    @staticmethod
    def _refs_are_valid(
        refs: tuple[str, ...],
        *,
        allow_empty: bool = False,
    ) -> bool:
        if not allow_empty and len(refs) < 1:
            return False
        if len(refs) > 8:
            return False
        for ref in refs:
            if not isinstance(ref, str):
                return False
            if len(ref) < 4 or len(ref) > 240:
                return False
            if ":" not in ref:
                return False
            source, _, value = ref.partition(":")
            if not source.isidentifier():
                return False
            if not value.strip():
                return False
            if ref != ref.strip():
                return False
        return True


@dataclass(frozen=True, slots=True)
class BeliefMatch:
    """One relevance-scored record from store retrieval."""

    record: BeliefRecord
    score: int
