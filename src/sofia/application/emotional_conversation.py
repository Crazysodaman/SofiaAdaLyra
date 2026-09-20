"""Application integration for evidence-linked emotional expression and reflection."""
from __future__ import annotations

from datetime import datetime, timezone

from sofia.application.conversation_service import ConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.reflection import ReflectionJournal
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

    def open(self) -> None:
        super().open()
        try:
            state_path = self._runtime.configuration.state_path
            self._emotional_journal = EmotionalJournal(state_path)
            self._reflection_journal = ReflectionJournal(state_path)
        except Exception:
            super().close()
            self._emotional_journal = None
            self._reflection_journal = None
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

    def close(self) -> None:
        super().close()
        self._emotional_journal = None
        self._reflection_journal = None

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
        if not projections:
            return request
        return CognitiveRequest(
            messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                      content="\n\n".join(projections)), *request.messages),
            tools=request.tools,
        )
