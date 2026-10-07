"""Response contracts and evidence/authority validation."""
from __future__ import annotations

import re

from sofia.cognition.model import CognitiveResponse
from sofia.cognition.output_guard import contains_internal_reasoning_leak
from .visibility import asks_about_machine_visibility

from .model import (
    AuthorityDecision,
    AuthorityPlan,
    EvidenceKind,
    EvidenceMatrix,
    EvidenceState,
    MatrixDomain,
    MatrixRelevance,
    ResponseContract,
    ResponseValidation,
    ResponseValidationDisposition,
    TurnMatrix,
)


_TECHNICAL_TOPIC_ANCHORS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("source-file", re.compile(r"\b[\w.-]+\.(?:py|js|ts|java|rs|go)\b", re.I)),
    ("test-runner", re.compile(r"\b(?:pytest|unittest|test\s+suite)\b", re.I)),
    (
        "schema",
        re.compile(
            r"\b(?:database\s+schema|json\s+schema|schema\s+migration)\b",
            re.I,
        ),
    ),
    (
        "debugging",
        re.compile(r"\b(?:stack\s+trace|timeout\s+debugging|debugger)\b", re.I),
    ),
    (
        "implementation",
        re.compile(
            r"\b(?:goal\s+implementation|provider\s+architecture|source\s+code)\b",
            re.I,
        ),
    ),
)

