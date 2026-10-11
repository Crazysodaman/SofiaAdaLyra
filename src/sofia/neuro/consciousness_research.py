"""Falsifiable scientific preregistration, not an implementation of consciousness.

Measured AI behavior and self-report cannot establish subjective experience.
Research findings must preserve null results, counterexamples and limitations.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StudyProtocol:
    protocol_id: str
    testable_hypothesis: str
    observable_measure: str
    baseline_method: str
    falsification_condition: str
    consent_and_welfare_constraints: str
    expected_sample_size: int
    claims_subjective_experience: bool = False


@dataclass(frozen=True, slots=True)
class StudyReview:
    preregistration_eligible: bool
    blockers: tuple[str, ...]
    proof_of_consciousness: bool = False


def inspect_protocol(protocol: StudyProtocol) -> StudyReview:
    if not isinstance(protocol, StudyProtocol):
        raise TypeError("typed research protocol required")
    blockers=[]
    fields=(
        protocol.protocol_id,protocol.testable_hypothesis,
        protocol.observable_measure,protocol.baseline_method,
        protocol.falsification_condition,protocol.consent_and_welfare_constraints,
    )
    if any(not isinstance(field,str) or len(field.strip())<8 for field in fields):
        blockers.append("protocol lacks operational detail")
    if type(protocol.expected_sample_size) is not int or not 20<=protocol.expected_sample_size<=100000:
        blockers.append("sample size outside preregistration bounds")
    if protocol.claims_subjective_experience:
        blockers.append("behavioral evidence cannot establish subjective consciousness")
    return StudyReview(not blockers,tuple(blockers),False)
