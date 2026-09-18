from datetime import datetime, timezone
from uuid import uuid4

from sofia.authorization.evaluator import (
    FilesystemAuthorizationEvaluator,
)
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

    def respond(
        self,
        content: str,
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

        response = self._runtime.respond(
            request,
            filesystem_results=filesystem_results,
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
            for message in messages
        )

        return CognitiveRequest(
            messages=cognitive_messages,
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