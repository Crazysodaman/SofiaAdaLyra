"""Application integration for evidence-linked emotional expression."""
from __future__ import annotations

from datetime import datetime, timezone

from sofia.application.conversation_service import ConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.personality.emotion import EmotionalJournal
from sofia.runtime.runtime import SofiaRuntime


class EmotionalConversationService(ConversationService):
    """Keep emotional events outside canonical identity and operational authority.

    The journal is recorded only after the user turn is durably saved by the
    base service. The LLM receives a bounded read-only projection, never
    direct write access to the journal or any action permission.
    """

    def __init__(self, runtime: SofiaRuntime, conversation_store: ConversationStore) -> None:
        super().__init__(runtime=runtime, conversation_store=conversation_store)
        self._emotional_journal: EmotionalJournal | None = None

    def open(self) -> None:
        super().open()
        try:
            self._emotional_journal = EmotionalJournal(self._runtime.configuration.state_path)
        except Exception:
            super().close()
            raise

    @property
    def emotional_journal(self) -> EmotionalJournal:
        if self._emotional_journal is None:
            raise RuntimeError("Emotional journal is not open.")
        return self._emotional_journal

    def close(self) -> None:
        super().close()
        self._emotional_journal = None

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
        context = self.emotional_journal.prompt_context(now=datetime.now(timezone.utc))
        if context is None:
            return request
        return CognitiveRequest(
            messages=(CognitiveMessage(role=CognitiveRole.SYSTEM, content=context), *request.messages),
            tools=request.tools,
        )
