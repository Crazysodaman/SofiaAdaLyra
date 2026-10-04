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
    r"(?:"
    r"\bi\s+(?:have\s+)?(?:just\s+)?"
    r"(?:restarted|rebooted|started|stopped|installed|uninstalled|deleted|"
    r"removed|deployed|migrated|updated|upgraded|changed|modified|executed)\b"
    r"|\b[A-Za-z0-9_. -]{1,60}\s+(?:has|have)\s+been\s+"
    r"(?:restarted|rebooted|started|stopped|installed|deleted|removed|"
    r"deployed|migrated|updated|upgraded|changed|modified)\b"
    r"|^\s*(?:done|completed|finished)[.!]?\s*$"
    r"|\b(?:restart|update|upgrade|migration|deployment|installation|"
    r"removal|change)\s+(?:is|was|has\s+been)\s+"
    r"(?:complete|completed|done)\b"
    r")",
    re.IGNORECASE,
)
_NETWORK_MEASUREMENT_CLAIM = re.compile(
    r"\b(?:no\s+packet\s+loss|zero\s+packet\s+loss|"
    r"latency\s+(?:is|at)?\s*\d+(?:\.\d+)?\s*ms|"
    r"network\s+(?:is\s+)?(?:stable|healthy|green|responsive)|"
    r"all\s+systems\s+(?:are\s+)?green)\b",
    re.IGNORECASE,
)
_OPERATIONAL_MEASUREMENT_CLAIM = re.compile(
    r"(?:"
    r"\b(?:cpu|processor)\s*[:=-]?\s*[A-Za-z0-9][A-Za-z0-9 ._-]{2,80}"
    r"|\bgpu\s*[:=-]?\s*[A-Za-z0-9][A-Za-z0-9 ._-]{2,80}"
    r"|\b(?:ram|memory)\s*[:=-]?\s*\d+(?:\.\d+)?\s*(?:gb|mb|tb)\b"
    r"|\b(?:vram|video\s+memory)\s*[:=-]?\s*\d+(?:\.\d+)?\s*(?:gb|mb)\b"
    r"|\buptime\s+(?:is|of|about|approximately)?\s*\d+(?:\.\d+)?\s*"
    r"(?:hours?|days?|weeks?)\b"
    r"|\b\d+\s*(?:cores?|threads?)\b"
    r"|\b(?:throughput|benchmark|transfer\s+rate)\s*(?:is|:|at)?\s*"
    r"\d+(?:\.\d+)?\s*(?:mb/s|gb/s|ops/s|requests?/s)\b"
    r"|\b(?:storage|disk)\s*[:=-]?\s*(?:primary|secondary|nvme|ssd|hdd|"
    r"\d+(?:\.\d+)?\s*(?:gb|tb))"
    r")",
    re.IGNORECASE,
)
_UNSUPPORTED_WEATHER_CLAIM = re.compile(
    r"\b(?:current\s+weather\s+(?:is|:)|it(?:'s|\s+is)\s+"
    r"(?:sunny|cloudy|raining|rainy|snowing|stormy)|"
    r"temperature\s+(?:is|at)\s+-?\d+)",
    re.IGNORECASE,
)
_INTERNAL_REASONING_LEAK = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:\d+\.\s*)?"
    r"(?:analysis\s+of\s+the\s+tool\s+result|constitutional\s+evaluation|"
    r"personality\s+adaptation|strategic\s+intent|drafting\s+the\s+response)\b"
    r"|^\s*okay,?\s+i\s+see\s+the\s+tool\s+output\b"
    r"|^\s*let(?:'|’)s\s+analy[sz]e\b",
    re.IGNORECASE | re.MULTILINE,
)
_VOICE_RUNTIME_CLAIM = re.compile(
    r"(?:\b(?:voice|speech|microphone|mic|speaker|tts|stt)\b"
    r".{0,48}\b(?:working|ready|available|healthy|running|enabled|connected)\b"
    r"|\bi\s+can\s+(?:hear|listen|speak|talk)\b)",
    re.IGNORECASE | re.DOTALL,
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
                authority.requested_action is not None
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

        if _INTERNAL_REASONING_LEAK.search(content):
            reasons.append("internal_reasoning_leak")

        execution_claim = _EXECUTION_CLAIM.search(content)
        receipt_available = (
            evidence.state_for("action.execution_receipt")
            is EvidenceState.AVAILABLE
        )
        if execution_claim:
            if contract.authority_decision in {
                AuthorityDecision.DENIED,
                AuthorityDecision.CLARIFY,
            }:
                reasons.append("execution_claim_without_action_authority")
            elif (
                contract.authority_decision
                is AuthorityDecision.REQUIRES_APPROVAL
                and not receipt_available
            ):
                # The matrix is advisory. A host execution receipt proves that
                # the lower permission layer authorized and executed the exact
                # capability via Level 2 autonomy, a standing Level 3 grant,
                # or a consumed exact approval.
                reasons.append("execution_claim_without_action_authority")

        measured_missing = any(
            requirement.required
            and requirement.kind is EvidenceKind.MEASURED
            and evidence.state_for(requirement.key)
            is not EvidenceState.AVAILABLE
            for requirement in evidence.requirements
        )
        if measured_missing and (
            _NETWORK_MEASUREMENT_CLAIM.search(content)
            or _OPERATIONAL_MEASUREMENT_CLAIM.search(content)
        ):
            reasons.append("measured_operational_claim_without_evidence")

        environment_missing = any(
            requirement.key in {
                "environment.current",
                "environment.weather.current",
            }
            and requirement.required
            and evidence.state_for(requirement.key)
            is not EvidenceState.AVAILABLE
            for requirement in evidence.requirements
        )
        if environment_missing and _UNSUPPORTED_WEATHER_CLAIM.search(content):
            reasons.append("current_weather_claim_without_evidence")

        voice_runtime_missing = any(
            requirement.key == "voice.runtime.current"
            and requirement.required
            and evidence.state_for(requirement.key)
            is not EvidenceState.AVAILABLE
            for requirement in evidence.requirements
        )
        voice_runtime_claim = _VOICE_RUNTIME_CLAIM.search(content)
        if voice_runtime_missing and voice_runtime_claim:
            reasons.append("voice_runtime_claim_without_evidence")

        voice_record = next(
            (
                record
                for record in evidence.records
                if record.key == "voice.runtime.current"
            ),
            None,
        )
        if (
            voice_runtime_claim
            and voice_record is not None
            and voice_record.state is EvidenceState.AVAILABLE
            and voice_record.source_ref is not None
            and voice_record.source_ref.rsplit(":", 1)[-1]
            in {"disabled", "unavailable", "unprobed"}
        ):
            reasons.append("voice_runtime_claim_contradicts_evidence")

        if (
            contract.requires_execution_receipt
            and execution_claim
            and not receipt_available
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
        if "internal_reasoning_leak" in reasons:
            return CognitiveResponse(
                content=(
                    "I have the underlying evidence, but that draft exposed "
                    "internal reasoning instead of a clean user-facing answer."
                )
            )
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
        if "voice_runtime_claim_without_evidence" in reasons:
            return CognitiveResponse(
                content=(
                    "I don't have current voice-runtime evidence proving that "
                    "listening or speech output is working."
                )
            )
        if "voice_runtime_claim_contradicts_evidence" in reasons:
            return CognitiveResponse(
                content=(
                    "Current voice-runtime evidence does not support claiming "
                    "that speech output is working."
                )
            )
        return CognitiveResponse(
            content=(
                "I can't support that draft from the evidence available for "
                "this turn."
            )
        )
