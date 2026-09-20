"""Application integration for evidence-linked emotional expression and reflection."""
from __future__ import annotations

from datetime import datetime, timezone

from sofia.application.conversation_service import ConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.personality.clarification import ClarificationJournal
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.observation_bridge import record_workspace_observation
from sofia.personality.reflection import ReflectionJournal
from sofia.personality.thought_agent import ReflectionOutcome, ThoughtAgent
from sofia.runtime.runtime import SofiaRuntime


class EmotionalConversationService(ConversationService):
    """Keep emotional events and reflections outside identity and authority.

    The emotional journal is recorded only after the user turn is durably
    saved by the base service. Periodic reflections run only when this
    service processes a request, not continuously while it is offline.
    The model receives bounded, read-only data, not journal write access.
    """

    def __init__(self, runtime: SofiaRuntime, conversation_store: ConversationStore) -> None:
        super().__init__(runtime=runtime, conversation_store=conversation_store)
        self._emotional_journal: EmotionalJournal | None = None
        self._reflection_journal: ReflectionJournal | None = None
        self._clarification_journal: ClarificationJournal | None = None

    def open(self) -> None:
        super().open()
        try:
            state_path = self._runtime.configuration.state_path
            self._emotional_journal = EmotionalJournal(state_path)
            self._reflection_journal = ReflectionJournal(state_path)
            self._clarification_journal = ClarificationJournal(state_path)
            changes = getattr(self._runtime, "workspace_changes", None)
            if self._runtime.personality is not None and changes is not None:
                record_workspace_observation(
                    event=changes, emotions=self._emotional_journal,
                    reflections=self._reflection_journal,
                    ignored_paths=(state_path,),
                )
        except Exception:
            super().close()
            self._emotional_journal = None
            self._reflection_journal = None
            self._clarification_journal = None
            raise

    @property
    def emotional_journal(self) -> EmotionalJournal:
        if self._emotional_journal is None:
            raise RuntimeError("Emotional journal is not open.")
        return self._emotional_journal

    @property
    def reflection_journal(self) -> ReflectionJournal:
        if self._reflection_journal is None:
            raise RuntimeError("Reflection journal is not open.")
        return self._reflection_journal

    @property
    def clarification_journal(self) -> ClarificationJournal:
        if self._clarification_journal is None:
            raise RuntimeError("Clarification journal is not open.")
        return self._clarification_journal

    def clarify_event(self, *, event_id: str, message_id: str) -> None:
        """Explicitly link one saved user turn to one selected event.

        An authorized application UI must resolve and confirm the event ID.
        Neither the LLM nor this method guesses a target from arbitrary text,
        infers a new emotion, or rewrites the original reaction.
        """
        if self._runtime.personality is None:
            raise RuntimeError("No personality profile is active.")
        if self._session is None:
            raise RuntimeError("A conversation session must be active.")
        matching = tuple(message for message in self.messages() if message.id == message_id)
        if len(matching) != 1 or matching[0].role is not ConversationRole.USER:
            raise ValueError("Clarification must reference a saved user message in this session.")
        message = matching[0]
        self.clarification_journal.record(
            event_id=event_id, message_id=message.id,
            content=message.content, created_at=message.created_at,
        )

    def reflect_on_event(self, *, event_id: str) -> ReflectionOutcome:
        """Generate one optional model thought from explicitly selected evidence.

        A trusted application caller selects the event. This method does not
        run by itself, interpret ambiguous user language, or send messages.
        The cognitive system supplies canonical grounding but gains no tools
        or new operational authority from the reflection request.
        """
        if self._runtime.personality is None:
            raise RuntimeError("No personality profile is active.")
        if self._session is None:
            raise RuntimeError("A conversation session must be active.")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("A recorded event ID is required.")
        now = datetime.now(timezone.utc)
        matching = tuple(
            event for event in self.emotional_journal.recent(
                now=now, days=366, limit=50,
            ) if event.event_id == event_id
        )
        if len(matching) != 1:
            raise KeyError("No matching recent emotional event was recorded.")
        agent = ThoughtAgent(
            generate=self._runtime.respond,
            reflections=self.reflection_journal,
        )
        return agent.reflect(event=matching[0], now=now)

    def close(self) -> None:
        super().close()
        self._emotional_journal = None
        self._reflection_journal = None
        self._clarification_journal = None

    def _build_request(self) -> CognitiveRequest:
        request = super()._build_request()
        if self._runtime.personality is None:
            return request
        messages = self.messages()
        if messages and messages[-1].role is ConversationRole.USER:
            user = messages[-1]
            self.emotional_journal.record_user_cue(
                message_id=user.id, content=user.content, occurred_at=user.created_at,
            )
        now = datetime.now(timezone.utc)
        projections = []
        emotional_context = self.emotional_journal.prompt_context(now=now)
        if emotional_context is not None:
            projections.append(emotional_context)
        # The optional guard preserves compatibility with a test-only
        # uninitialized service; a normally opened service always has this.
        reflections = getattr(self, "_reflection_journal", None)
        if reflections is not None:
            reflections.reflect_due(now=now)
            reflection_context = reflections.prompt_context()
            if reflection_context is not None:
                projections.append(reflection_context)
        clarifications = getattr(self, "_clarification_journal", None)
        if clarifications is not None:
            clarification_context = clarifications.prompt_context(now=now)
            if clarification_context is not None:
                projections.append(clarification_context)
        if not projections:
            return request
        return CognitiveRequest(
            messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                      content="\n\n".join(projections)), *request.messages),
            tools=request.tools,
        )
