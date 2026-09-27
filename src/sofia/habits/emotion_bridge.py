"""Translate resolved habit expectations into bounded emotional appraisals.

This bridge is intentionally one-way: habit evidence may affect modeled
emotion. Emotional state never changes habit confidence, memory provenance,
consent, authority, or whether an expectation is factually fulfilled.
"""
from __future__ import annotations

from datetime import datetime

from sofia.personality.emotion import EmotionalJournal

from .model import ExpectationStatus, HabitExpectation, HabitPattern, HabitStatus
from .store import HabitStore


def _labels(
    expectation: HabitExpectation,
    pattern: HabitPattern,
) -> tuple[str, ...] | None:
    contact = pattern.kind == "conversation.contact"
    trusted = pattern.status is HabitStatus.TRUSTED

    if expectation.status is ExpectationStatus.FULFILLED:
        if contact:
            return ("contentment", "fondness") if trusted else ("contentment",)
        return ("contentment",)

    if expectation.status is ExpectationStatus.MISSED:
        if contact:
            return (
                ("longing", "disappointment")
                if trusted
                else ("longing", "uncertainty")
            )
        return (
            ("curiosity", "disappointment")
            if trusted
            else ("curiosity", "uncertainty")
        )

    if expectation.status is ExpectationStatus.UNCERTAIN:
        return ("uncertainty", "curiosity")

    return None


def record_expectation_appraisals(
    *,
    expectations: tuple[HabitExpectation, ...],
    store: HabitStore,
    journal: EmotionalJournal,
    at: datetime,
) -> tuple[str, ...]:
    if not isinstance(expectations, tuple):
        raise TypeError("expectations must be a tuple")
    if not isinstance(store, HabitStore):
        raise TypeError("store must be HabitStore")
    if not isinstance(journal, EmotionalJournal):
        raise TypeError("journal must be EmotionalJournal")
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("appraisal time must be timezone-aware")

    by_id: dict[str, HabitPattern] = {}
    for item in expectations:
        if not isinstance(item, HabitExpectation):
            raise TypeError("expectations must contain HabitExpectation values")
        if item.principal_id not in by_id:
            for pattern in store.patterns(principal_id=item.principal_id):
                by_id.setdefault(pattern.habit_id, pattern)

    recorded: list[str] = []
    for expectation in expectations:
        pattern = by_id.get(expectation.habit_id)
        if pattern is None:
            continue
        labels = _labels(expectation, pattern)
        if labels is None:
            continue
        event_id = f"habit-appraisal:{expectation.expectation_id}:{expectation.status.value}"
        if expectation.status is ExpectationStatus.FULFILLED:
            detail = (
                "A recurring pattern expectation was fulfilled by recorded evidence."
            )
        elif expectation.status is ExpectationStatus.MISSED:
            detail = (
                "A recurring pattern window ended without a matching observation "
                "while observation coverage was available."
            )
        else:
            detail = (
                "A recurring pattern window ended without enough observation "
                "coverage to decide whether the routine occurred."
            )
        journal.record(
            event_id=event_id,
            source="inferred",
            evidence_ref=expectation.expectation_id,
            description=(
                f"{detail} Pattern={pattern.kind}:{pattern.value}; "
                f"cadence={pattern.cadence.value}. This appraisal creates no "
                "obligation, blame, consent, permission, or causal claim."
            )[:320],
            emotions=labels,
            occurred_at=at,
            subject=expectation.principal_id,
        )
        recorded.append(event_id)
    return tuple(recorded)
