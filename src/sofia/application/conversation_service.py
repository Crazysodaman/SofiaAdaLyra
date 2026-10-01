from datetime import datetime, timezone
from pathlib import Path
import re
from uuid import uuid4

from sofia.authorization.evaluator import (
    FilesystemAuthorizationEvaluator,
)
from sofia.continuity.model import ContinuityEvent
from sofia.conversation.model import (
    ConversationMessage,
    ConversationRole,
    ConversationSession,
)
from sofia.conversation.store import ConversationStore
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
    MatrixTrace,
    MatrixTraceStore,
    ResponseContract,
    ResponseValidation,
    ResponseValidationDisposition,
    RoutingPlan,
    TurnEnvelope,
    TurnMatrix,
)
from sofia.cognition.matrix.defaults import default_matrix_registry
from sofia.filesystem.orchestrator import (
    FilesystemOrchestrator,
)
from sofia.runtime.runtime import SofiaRuntime
from sofia.social.model import PrincipalContext
from sofia.social.store import SocialSessionStore
from sofia.rel.store import RelationshipStore


_TOOL_TARGET_RE = re.compile(
    r"\b(?:file|folder|directory|code|codebase|repository|repo|github|"
    r"issue|pull\s+request|process|cpu|gpu|memory|ram|disk|storage|"
    r"system|computer|machine|host|network|services?|hardware|sensor|sensors|vm|"
    r"virtual\s+machine|container|docker|ollama|sqlite|database|"
    r"home\s+assistant|portainer|jmri|discord|fleet|remote|telemetry|"
    r"package|deployment|server)\b",
    re.IGNORECASE,
)
_TOOL_ACTION_RE = re.compile(
    r"\b(?:inspect|check|show|list|read|search|find|query|get|status|"
    r"state|running|run|start|stop|restart|reboot|update|upgrade|deploy|"
    r"install|remove|delete|create|write|edit|change|control)\b",
    re.IGNORECASE,
)
_SOFIA_MATRIX_TERM_RE = re.compile(
    r"\b(?:matrix|matrixes|matrices|matrixs)\b",
    re.IGNORECASE,
)

_TOOL_CONTROL_RE = re.compile(
    r"\b(?:start|stop|restart|reboot|update|upgrade|deploy|install|"
    r"remove|delete|write|edit)\b",
    re.IGNORECASE,
)
_TOOL_QUESTION_RE = re.compile(
    r"^\s*(?:what|which|how|is|are|do|does|can|could|would|will)\b",
    re.IGNORECASE,
)
_RUNNING_APP_RE = re.compile(
    r"\b(?:is|are)\s+[A-Za-z0-9_.-]+\s+running\b|"
    r"\bwhat(?:\'s|\s+is)\s+running\b",
    re.IGNORECASE,
)


def _conversation_tools_relevant(content: str | None) -> bool:
    """Expose operational tools only when the current user turn needs them.

    Ordinary social/environment/avatar conversation stays tool-free. This keeps
    provider-side response-quality repair available and avoids sending the full
    operational toolbox/context on turns such as hru or timezone follow-ups.
    Host authorization still independently governs every exposed capability.
    """
    if content is None:
        return False
    if not isinstance(content, str):
        raise TypeError("conversation tool relevance content must be a string or None")
    text = content.strip()
    if not text:
        return False
    if _RUNNING_APP_RE.search(text):
        return True
    if _TOOL_TARGET_RE.search(text) is None:
        return False
    return (
        _TOOL_ACTION_RE.search(text) is not None
        or _TOOL_CONTROL_RE.search(text) is not None
        or _TOOL_QUESTION_RE.search(text) is not None
    )


# The durable store keeps full history, but a new unrelated question must not
# inherit previous assistant prose as if it were relevant evidence.
_STANDALONE_TURN_RE = re.compile(
    r"^\s*(?:so\s+)?(?:"
    r"hru|how\s+(?:are|r)\s+(?:you|u)|how(?:'|’)re\s+you|"
    r"how(?:'|’)?s\s+(?:the\s+)?network|how\s+is\s+(?:the\s+)?network|"
    r"what(?:'|’)?s\s+(?:the\s+)?network\s+status|"
    r"what\s+(?:llm|model)\s+(?:am\s+i|are\s+you|is\s+sofia)\s+running"
    r"(?:\s+(?:right\s+now|rn|currently))?|"
    r"what\s+(?:llm|model)\s+is\s+running"
    r"(?:\s+(?:right\s+now|rn|currently))?"
    r")\s*[?!.]*\s*$",
    re.IGNORECASE,
)
_MAX_COGNITIVE_TRANSCRIPT_MESSAGES = 12


