"""Conversation-specific cognition matrix planning, evidence, and validation."""
from __future__ import annotations

from datetime import datetime, timezone

from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
    CognitiveResponse,
)
from sofia.cognition.matrix import (
    AuthorityDecision,
    AuthorityPlan,
    CognitionExecutionStep,
    CognitionExecutionTrace,
    ContextPlan,
    EvidenceMatrix,
    EvidenceRecord,
    EvidenceState,
    HistoryPolicy,
    MatrixAuthorityPlanner,
    MatrixContextPlanner,
    MatrixCoordinator,
    MatrixDomain,
    MatrixEvidencePlanner,
    MatrixEvidenceResolver,
    MatrixResponsePlanner,
    MatrixResponseValidator,
    MatrixIntent,
    MatrixRelevance,
    MatrixRoute,
    MatrixRoutingPlanner,
    MatrixPrivacyPlanner,
    MatrixToolExposurePlanner,
    MatrixTrace,
    MatrixTraceStore,
    ResponseContract,
    ResponseStrategy,
    ResponseValidation,
    ResponseValidationDisposition,
    RoutingPlan,
    PrivacyProjectionPlan,
    ToolExposurePlan,
    TurnEnvelope,
    TurnMatrix,
)
from sofia.cognition.matrix.defaults import default_matrix_registry
from sofia.social.model import PrincipalContext
from sofia.voice.tts import TTSStatus


def _matrix_context_window(
    messages: tuple[ConversationMessage, ...],
    plan: ContextPlan,
    *,
    domain_lookup=None,
    current_message_id: str | None = None,
) -> tuple[ConversationMessage, ...]:
    """Apply typed history limits and domain eligibility to provider context.

    When matrix trace lookup is available, prior user/assistant exchanges are
    retained only when the originating user turn overlaps the current
    ContextPlan. The current user message is always retained.
    """
    if not isinstance(plan, ContextPlan):
        raise TypeError("plan must be ContextPlan")
    if not messages:
        return ()

    bounded = messages[-plan.max_history_messages:]
    if (
        domain_lookup is None
        or plan.history_policy in {
            HistoryPolicy.NONE,
            HistoryPolicy.RETRIEVE_SPECIFIC,
        }
    ):
        return bounded

    current_id = current_message_id or bounded[-1].id
    visible: list[ConversationMessage] = []
    prior_user_allowed = False

    for message in bounded:
        if message.role is ConversationRole.USER:
            if message.id == current_id:
                prior_user_allowed = True
            else:
                domains = tuple(domain_lookup(message.id))
                prior_user_allowed = any(
                    plan.allows(domain)
                    for domain in domains
                )
            if prior_user_allowed:
                visible.append(message)
            continue

        if (
            message.role is ConversationRole.ASSISTANT
            and prior_user_allowed
        ):
            visible.append(message)

    return tuple(visible)


def _inherit_last_turn_domains(
    turn: TurnMatrix,
    prior_turn: TurnMatrix | None,
) -> TurnMatrix:
    """Carry prior semantic domains into an explicit LAST_TURN follow-up.

    Inherited domains are contextual only. They provide topic continuity
    without manufacturing evidence, authority, or action permission.
    """
    if not isinstance(turn, TurnMatrix):
        raise TypeError("turn must be TurnMatrix")
    if prior_turn is not None and not isinstance(prior_turn, TurnMatrix):
        raise TypeError("prior_turn must be TurnMatrix or None")
    if (
        prior_turn is None
        or turn.history_policy is not HistoryPolicy.LAST_TURN
    ):
        return turn

    domains = {item.domain: item for item in turn.domains}
    for item in prior_turn.domains:
        if item.domain in domains:
            continue
        domains[item.domain] = type(item)(
            domain=item.domain,
            relevance=MatrixRelevance.CONTEXTUAL,
            reason="inherited from the immediately preceding matrix turn",
        )

    return TurnMatrix(
        intent=turn.intent,
        confidence=turn.confidence,
        history_policy=turn.history_policy,
        response_strategy=turn.response_strategy,
        domains=tuple(
            domains[key]
            for key in sorted(domains, key=lambda domain: domain.value)
        ),
        ambiguous=turn.ambiguous,
        schema_version=turn.schema_version,
    )


