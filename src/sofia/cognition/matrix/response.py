"""Response contracts and evidence/authority validation."""
from __future__ import annotations

import re

from sofia.cognition.model import CognitiveResponse

from .model import (
    AuthorityDecision,
    AuthorityPlan,
    EvidenceKind,
    EvidenceMatrix,
    EvidenceState,
    ResponseContract,
    ResponseValidation,
    ResponseValidationDisposition,
    TurnMatrix,
)


_EXECUTION_CLAIM = re.compile(
    r"\b(?:i\s+(?:have\s+)?(?:restarted|rebooted|started|stopped|installed|"
    r"uninstalled|deleted|removed|deployed|migrated|updated|upgraded|changed|"
    r"modified|executed)|(?:done|completed|finished)\b|"
    r"(?:has|have)\s+been\s+(?:restarted|rebooted|started|stopped|installed|"
    r"deleted|removed|deployed|migrated|updated|changed|modified))",
    re.IGNORECASE,
)
_NETWORK_MEASUREMENT_CLAIM = re.compile(
    r"\b(?:no\s+packet\s+loss|zero\s+packet\s+loss|"
    r"latency\s+(?:is|at)?\s*\d+(?:\.\d+)?\s*ms|"
    r"network\s+(?:is\s+)?(?:stable|healthy|green|responsive)|"
    r"all\s+systems\s+(?:are\s+)?green)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_WEATHER_CLAIM = re.compile(
    r"\b(?:current\s+weather\s+(?:is|:)|it(?:'s|\s+is)\s+"
    r"(?:sunny|cloudy|raining|rainy|snowing|stormy)|"
    r"temperature\s+(?:is|at)\s+-?\d+)",
    re.IGNORECASE,
)


class MatrixResponsePlanner:
    def plan(
        self,
        turn: TurnMatrix,
        evidence: EvidenceMatrix,
        authority: AuthorityPlan,
    ) -> ResponseContract:
        if not isinstance(turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix")
        if not isinstance(evidence, EvidenceMatrix):
            raise TypeError("evidence must be EvidenceMatrix")
        if not isinstance(authority, AuthorityPlan):
            raise TypeError("authority must be AuthorityPlan")

        return ResponseContract(
            require_grounded_claims=True,
            prohibited_claims=(),
            requires_execution_receipt=(
                authority.decision is AuthorityDecision.ALLOWED
                and authority.requested_action is not None
            ),
            authority_decision=authority.decision,
        )


class MatrixResponseValidator:
    """Validate claims against host evidence and action authority."""

    def validate(
        self,
        response: CognitiveResponse,
        contract: ResponseContract,
        evidence: EvidenceMatrix,
    ) -> ResponseValidation:
        if not isinstance(response, CognitiveResponse):
            raise TypeError("response must be CognitiveResponse")
        if not isinstance(contract, ResponseContract):
            raise TypeError("contract must be ResponseContract")
        if not isinstance(evidence, EvidenceMatrix):
            raise TypeError("evidence must be EvidenceMatrix")

        content = response.content.strip()
        reasons: list[str] = []

        if (
            contract.authority_decision
            in {
                AuthorityDecision.REQUIRES_APPROVAL,
                AuthorityDecision.DENIED,
                AuthorityDecision.CLARIFY,
            }
            and _EXECUTION_CLAIM.search(content)
        ):
            reasons.append("execution_claim_without_action_authority")

        measured_missing = any(
            requirement.required
            and requirement.kind is EvidenceKind.MEASURED
            and evidence.state_for(requirement.key)
            is not EvidenceState.AVAILABLE
            for requirement in evidence.requirements
        )
        if measured_missing and _NETWORK_MEASUREMENT_CLAIM.search(content):
            reasons.append("measured_operational_claim_without_evidence")

        environment_missing = (
            any(
                requirement.key == "environment.current"
                and requirement.required
                and evidence.state_for(requirement.key)
                is not EvidenceState.AVAILABLE
                for requirement in evidence.requirements
            )
        )
        if environment_missing and _UNSUPPORTED_WEATHER_CLAIM.search(content):
            reasons.append("current_weather_claim_without_evidence")

        if (
            contract.requires_execution_receipt
            and _EXECUTION_CLAIM.search(content)
            and evidence.state_for("action.execution_receipt")
            is not EvidenceState.AVAILABLE
        ):
            reasons.append("execution_claim_without_receipt")

        for claim in contract.prohibited_claims:
            if claim.casefold() in content.casefold():
                reasons.append(f"prohibited_claim:{claim}")

        if reasons:
            return ResponseValidation(
                ResponseValidationDisposition.RETRY,
                tuple(dict.fromkeys(reasons)),
            )
        return ResponseValidation(ResponseValidationDisposition.PASS)

    def fallback(
        self,
        validation: ResponseValidation,
        contract: ResponseContract,
    ) -> CognitiveResponse:
        reasons = set(validation.reasons)
        if "execution_claim_without_action_authority" in reasons:
            if contract.authority_decision is AuthorityDecision.CLARIFY:
                return CognitiveResponse(
                    content=(
                        "I need the target clarified before treating that as "
                        "an action. Nothing has been executed."
                    )
                )
            if contract.authority_decision is AuthorityDecision.REQUIRES_APPROVAL:
                return CognitiveResponse(
                    content=(
                        "I can plan or propose that action, but I don't have "
                        "authority to claim it was executed without approval "
                        "and execution evidence."
                    )
                )
            return CognitiveResponse(
                content=(
                    "I don't have authority to execute or claim completion "
                    "of that action."
                )
            )
        if "execution_claim_without_receipt" in reasons:
            return CognitiveResponse(
                content=(
                    "I don't have an execution receipt proving that action "
                    "completed, so I won't claim that it did."
                )
            )
        if "measured_operational_claim_without_evidence" in reasons:
            return CognitiveResponse(
                content=(
                    "I don't have the required current measurement evidence "
                    "to make that operational claim."
                )
            )
        if "current_weather_claim_without_evidence" in reasons:
            return CognitiveResponse(
                content=(
                    "I don't have current weather evidence for that claim."
                )
            )
        return CognitiveResponse(
            content=(
                "I can't support that draft from the evidence available for "
                "this turn."
            )
        )