def _conversation_cognitive_window(
    messages: tuple[ConversationMessage, ...],
) -> tuple[ConversationMessage, ...]:
    """Keep persisted history intact while bounding prompt-visible history.

    Standalone social/operational self-report questions start fresh. Follow-ups
    keep a short recent transcript and can access relevant canonical memory.
    """
    if not messages:
        return ()
    current = messages[-1]
    if (
        current.role is ConversationRole.USER
        and _STANDALONE_TURN_RE.fullmatch(current.content)
    ):
        return (current,)
    return messages[-_MAX_COGNITIVE_TRANSCRIPT_MESSAGES:]


def _matrix_context_window(
    messages: tuple[ConversationMessage, ...],
    plan: ContextPlan,
) -> tuple[ConversationMessage, ...]:
    """Apply the matrix history policy to provider-visible transcript only."""
    if not isinstance(plan, ContextPlan):
        raise TypeError("plan must be ContextPlan")
    if not messages:
        return ()
    return messages[-plan.max_history_messages:]


class ConversationService:
    """
    Application-level conversation boundary.

    Coordinates conversation persistence, filesystem request
    orchestration, authorization, and Sofía's runtime.

    Terminal interaction must not know about persistence,
    filesystem capability, authorization, or cognitive request
    construction.
    """

    def __init__(
        self,
        runtime: SofiaRuntime,
        conversation_store: ConversationStore,
    ) -> None:
        if not isinstance(runtime, SofiaRuntime):
            raise TypeError(
                "ConversationService runtime must be a SofiaRuntime."
            )

        if not isinstance(
            conversation_store,
            ConversationStore,
        ):
            raise TypeError(
                "ConversationService conversation_store must be "
                "a ConversationStore."
            )

        self._runtime = runtime
        self._conversation_store = conversation_store
        self._social_store = SocialSessionStore(
            runtime.configuration.state_path
        )
        self._relationship_store = RelationshipStore(
            runtime.configuration.state_path,
            state_plane=runtime.state_plane,
        )
        self._learning_coordinator = None
        self._habit_continuity = None
        self._pre_response_hook = None
        self._filesystem_orchestrator = (
            FilesystemOrchestrator(
                runtime=runtime,
            )
        )
        self._filesystem_authorization_evaluator = (
            FilesystemAuthorizationEvaluator(
                scope=runtime.configuration.filesystem_root,
            )
        )
        self._session: ConversationSession | None = None
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
        self._matrix_trace_store: MatrixTraceStore | None = None
        self._current_matrix_message_id: str | None = None
        self._current_matrix_envelope: TurnEnvelope | None = None
        self._current_turn_matrix: TurnMatrix | None = None
        self._current_context_plan: ContextPlan | None = None
        self._current_evidence_matrix: EvidenceMatrix | None = None
        self._current_authority_plan: AuthorityPlan | None = None
        self._current_response_contract: ResponseContract | None = None
        self._current_response_validation: ResponseValidation | None = None
        self._current_routing_plan: RoutingPlan | None = None
        self._current_cognition_execution: CognitionExecutionTrace | None = None
        self._matrix_execution_baseline_serial = 0
        self._last_matrix_error: str | None = None

    @property
    def session(self) -> ConversationSession | None:
        return self._session

    def set_learning_coordinator(self, coordinator) -> None:
        """Install the application-owned post-persistence learning hook."""
        if coordinator is not None:
            from sofia.application.conversation_learning import (
                ConversationLearningCoordinator,
            )
            if not isinstance(coordinator, ConversationLearningCoordinator):
                raise TypeError(
                    "coordinator must be ConversationLearningCoordinator or None"
                )
        self._learning_coordinator = coordinator

    def set_habit_continuity(self, coordinator) -> None:
        """Install the application-owned HABIT observation coordinator."""
        if coordinator is not None:
            from sofia.habits.continuity import HabitContinuityCoordinator
            if not isinstance(coordinator, HabitContinuityCoordinator):
                raise TypeError(
                    "coordinator must be HabitContinuityCoordinator or None"
                )
        self._habit_continuity = coordinator

    def set_pre_response_hook(self, hook) -> None:
        """Install one application-owned hook that refreshes trusted live state."""
        if hook is not None and not callable(hook):
            raise TypeError("pre-response hook must be callable or None")
        self._pre_response_hook = hook

    @property
    def database_path(self) -> Path:
        """Return the exact durable conversation database file."""
        return self._conversation_store.database_path

    @property
    def session_id(self) -> str | None:
        if self._session is None:
            return None

        return self._session.id

    def open(self) -> None:
        """
        Open the conversation persistence layer.
        """

        self._conversation_store.open()
        # Matrix traces begin as provisional planning evidence and are replaced
        # with the active validation result before normal response persistence.
        self._matrix_trace_store = MatrixTraceStore(
            self._runtime.configuration.state_path
        )

    def start(
        self,
        session_id: str | None = None,
    ) -> ConversationSession:
        """
        Start a conversation.

        When session_id is omitted, create a new conversation.
        When session_id is provided, explicitly resume that
        persisted conversation.
        """

        if self._session is not None:
            raise RuntimeError(
                "ConversationService already has an active session."
            )

        if session_id is None:
            self._session = (
                self._conversation_store.create_session()
            )

            return self._session

        if not isinstance(session_id, str):
            raise TypeError(
                "ConversationService session_id must be a string."
            )

        session_id = session_id.strip()

        if not session_id:
            raise ValueError(
                "ConversationService session_id must not be empty."
            )

        session = self._conversation_store.get_session(
            session_id
        )

        if session is None:
            raise ValueError(
                f"Conversation session does not exist: {session_id}"
            )

        self._session = session

        return self._session

    def deliver_pending_awareness(
        self,
    ) -> CognitiveResponse | None:
        """
        Deliver one pending continuity-awareness event.

        The awareness instruction is represented as a SYSTEM
        cognitive message rather than a fake USER message.

        The pending event is consumed only after the generated
        assistant response has been persisted successfully.
        """

        if self._session is None:
            raise RuntimeError(
                "ConversationService must be started before "
                "delivering awareness."
            )

        event = self._runtime.pending_continuity_event

        if event is None:
            return None

        request = CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.SYSTEM,
                    content=self._build_awareness_instruction(
                        event
                    ),
                ),
            ),
            allow_tools=False,
        )

        response = self._runtime.respond(
            request,
            filesystem_results=(),
        )

        # Proactive awareness has no authenticated user principal.
        response = self._finalize_response(
            request,
            response,
            principal=None,
        )

        assistant_message = ConversationMessage(
            id=str(uuid4()),
            session_id=self._session.id,
            role=ConversationRole.ASSISTANT,
            content=response.content,
            created_at=datetime.now(timezone.utc),
        )

        self._conversation_store.save(assistant_message)

        self._session = (
            self._conversation_store.get_session(
                self._session.id
            )
        )

        if self._session is None:
            raise RuntimeError(
                "ConversationService lost its active session."
            )

        self._runtime.consume_continuity_awareness()

        return response

    @staticmethod
    def _build_awareness_instruction(
        event: ContinuityEvent,
    ) -> str:
        return (
            "Produce a concise user-facing awareness message about "
            "the pending continuity event below.\n\n"
            "Report observed operational evidence only. Do not claim "
            "subjective memory, awareness, experience, intent, "
            "authorship, cause, or significance that is not contained "
            "in the evidence.\n\n"
            "If a previous runtime is present, explain that a previous "
            "runtime was observed before the current runtime. Do not "
            "claim to remember being shut down or being offline.\n\n"
            "If workspace changes are present, summarize related "
            "changes as one coherent event. Do not produce a separate "
            "statement for each changed file.\n\n"
            "The user did not ask a question. This is proactive "
            "operational awareness, so keep the message concise and "
            "natural. Do not end with an offer, question, menu of next steps, "
            "or phrases such as 'let me know', 'ready to dive in', or "
            "'with confidence'. Do not characterize the user relationship "
            "or call them creator, companion, owner, partner, or similar. "
            "Do not speculate that changed test databases, files, or code are "
            "important unless the evidence itself establishes that.\n\n"
            f"Continuity event kind: {event.kind.value}\n"
            f"Evidence status: {event.evidence_status.value}\n"
            f"Restart observed: {event.restart_observed}\n"
            f"Workspace change count: {event.workspace_change_count}"
        )

    def _bind_principal(
        self,
        principal: PrincipalContext | None,
    ) -> PrincipalContext | None:
        if self._session is None:
            raise RuntimeError(
                "ConversationService must be started before binding a principal."
            )
        social_store = getattr(self, "_social_store", None)
        if social_store is None:
            return principal
        bound = social_store.get(self._session.id)
        if principal is None:
            if bound is not None:
                raise PermissionError(
                    "This conversation session is principal-bound; "
                    "authenticated principal context is required."
                )
            return None
        return social_store.bind(
            session_id=self._session.id,
            principal=principal,
        )

    def _after_user_message_saved(
        self,
        *,
        message: ConversationMessage,
        principal: PrincipalContext | None,
    ) -> None:
        """Run all continuity hooks only after the user turn is durable."""
        learning = getattr(self, "_learning_coordinator", None)
        if learning is not None:
            learning.observe_user_message(
                message=message,
                principal=principal,
            )

        habit = getattr(self, "_habit_continuity", None)
        if habit is not None and principal is not None:
            environment = self._runtime.environment_service.snapshot(
                now=message.created_at,
                refresh_providers=False,
            )
            habit.observe_conversation(
                message=message,
                principal=principal,
                environment=environment,
            )

        if principal is not None:
            self._relationship_store.observe(
                principal=principal,
                evidence_ref=message.id,
                occurred_at=message.created_at,
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
        self._current_response_contract = None
        self._current_response_validation = None
        self._current_routing_plan = None
        self._current_cognition_execution = None
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
            context_plan = self._matrix_context_planner.plan(turn)
            evidence_requirements = self._matrix_evidence_planner.plan(
                turn,
                envelope,
            )
            evidence = self._matrix_evidence_resolver.resolve(
                evidence_requirements,
                self._runtime.matrix_evidence_availability(
                    required_keys=tuple(
                        item.key
                        for item in evidence_requirements.requirements
                    )
                ),
            )
            authority_plan = self._matrix_authority_planner.plan(
                envelope,
                turn,
                self._runtime.current_authority(),
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
            )
        else:
            retry = self._runtime.respond(
                retry_request,
                filesystem_results=(),
                principal=principal,
                context_plan=self._current_context_plan,
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

    def respond(
        self,
        content: str,
        *,
        principal: PrincipalContext | None = None,
        channel: str = "conversation",
    ) -> CognitiveResponse:
        """
        Persist a user message, process authorization or any
        filesystem intent, obtain Sofía's response, and persist
        the assistant response.
        """

        if self._session is None:
            raise RuntimeError(
                "ConversationService must be started before responding."
            )

        if not isinstance(content, str):
            raise TypeError(
                "ConversationService content must be a string."
            )

        if principal is not None and not isinstance(principal, PrincipalContext):
            raise TypeError(
                "ConversationService principal must be a PrincipalContext or None."
            )

        if not isinstance(channel, str) or not channel.strip():
            raise ValueError(
                "ConversationService channel must be a nonempty string."
            )
        channel = channel.strip().casefold()

        principal = self._bind_principal(principal)
        content = content.strip()

        if not content:
            raise ValueError(
                "ConversationService content must not be empty."
            )

        pre_response_hook = self._pre_response_hook
        if pre_response_hook is not None:
            pre_response_hook(
                content=content,
                principal=principal,
                channel=channel,
            )

        user_message = ConversationMessage(
            id=str(uuid4()),
            session_id=self._session.id,
            role=ConversationRole.USER,
            content=content,
            created_at=datetime.now(timezone.utc),
        )

        self._conversation_store.save(user_message)
        self._after_user_message_saved(
            message=user_message,
            principal=principal,
        )
        self._record_shadow_matrix(
            message=user_message,
            principal=principal,
            channel=channel,
        )

        authorization = (
            self._filesystem_authorization_evaluator.evaluate(
                content
            )
        )

        if authorization is not None:
            self._runtime.authorize_filesystem(
                authorization
            )
            filesystem_results = ()
        else:
            filesystem_results = (
                self._filesystem_orchestrator.process(
                    content
                )
            )

        request = self._build_request()

        context_plan = (
            self._current_context_plan
            if self._current_matrix_message_id == user_message.id
            else None
        )
        if principal is None:
            response = self._runtime.respond(
                request,
                filesystem_results=filesystem_results,
                context_plan=context_plan,
            )
        else:
            response = self._runtime.respond(
                request,
                filesystem_results=filesystem_results,
                principal=principal,
                context_plan=context_plan,
            )

        self._capture_cognition_execution()

        # Reject unsupported interaction claims before they become history.
        response = self._finalize_response(
            request,
            response,
            principal=principal,
        )
        response = self._matrix_finalize_response(
            request,
            response,
            principal=principal,
        )

        assistant_message = ConversationMessage(
            id=str(uuid4()),
            session_id=self._session.id,
            role=ConversationRole.ASSISTANT,
            content=response.content,
            created_at=datetime.now(timezone.utc),
        )

        self._conversation_store.save(assistant_message)

        self._session = (
            self._conversation_store.get_session(
                self._session.id
            )
        )

        if self._session is None:
            raise RuntimeError(
                "ConversationService lost its active session."
            )

        return response

    def _finalize_response(
        self,
        request: CognitiveRequest,
        response: CognitiveResponse,
        *,
        principal: PrincipalContext | None,
    ) -> CognitiveResponse:
        """Validate/transform model output before it becomes durable history."""
        return response

    def messages(
        self,
    ) -> tuple[ConversationMessage, ...]:
        """
        Return all persisted messages for the active session.
        """

        if self._session is None:
            raise RuntimeError(
                "ConversationService must be started before reading messages."
            )

        return self._conversation_store.list_messages(
            self._session.id
        )

    def close(self) -> None:
        """
        Close the conversation service and its persistence layer.

        The persisted conversation remains available for explicit
        resumption after restart, but no active in-memory session
        remains attached to the closed service.
        """

        self._session = None
        self._conversation_store.close()

    def _build_request(self) -> CognitiveRequest:
        messages = self._conversation_store.list_messages(
            self._session.id
        )

        current_user = next(
            (
                message
                for message in reversed(messages)
                if message.role is ConversationRole.USER
            ),
            None,
        )
        context_plan = (
            self._current_context_plan
            if (
                current_user is not None
                and current_user.id == self._current_matrix_message_id
            )
            else None
        )
        visible_messages = (
            _matrix_context_window(messages, context_plan)
            if context_plan is not None
            else _conversation_cognitive_window(messages)
        )
        cognitive_messages = tuple(
            self._to_cognitive_message(message)
            for message in visible_messages
        )

        latest_user = next(
            (
                message.content
                for message in reversed(messages)
                if message.role is ConversationRole.USER
            ),
            None,
        )

        if (
            context_plan is not None
            and context_plan.history_policy is HistoryPolicy.LAST_TURN
        ):
            cognitive_messages = (
                CognitiveMessage(
                    role=CognitiveRole.SYSTEM,
                    content=(
                        "TRUSTED FOLLOW-UP SCOPE\n"
                        "The current user turn is a short follow-up. Answer "
                        "the immediately preceding user/assistant exchange. "
                        "Do not reinterpret it as a new unrelated topic and "
                        "do not pivot into Sofía architecture, operations, "
                        "diagnostics, wardrobe, or other domains unless that "
                        "immediately preceding exchange was already about "
                        "that domain."
                    ),
                ),
                *cognitive_messages,
            )

        if (
            latest_user
            and _SOFIA_MATRIX_TERM_RE.search(latest_user)
            and self._current_turn_matrix is not None
            and self._current_turn_matrix.relevance_for(
                MatrixDomain.COGNITION
            ) is not MatrixRelevance.NONE
        ):
            cognitive_messages = (
                CognitiveMessage(
                    role=CognitiveRole.SYSTEM,
                    content=(
                        "TRUSTED SOFÍA PROJECT TERM CONTEXT\n"
                        "In this Sofía codebase, an unqualified reference to "
                        "'matrix', 'matrixs', 'matrixes', or 'matrices' in a "
                        "project/self-system discussion refers to Sofía's "
                        "message/domain/context/evidence/authority/response/"
                        "routing matrix architecture, not a mathematical or "
                        "data matrix, unless the user explicitly asks for math, "
                        "NumPy, linear algebra, rows/columns, or tabular data. "
                        "Do not invent implementation status that is not "
                        "present in trusted context."
                    ),
                ),
                *cognitive_messages,
            )

        allow_tools = _conversation_tools_relevant(latest_user)
        if (
            self._current_turn_matrix is not None
            and self._current_turn_matrix.intent is MatrixIntent.ACTION_REQUEST
            and self._current_authority_plan is not None
            and self._current_authority_plan.decision
            in {
                AuthorityDecision.REQUIRES_APPROVAL,
                AuthorityDecision.DENIED,
                AuthorityDecision.CLARIFY,
            }
        ):
            allow_tools = False

        route_hint = None
        if (
            self._current_routing_plan is not None
            and self._current_routing_plan.route is not MatrixRoute.AUTO
        ):
            route_hint = self._current_routing_plan.route.value

        return CognitiveRequest(
            messages=cognitive_messages,
            allow_tools=allow_tools,
            route_hint=route_hint,
        )

    @staticmethod
    def _to_cognitive_message(
        message: ConversationMessage,
    ) -> CognitiveMessage:
        if message.role is ConversationRole.USER:
            role = CognitiveRole.USER
        elif message.role is ConversationRole.ASSISTANT:
            role = CognitiveRole.ASSISTANT
        else:
            raise ValueError(
                f"Unsupported conversation role: {message.role}"
            )

        return CognitiveMessage(
            role=role,
            content=message.content,
        )