# Named-host absence/presence is not established by local machine inspection.
# A successful Fleet inventory query is the minimum evidence for such a claim;
# it still does not prove agent connectivity or that every possible host exists.
_NAMED_HOST_SCOPE_ASSERTION = re.compile(
    r"\b(?:i\s+(?:can(?:not|['’]t)|do\s+not|don['’]t|can|do)\s+"
    r"(?:see|find|reach|access)\b"
    r"|nothing\s+(?:called|named)\b"
    r"|no\s+(?:computer|machine|server|host|node)\s+"
    r"(?:called|named|registered)\b"
    r"|(?:isn't|is\s+not|aren't|are\s+not)\s+(?:in|on)\s+"
    r"(?:my|our|the|this)\s+(?:fleet|scope|inventory)\b"
    r"|\b(?:is|isn't|is\s+not)\s+(?:registered|reachable|connected)\b"
    r"|stuck\s+to\s+(?:this|that|a|the)\s+single\s+"
    r"(?:os|machine|host)\b)",
    re.IGNORECASE,
)
_FLEET_EVIDENCE_REFS = frozenset({
    "capability:ops.fleet.list",
    "capability:ops.fleet.get",
    "capability:remote.nodes",
})


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
_VOICE_RUNTIME_CLAIM = re.compile(
    r"(?:\b(?:voice|speech|microphone|mic|speaker|tts|stt)\b"
    r".{0,48}\b(?:working|ready|available|healthy|running|enabled|connected)\b"
    r"|\b(?:voice|audio|speech|microphone|mic|speaker|tts|stt)\b"
    r".{0,48}\b(?:lost|dropped|disconnected|unavailable|failed|offline)\b"
    r"|\bi\s+can\s+(?:hear|listen|speak|talk)\b)",
    re.IGNORECASE | re.DOTALL,
)
_MACHINERY_METAPHOR = re.compile(
    r"\b(?:kernel|circuit(?:s)?|processor|cpu|diagnostic(?:s)?|reboot(?:ing|ed)?|"
    r"diagnostic\s+cycle|background\s+monitoring(?:\s+loop)?|link\s+integrity|"
    r"system\s+link|data\s+link|connection\s+protocol|emotional\s+firewall|"
    r"audio\s+feed|subroutine|firmware|telemetry|sensor\s+node|bandwidth|"
    r"subsystem|servo(?:s)?|actuator(?:s)?|cooling\s+fan(?:s)?)\b",
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
        *,
        turn: TurnMatrix | None = None,
        retained_user_context: str = "",
    ) -> ResponseValidation:
        if not isinstance(response, CognitiveResponse):
            raise TypeError("response must be CognitiveResponse")
        if not isinstance(contract, ResponseContract):
            raise TypeError("contract must be ResponseContract")
        if not isinstance(evidence, EvidenceMatrix):
            raise TypeError("evidence must be EvidenceMatrix")
        if turn is not None and not isinstance(turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix or None")
        if not isinstance(retained_user_context, str):
            raise TypeError("retained_user_context must be str")

        content = response.content.strip()
        reasons: list[str] = []

        if contains_internal_reasoning_leak(content):
            reasons.append("internal_reasoning_leak")

        # This is deliberately a gross-drift check, not a ban on technical
        # vocabulary. A single nerdy joke remains valid personality. Two or
        # more unrelated, concrete implementation-topic groups in a social or
        # avatar response indicate that the model answered leaked context.
        if turn is not None:
            active_domains = {
                item.domain for item in turn.domains
                if item.relevance is not MatrixRelevance.NONE
            }
            social_turn = bool(active_domains & {
                MatrixDomain.SOCIAL,
                MatrixDomain.AVATAR,
                MatrixDomain.INTERACTION,
            })
            technical_turn = bool(active_domains & {
                MatrixDomain.DEV,
                MatrixDomain.OPS,
                MatrixDomain.COGNITION,
                MatrixDomain.MACHINE,
                MatrixDomain.INTEGRATE,
            })
            response_topics = {
                name for name, pattern in _TECHNICAL_TOPIC_ANCHORS
                if pattern.search(content)
            }
            retained_topics = {
                name for name, pattern in _TECHNICAL_TOPIC_ANCHORS
                if pattern.search(retained_user_context)
            }
            if (
                social_turn
                and not technical_turn
                and len(response_topics - retained_topics) >= 2
            ):
                reasons.append("gross_domain_drift")
            if social_turn and not technical_turn:
                metaphor_terms = {
                    match.group(0).casefold()
                    for match in _MACHINERY_METAPHOR.finditer(content)
                }
                if len(metaphor_terms) >= 2:
                    reasons.append("social_machinery_metaphor_stack")

        if (
            turn is not None
            and any(
                asks_about_machine_visibility(line.strip())
                for line in retained_user_context.splitlines()
            )
            and _NAMED_HOST_SCOPE_ASSERTION.search(content)
            and not _FLEET_EVIDENCE_REFS.intersection(response.evidence_refs)
        ):
            reasons.append("fleet_visibility_claim_without_fleet_evidence")

        if contract.require_grounded_claims:
            for requirement in evidence.missing_required:
                reasons.append(
                    "required_evidence_unavailable:" + requirement.key
                )

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
        if (
            voice_runtime_claim
            and turn is not None
            and turn.relevance_for(MatrixDomain.VOICE) is MatrixRelevance.NONE
        ):
            reasons.append("voice_runtime_claim_outside_context")
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
        if "fleet_visibility_claim_without_fleet_evidence" in reasons:
            return CognitiveResponse(
                content=(
                    "I haven't verified that machine against current Fleet "
                    "inventory. Local host details don't establish whether "
                    "the remote machine is registered or reachable."
                )
            )
        if "gross_domain_drift" in reasons:
            return CognitiveResponse(
                content=(
                    "That draft drifted into unrelated implementation details. "
                    "I'll answer the current conversation instead."
                )
            )
        if "social_machinery_metaphor_stack" in reasons:
            return CognitiveResponse(
                content=(
                    "I'm doing okay—present, a little foxish, and glad you asked."
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
        if "voice_runtime_claim_outside_context" in reasons:
            return CognitiveResponse(
                content=(
                    "That voice or audio-state claim is unrelated to the current "
                    "grounded context, so I won't present it as runtime fact."
                )
            )
        if "voice_runtime_claim_contradicts_evidence" in reasons:
            return CognitiveResponse(
                content=(
                    "Current voice-runtime evidence does not support claiming "
                    "that speech output is working."
                )
            )
        if "required_evidence_unavailable:memory.retrieval" in reasons:
            return CognitiveResponse(
                content=(
                    "I don't have retrieved memory evidence supporting an "
                    "answer to that, so I won't invent a memory."
                )
            )
        if "required_evidence_unavailable:environment.weather.current" in reasons:
            return CognitiveResponse(
                content=(
                    "I don't have current weather evidence, so I can't ground "
                    "how it affects my expression right now."
                )
            )
        if any(
            reason.startswith("required_evidence_unavailable:")
            for reason in reasons
        ):
            return CognitiveResponse(
                content=(
                    "I don't have the required grounded evidence for that "
                    "current-state answer, so I won't invent it."
                )
            )
        return CognitiveResponse(
            content=(
                "I can't support that draft from the evidence available for "
                "this turn."
            )
        )
