from datetime import datetime, timezone
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

    def respond(
        self,
        content: str,
        *,
        principal: PrincipalContext | None = None,
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

        principal = self._bind_principal(principal)
        content = content.strip()

        if not content:
            raise ValueError(
                "ConversationService content must not be empty."
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

        if principal is None:
            response = self._runtime.respond(
                request,
                filesystem_results=filesystem_results,
            )
        else:
            response = self._runtime.respond(
                request,
                filesystem_results=filesystem_results,
                principal=principal,
            )

        # Reject unsupported interaction claims before they become history.
        response = self._finalize_response(
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

        cognitive_messages = tuple(
            self._to_cognitive_message(message)
            for message in _conversation_cognitive_window(messages)
        )

        latest_user = next(
            (
                message.content
                for message in reversed(messages)
                if message.role is ConversationRole.USER
            ),
            None,
        )

        return CognitiveRequest(
            messages=cognitive_messages,
            allow_tools=_conversation_tools_relevant(latest_user),
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