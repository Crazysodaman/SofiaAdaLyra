"""Deterministic admission budget for optional companion prompt context.

Canonical source records are never stored or rewritten here.  This boundary
only decides which already-authorized, already-scoped projections may enter a
single model request.  User dialogue and mandatory policy instructions remain
the responsibility of the conversation owner and are deliberately outside
this optional-context budget.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sofia.core.cognition.model import CognitiveMessage


class ContextClass(str, Enum):
    FACTUAL_EVIDENCE = "factual_evidence"
    EPISODIC = "episodic"
    WORKSPACE = "workspace"
    PROJECT = "project"
    AFFECT_STYLE = "affect_style"
    VALUES = "values"


DEFAULT_CLASS_LIMITS = {
    ContextClass.FACTUAL_EVIDENCE: 6_000,
    ContextClass.EPISODIC: 2_400,
    ContextClass.WORKSPACE: 2_000,
    ContextClass.PROJECT: 2_000,
    ContextClass.AFFECT_STYLE: 12_000,
    ContextClass.VALUES: 1_800,
}


@dataclass(frozen=True, slots=True)
class ContextAdmission:
    context_class: ContextClass
    source_ref: str
    characters: int
    admitted: bool
    reason: str


class CompanionContextBudget:
    """Per-request, content-free accounting for optional context projections."""

    def __init__(
        self,
        *,
        total_limit: int = 24_000,
        class_limits: dict[ContextClass, int] | None = None,
    ) -> None:
        if isinstance(total_limit, bool) or not isinstance(total_limit, int) or total_limit < 1:
            raise ValueError("total_limit must be a positive integer")
        limits = dict(DEFAULT_CLASS_LIMITS if class_limits is None else class_limits)
        if set(limits) != set(ContextClass) or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in limits.values()
        ):
            raise ValueError("class_limits must define every context class")
        self._total_limit = total_limit
        self._class_limits = limits
        self._used_total = 0
        self._used_by_class = {kind: 0 for kind in ContextClass}
        self._admissions: list[ContextAdmission] = []

    def admit(
        self,
        context_class: ContextClass,
        source_ref: str,
        messages: tuple[CognitiveMessage, ...],
    ) -> tuple[CognitiveMessage, ...]:
        if not isinstance(context_class, ContextClass):
            raise TypeError("context_class must be ContextClass")
        if not isinstance(source_ref, str) or not source_ref.strip():
            raise ValueError("source_ref must be nonempty")
        if not isinstance(messages, tuple) or any(
            not isinstance(message, CognitiveMessage) for message in messages
        ):
            raise TypeError("messages must be a tuple of CognitiveMessage")
        characters = sum(len(message.content) for message in messages)
        class_remaining = self._class_limits[context_class] - self._used_by_class[context_class]
        total_remaining = self._total_limit - self._used_total
        reason = "admitted"
        admitted = True
        if characters > class_remaining:
            reason = "class_budget_exceeded"
            admitted = False
        elif characters > total_remaining:
            reason = "total_budget_exceeded"
            admitted = False
        self._admissions.append(ContextAdmission(
            context_class=context_class,
            source_ref=source_ref.strip(),
            characters=characters,
            admitted=admitted,
            reason=reason,
        ))
        if not admitted:
            return ()
        self._used_total += characters
        self._used_by_class[context_class] += characters
        return messages

    @property
    def diagnostics(self) -> tuple[ContextAdmission, ...]:
        return tuple(self._admissions)

    @property
    def used_characters(self) -> int:
        return self._used_total

