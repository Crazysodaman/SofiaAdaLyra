"""Text-first PKG-UI adapter over Sofía's canonical conversation service.

The adapter does not create a second runtime, memory, personality, or session
model. It projects persisted conversation messages for a client and keeps
unsent draft state separate from cognition.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.ui.drafts import UIDraft, UIDraftStore


class ConversationPort(Protocol):
    @property
    def session_id(self) -> str | None: ...

    def messages(self) -> tuple[ConversationMessage, ...]: ...

    def respond(self, content: str): ...


@dataclass(frozen=True, slots=True)
class UITextMessage:
    message_id: str
    session_id: str
    actor: str
    content: str
    created_at: datetime


class UITextClient:
    """One local text client view over an already-started conversation."""

    def __init__(
        self,
        *,
        conversation: ConversationPort,
        drafts: UIDraftStore,
        client_id: str,
    ) -> None:
        if not hasattr(conversation, "session_id"):
            raise TypeError("conversation must expose session_id")
        if not callable(getattr(conversation, "messages", None)):
            raise TypeError("conversation must expose messages()")
        if not callable(getattr(conversation, "respond", None)):
            raise TypeError("conversation must expose respond(content)")
        if not isinstance(drafts, UIDraftStore):
            raise TypeError("drafts must be UIDraftStore")
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("client_id must be nonempty")
        self._conversation = conversation
        self._drafts = drafts
        self._client_id = client_id

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def session_id(self) -> str:
        value = self._conversation.session_id
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError("text client requires an active conversation session")
        return value

    def history(self) -> tuple[UITextMessage, ...]:
        result: list[UITextMessage] = []
        for message in self._conversation.messages():
            if not isinstance(message, ConversationMessage):
                raise TypeError("conversation returned a non-ConversationMessage")
            actor = (
                "user"
                if message.role is ConversationRole.USER
                else "sofia"
                if message.role is ConversationRole.ASSISTANT
                else None
            )
            if actor is None:
                raise ValueError("unsupported conversation role")
            result.append(
                UITextMessage(
                    message_id=message.id,
                    session_id=message.session_id,
                    actor=actor,
                    content=message.content,
                    created_at=message.created_at,
                )
            )
        return tuple(result)

    def draft(self) -> UIDraft | None:
        return self._drafts.load(
            client_id=self._client_id,
            session_id=self.session_id,
        )

    def save_draft(self, content: str) -> UIDraft | None:
        return self._drafts.save(
            client_id=self._client_id,
            session_id=self.session_id,
            content=content,
        )

    def clear_draft(self) -> None:
        self._drafts.clear(
            client_id=self._client_id,
            session_id=self.session_id,
        )

    def send(self, content: str | None = None):
        """Send explicit text through the canonical conversation path.

        If content is omitted, the currently persisted draft is sent. Draft
        state is cleared only after the conversation call succeeds.
        """
        if content is None:
            draft = self.draft()
            if draft is None:
                raise ValueError("there is no saved draft to send")
            content = draft.content
        if not isinstance(content, str):
            raise TypeError("content must be a string")
        if not content.strip():
            raise ValueError("content must not be blank")

        response = self._conversation.respond(content)
        self.clear_draft()
        return response