class ConversationMatrixMixin:
    """Matrix planning/trace/validation support for conversation services."""

    def _initialize_matrix_state(self) -> None:
        self._matrix_coordinator = MatrixCoordinator(
            registry=default_matrix_registry()
        )
        self._matrix_context_planner = MatrixContextPlanner()
        self._matrix_evidence_planner = MatrixEvidencePlanner()
        self._matrix_evidence_resolver = MatrixEvidenceResolver()
        self._matrix_authority_planner = MatrixAuthorityPlanner()
        self._matrix_response_planner = MatrixResponsePlanner()
        self._matrix_response_validator = MatrixResponseValidator()
        self._matrix_routing_planner = MatrixRoutingPlanner()
        self._matrix_privacy_planner = MatrixPrivacyPlanner()
        self._matrix_tool_exposure_planner = MatrixToolExposurePlanner()
        self._matrix_trace_store: MatrixTraceStore | None = None
        self._current_matrix_message_id: str | None = None
        self._current_matrix_envelope: TurnEnvelope | None = None
        self._current_turn_matrix: TurnMatrix | None = None
        self._current_context_plan: ContextPlan | None = None
        self._current_evidence_matrix: EvidenceMatrix | None = None
        self._current_authority_plan: AuthorityPlan | None = None
        self._current_privacy_plan: PrivacyProjectionPlan | None = None
        self._current_tool_exposure_plan: ToolExposurePlan | None = None
        self._current_response_contract: ResponseContract | None = None
        self._current_response_validation: ResponseValidation | None = None
        self._current_routing_plan: RoutingPlan | None = None
        self._current_cognition_execution: CognitionExecutionTrace | None = None
        self._current_contextual_influence = None
        self._matrix_execution_baseline_serial = 0
        self._last_matrix_error: str | None = None

    def _open_matrix_trace_store(self) -> None:
        self._matrix_trace_store = MatrixTraceStore(
            self._runtime.configuration.state_path
        )

    def _voice_runtime_status(self) -> TTSStatus | None:
        provider = getattr(self, "_voice_runtime_provider", None)
        if provider is None:
            return None
        try:
            status = provider()
        except Exception:
            return None
        return status if isinstance(status, TTSStatus) else None

    def _matrix_voice_evidence(
        self,
    ) -> dict[str, EvidenceRecord | EvidenceState]:
        status = self._voice_runtime_status()
        if status is None:
            return {}
        return {
            "voice.runtime.current": EvidenceRecord(
                "voice.runtime.current",
                EvidenceState.AVAILABLE,
                status.evidence_ref,
            )
        }

    def _matrix_voice_context_messages(
        self,
    ) -> tuple[CognitiveMessage, ...]:
        context = getattr(self, "_current_context_plan", None)
        if context is None or not context.allows(MatrixDomain.VOICE):
            return ()
        status = self._voice_runtime_status()
        if status is None:
            return ()
        return (
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content=status.prompt(),
            ),
        )

    def _matrix_person_scoped_evidence(
        self,
        *,
        principal: PrincipalContext | None,
        current_message_id: str,
    ) -> dict[str, EvidenceRecord]:
        """Resolve REL/HABIT evidence only from authenticated scoped stores."""
        result: dict[str, EvidenceRecord] = {}
        if principal is None:
            return result

        history = tuple(
            item
            for item in self._relationship_store.history(
                principal.principal_id
            )
            if (
                item.evidence_ref != current_message_id
                and item.principal_id == principal.principal_id
                and item.audience_id == principal.audience_id
            )
        )
        result["relationship.prior_contact"] = (
            EvidenceRecord(
                "relationship.prior_contact",
                EvidenceState.MISSING,
            )
            if not history
            else EvidenceRecord(
                "relationship.prior_contact",
                EvidenceState.AVAILABLE,
                history[-1].evidence_ref,
            )
        )

        habit = getattr(self, "_habit_continuity", None)
        patterns = ()
        if habit is not None:
            patterns = habit.patterns.patterns(
                principal_id=principal.principal_id,
                audience_id=principal.audience_id,
            )
        strongest = (
            None
            if not patterns
            else max(
                patterns,
                key=lambda item: (
                    item.confidence,
                    item.last_seen,
                    item.pattern_id,
                ),
            )
        )
        result["habit.patterns"] = (
            EvidenceRecord(
                "habit.patterns",
                EvidenceState.MISSING,
            )
            if strongest is None
            else EvidenceRecord(
                "habit.patterns",
                EvidenceState.AVAILABLE,
                f"habit-pattern:{strongest.pattern_id}",
            )
        )
        return result

    def _matrix_person_scoped_context_messages(
        self,
        *,
        current_user: ConversationMessage | None,
    ) -> tuple[CognitiveMessage, ...]:
        """Project bounded REL/HABIT context under the matrix privacy plan."""
        if (
            current_user is None
            or self._session is None
            or self._current_context_plan is None
            or self._current_privacy_plan is None
        ):
            return ()

        principal = self._social_store.get(self._session.id)
        if principal is None:
            return ()

        context_plan = self._current_context_plan
        privacy = self._current_privacy_plan
        messages: list[CognitiveMessage] = []

        if (
            context_plan.allows(MatrixDomain.REL)
            and privacy.allow_relationship_scope
        ):
            history = tuple(
                item
                for item in self._relationship_store.history(
                    principal.principal_id
                )
                if (
                    item.evidence_ref != current_user.id
                    and item.principal_id == principal.principal_id
                    and item.audience_id == principal.audience_id
                )
            )
            if history:
                previous = history[-1]
                messages.append(
                    CognitiveMessage(
                        role=CognitiveRole.SYSTEM,
                        content=(
                            "TRUSTED RELATIONSHIP CONTACT EVIDENCE\n"
                            "This is principal-bound observed contact evidence, "
                            "not a feeling, preference, or permission grant.\n"
                            f"Previous observed contact: {previous.occurred_at.isoformat()}\n"
                            f"Evidence ref: {previous.evidence_ref}\n"
                            "The current user turn is the current contact and is "
                            "intentionally excluded from 'previous contact'. "
                            "Do not invent contact during unobserved time."
                        ),
                    )
                )

        if (
            context_plan.allows(MatrixDomain.HABIT)
            and privacy.allow_audience_scope
        ):
            habit = getattr(self, "_habit_continuity", None)
            if habit is not None:
                patterns = habit.patterns.patterns(
                    principal_id=principal.principal_id,
                    audience_id=principal.audience_id,
                )
                ranked = tuple(sorted(
                    patterns,
                    key=lambda item: (
                        -item.confidence,
                        -item.support_count,
                        item.pattern_id,
                    ),
                ))[:8]
                if ranked:
                    lines = [
                        "TRUSTED HABIT PATTERN EVIDENCE",
                        (
                            "These are principal/audience-scoped learned "
                            "patterns, not commands or guaranteed facts. "
                            "Tentative patterns must not be described as "
                            "established routines."
                        ),
                    ]
                    for item in ranked:
                        context = ", ".join(
                            f"{key}={value}"
                            for key, value in sorted(item.context.items())
                            if key != "observation_kind"
                        ) or "no-context"
                        lines.append(
                            "- "
                            f"id={item.pattern_id}; "
                            f"category={item.category.value}; "
                            f"cadence={item.cadence.value}; "
                            f"lifecycle={item.lifecycle.value}; "
                            f"confidence={item.confidence:.4f}; "
                            f"support={item.support_count}; "
                            f"context={context}"
                        )
                    messages.append(
                        CognitiveMessage(
                            role=CognitiveRole.SYSTEM,
                            content="\n".join(lines),
                        )
                    )

        return tuple(messages)

    def _matrix_domains_for_message(
        self,
        message_id: str,
    ) -> tuple[MatrixDomain, ...]:
        """Return traced semantic domains for a prior user message."""
        if not isinstance(message_id, str) or not message_id.strip():
            raise ValueError("message_id must be nonempty")
        store = getattr(self, "_matrix_trace_store", None)
        if store is None:
            return ()
        trace = store.get(message_id)
        if trace is None:
            return ()
        return tuple(
            item.domain
            for item in trace.turn.domains
            if item.relevance is not MatrixRelevance.NONE
        )

    def _record_shadow_matrix(
        self,
        *,
        message: ConversationMessage,
        principal: PrincipalContext | None,
        channel: str,
    ) -> None:
        """Plan the turn matrix and persist a provisional pre-response trace."""
        self._current_matrix_message_id = None
        self._current_matrix_envelope = None
        self._current_turn_matrix = None
        self._current_context_plan = None
        self._current_evidence_matrix = None
        self._current_authority_plan = None
        self._current_privacy_plan = None
        self._current_tool_exposure_plan = None
        self._current_response_contract = None
        self._current_response_validation = None
        self._current_routing_plan = None
        self._current_cognition_execution = None
        self._current_contextual_influence = None
        execution_reader = getattr(
            self._runtime,
            "cognition_routing_execution",
            None,
        )
        prior_execution = (
            execution_reader()
            if callable(execution_reader)
            else None
        )
        self._matrix_execution_baseline_serial = (
            0 if prior_execution is None else prior_execution.serial
        )
        store = getattr(self, "_matrix_trace_store", None)
        if store is None:
            return
        try:
            envelope = TurnEnvelope(
                message_id=message.id,
                session_id=message.session_id,
                content=message.content,
                created_at=message.created_at,
                principal_id=(
                    None if principal is None else principal.principal_id
                ),
                channel=channel,
            )
            turn = self._matrix_coordinator.evaluate(envelope)
            prior_trace = store.latest(session_id=message.session_id)
            turn = _inherit_last_turn_domains(
                turn,
                None if prior_trace is None else prior_trace.turn,
            )
            context_plan = self._matrix_context_planner.plan(turn)
            evidence_requirements = self._matrix_evidence_planner.plan(
                turn,
                envelope,
            )
            availability = self._runtime.matrix_evidence_availability(
                required_keys=tuple(
                    item.key
                    for item in evidence_requirements.requirements
                )
            )
            availability.update(
                self._matrix_person_scoped_evidence(
                    principal=principal,
                    current_message_id=message.id,
                )
            )
            availability.update(
                self._matrix_voice_evidence()
            )
            evidence = self._matrix_evidence_resolver.resolve(
                evidence_requirements,
                availability,
            )
            authority_plan = self._matrix_authority_planner.plan(
                envelope,
                turn,
                self._runtime.current_authority(),
            )
            privacy_plan = self._matrix_privacy_planner.plan(principal)
            tool_exposure_plan = self._matrix_tool_exposure_planner.plan(
                envelope,
                turn,
                authority_plan,
            )
            response_contract = self._matrix_response_planner.plan(
                turn,
                evidence,
                authority_plan,
            )
            routing_plan = self._matrix_routing_planner.plan(
                envelope,
                turn,
            )
            store.record(
                MatrixTrace(
                    envelope=envelope,
                    turn=turn,
                    context=context_plan,
                    evidence=evidence,
                    authority=authority_plan,
                    privacy=privacy_plan,
                    tool_exposure=tool_exposure_plan,
                    response_contract=response_contract,
                    routing=routing_plan,
                    created_at=datetime.now(timezone.utc),
                    shadow=True,
                    context_active=True,
                )
            )
            self._current_matrix_message_id = message.id
            self._current_matrix_envelope = envelope
            self._current_turn_matrix = turn
            self._current_context_plan = context_plan
            self._current_evidence_matrix = evidence
            self._current_authority_plan = authority_plan
            self._current_privacy_plan = privacy_plan
            self._current_tool_exposure_plan = tool_exposure_plan
            self._current_response_contract = response_contract
            self._current_routing_plan = routing_plan
            self._last_matrix_error = None
        except Exception as exc:
            # Matrix telemetry/context failure must never make chat unavailable.
            self._current_matrix_message_id = None
            self._current_matrix_envelope = None
            self._current_turn_matrix = None
            self._current_context_plan = None
            self._current_evidence_matrix = None
            self._current_authority_plan = None
            self._current_privacy_plan = None
            self._current_tool_exposure_plan = None
            self._current_response_contract = None
            self._current_response_validation = None
            self._current_routing_plan = None
            self._current_cognition_execution = None
            self._last_matrix_error = type(exc).__name__

    def _record_current_matrix_trace(self) -> None:
        store = getattr(self, "_matrix_trace_store", None)
        if (
            store is None
            or self._current_matrix_envelope is None
            or self._current_turn_matrix is None
        ):
            return
        store.record(
            MatrixTrace(
                envelope=self._current_matrix_envelope,
                turn=self._current_turn_matrix,
                context=self._current_context_plan,
                evidence=self._current_evidence_matrix,
                authority=self._current_authority_plan,
                privacy=self._current_privacy_plan,
                tool_exposure=self._current_tool_exposure_plan,
                response_contract=self._current_response_contract,
                response_validation=self._current_response_validation,
                routing=self._current_routing_plan,
                cognition_execution=self._current_cognition_execution,
                created_at=datetime.now(timezone.utc),
                shadow=False,
                context_active=self._current_context_plan is not None,
            )
        )

    def _capture_cognition_execution(self) -> None:
        execution_reader = getattr(
            self._runtime,
            "cognition_routing_execution",
            None,
        )
        if not callable(execution_reader):
            return
        execution = execution_reader()
        if (
            execution is None
            or execution.serial <= self._matrix_execution_baseline_serial
        ):
            return
        self._current_cognition_execution = CognitionExecutionTrace(
            serial=execution.serial,
            actual_route=execution.route.value,
            steps=tuple(
                CognitionExecutionStep(
                    role=step.role,
                    model=step.model,
                    host=step.host,
                    succeeded=step.succeeded,
                )
                for step in execution.steps
            ),
            fallback_count=execution.fallback_count,
            verification_passes=execution.verification_passes,
        )

    @staticmethod
    def _matrix_request_evidence(
        request: CognitiveRequest | None,
    ) -> dict[str, EvidenceRecord | EvidenceState]:
        if request is None:
            return {}
        if not isinstance(request, CognitiveRequest):
            raise TypeError("request must be CognitiveRequest or None")

        system_text = "\n".join(
            message.content
            for message in request.messages
            if message.role is CognitiveRole.SYSTEM
        )
        availability: dict[str, EvidenceRecord | EvidenceState] = {}

        if any(
            marker in system_text
            for marker in (
                "TRUSTED INTERACTION INTERPRETATION",
                "TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION",
                "TRUSTED BODY INTERACTION CONTROL",
                "TRUSTED REPRESENTATIONAL EXPERIENCE FOLLOW-UP",
                "TRUSTED REPRESENTATIONAL PRESENTATION REQUEST",
            )
        ):
            availability["interaction.interpretation"] = EvidenceRecord(
                "interaction.interpretation",
                EvidenceState.AVAILABLE,
                "request:host-interaction-projection",
            )

        if any(
            marker in system_text
            for marker in (
                "CURRENT MODELED EMOTIONAL STATE",
                "MODELED EMOTIONAL CONTEXT",
            )
        ):
            availability["emotion.current"] = EvidenceRecord(
                "emotion.current",
                EvidenceState.AVAILABLE,
                "request:host-emotion-projection",
            )

        return availability

    def _refresh_matrix_evidence(
        self,
        response: CognitiveResponse,
        request: CognitiveRequest | None = None,
    ) -> None:
        if self._current_evidence_matrix is None:
            return
        availability = self._runtime.matrix_evidence_availability(
            required_keys=tuple(
                item.key
                for item in self._current_evidence_matrix.requirements
            ),
            response=response,
        )
        availability.update(
            self._matrix_request_evidence(request)
        )
        availability.update(
            self._matrix_voice_evidence()
        )
        self._current_evidence_matrix = self._matrix_evidence_resolver.resolve(
            self._current_evidence_matrix,
            availability,
        )
        if (
            self._current_turn_matrix is not None
            and self._current_authority_plan is not None
        ):
            self._current_response_contract = (
                self._matrix_response_planner.plan(
                    self._current_turn_matrix,
                    self._current_evidence_matrix,
                    self._current_authority_plan,
                )
            )

    def _matrix_finalize_deterministic_response(
        self,
        response: CognitiveResponse,
    ) -> CognitiveResponse:
        """Validate a host-generated reply without invoking an LLM retry."""
        if (
            getattr(self, "_current_response_contract", None) is None
            or getattr(self, "_current_evidence_matrix", None) is None
        ):
            return response

        self._refresh_matrix_evidence(response)
        assert self._current_response_contract is not None
        assert self._current_evidence_matrix is not None
        validation = self._matrix_response_validator.validate(
            response,
            self._current_response_contract,
            self._current_evidence_matrix,
        )
        if validation.disposition is ResponseValidationDisposition.PASS:
            self._current_response_validation = validation
            self._record_current_matrix_trace()
            return response

        fallback = self._matrix_response_validator.fallback(
            validation,
            self._current_response_contract,
        )
        self._current_response_validation = ResponseValidation(
            ResponseValidationDisposition.FALLBACK,
            validation.reasons,
        )
        self._record_current_matrix_trace()
        return fallback

    def _matrix_finalize_response(
        self,
        request: CognitiveRequest,
        response: CognitiveResponse,
        *,
        principal: PrincipalContext | None,
    ) -> CognitiveResponse:
        """Apply F after domain-specific finalization and before persistence."""
        if (
            self._current_response_contract is None
            or self._current_evidence_matrix is None
        ):
            return response

        self._refresh_matrix_evidence(response, request)
        assert self._current_response_contract is not None
        assert self._current_evidence_matrix is not None

        validation = self._matrix_response_validator.validate(
            response,
            self._current_response_contract,
            self._current_evidence_matrix,
        )
        self._current_response_validation = validation
        if validation.disposition is ResponseValidationDisposition.PASS:
            self._record_current_matrix_trace()
            return response

        correction = CognitiveMessage(
            role=CognitiveRole.SYSTEM,
            content=(
                "MATRIX RESPONSE CORRECTION: The previous draft is rejected "
                "and must not become conversation history. Rewrite once using "
                "only supplied evidence and host authority. Do not claim an "
                "action executed without authority and an execution receipt. "
                "Do not invent current measurements or current weather. "
                "Validation reasons: "
                + ", ".join(validation.reasons)
            ),
        )
        retry_request = CognitiveRequest(
            messages=(correction, *request.messages),
            tools=(),
            allow_tools=False,
            route_hint="verify",
        )
        if principal is None:
            retry = self._runtime.respond(
                retry_request,
                filesystem_results=(),
                context_plan=self._current_context_plan,
                privacy_plan=self._current_privacy_plan,
                contextual_influence=self._current_contextual_influence,
            )
        else:
            retry = self._runtime.respond(
                retry_request,
                filesystem_results=(),
                principal=principal,
                context_plan=self._current_context_plan,
                privacy_plan=self._current_privacy_plan,
                contextual_influence=self._current_contextual_influence,
            )

        self._capture_cognition_execution()

        retry = self._finalize_response(
            retry_request,
            retry,
            principal=principal,
        )
        if response.evidence_refs and not retry.evidence_refs:
            retry = CognitiveResponse(
                content=retry.content,
                tool_calls=retry.tool_calls,
                evidence_refs=response.evidence_refs,
            )

        self._refresh_matrix_evidence(retry, retry_request)
        assert self._current_response_contract is not None
        assert self._current_evidence_matrix is not None
        retry_validation = self._matrix_response_validator.validate(
            retry,
            self._current_response_contract,
            self._current_evidence_matrix,
        )
        if retry_validation.disposition is ResponseValidationDisposition.PASS:
            self._current_response_validation = retry_validation
            self._record_current_matrix_trace()
            return retry

        fallback = self._matrix_response_validator.fallback(
            retry_validation,
            self._current_response_contract,
        )
        self._current_response_validation = ResponseValidation(
            ResponseValidationDisposition.FALLBACK,
            retry_validation.reasons,
        )
        self._record_current_matrix_trace()
        return fallback

    def latest_matrix_trace(self) -> MatrixTrace | None:
        """Return the most recent matrix decision for the active session."""
        if self._matrix_trace_store is None:
            return None
        session_id = None if self._session is None else self._session.id
        return self._matrix_trace_store.latest(session_id=session_id)

    @property
    def last_matrix_error(self) -> str | None:
        return self._last_matrix_error
