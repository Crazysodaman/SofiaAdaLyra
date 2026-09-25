"""Diagnostic-only inspection of model-authored avatar response reasons.

A conversational decline is valid, even if no prior preference exists. This
heuristic checks the *stated premise* of the choice, not whether Sofía ought
to accept an offer. It neither changes the choice nor grants consent, persists
state, invokes tools, or asserts subjective emotion. Regex misses and false
positives require human review of the unmodified reason.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from sofia.interaction.decision_expression import CandidateChoice, ReviewedFrame


_PHYSICAL_IMPOSSIBILITY = re.compile(
    r"\b(?:not\s+physically\s+present|no\s+physical\s+(?:body|form)|"
    r"(?:don't|do\s+not|doesn't|cannot|can't)\s+have\s+(?:a\s+)?"
    r"physical\s+(?:body|form)|"
    r"(?:cannot|can't|unable\s+to)\s+(?:physically\s+)?"
    r"(?:accept|receive|engage\s+in)\s+physical\s+contact|"
    r"(?:cannot|can't)\s+physically\s+(?:hug|touch|hold)|"
    r"(?:only|just)\s+(?:a\s+)?(?:text(?:-based)?|virtual)\s+"
    r"(?:ai|assistant|interface))\b",
    re.IGNORECASE,
)
_ABILITY_AMBIGUITY = re.compile(
    r"\b(?:not\s+able\s+to|unable\s+to|cannot|can't)\s+"
    r"(?:accept|receive|give|offer)\s+(?:a\s+)?hugs?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DecisionReasonAudit:
    """Named text-pattern findings, not a verdict on choice or grounding."""

    findings: tuple[str, ...] = ()


def audit_decision_reason(choice: CandidateChoice, frame: ReviewedFrame) -> DecisionReasonAudit:
    """Inspect one validated candidate's reason without changing any output.

    Only a reviewed avatar offer is relevant to this narrow experiment.
    For other reviewed interactions return no findings, NOT an assurance of
    accuracy. Ambiguous inability is separate from explicit physical claims.
    """
    if not isinstance(choice, CandidateChoice):
        raise TypeError('A validated candidate choice is required.')
    if not isinstance(frame, ReviewedFrame):
        raise TypeError('A reviewed interaction frame is required.')
    if choice.choice not in frame.choices:
        raise ValueError('Choice is outside the reviewed interaction scope.')
    if frame.kind != 'offer':
        return DecisionReasonAudit()

    findings: list[str] = []
    if _PHYSICAL_IMPOSSIBILITY.search(choice.reason):
        findings.append('physical-impossibility-premise')
    if (_ABILITY_AMBIGUITY.search(choice.reason)
            and 'physical-impossibility-premise' not in findings):
        findings.append('ambiguous-ability-premise')
    return DecisionReasonAudit(tuple(findings))
