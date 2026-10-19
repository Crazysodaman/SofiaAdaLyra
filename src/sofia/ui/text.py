"""Text-first PKG-UI adapter over Sofía's canonical conversation service.

The adapter does not create a second runtime, memory, personality, or session
model. It projects persisted conversation messages for a client and keeps
unsent draft state separate from cognition.
"""
from __future__ import annotations

from dataclasses import dataclass
import inspect
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.ui.drafts import UIDraft, UIDraftStore
from sofia.social.model import PrincipalContext


class ConversationPort(Protocol):
    @property
    def session_id(self) -> str | None: ...

    def messages(self) -> tuple[ConversationMessage, ...]: ...

    def respond(
        self,
        content: str,
        *,
        principal: PrincipalContext | None = None,
        channel: str = "conversation",
        source_event_id: str | None = None,
    ): ...


@dataclass(frozen=True, slots=True)
class UITextMessage:
    message_id: str | None
    session_id: str | None
    actor: str
    content: str | None
    created_at: datetime
    canonical_sequence: int | None = None
    turn_position: int | None = None
    redacted: bool = False
    unavailable_reason: str | None = None


class UITextClient:
    """One local text client view over an already-started conversation."""

    def __init__(
        self,
        *,
        conversation: ConversationPort,
        drafts: UIDraftStore,
        client_id: str,
        principal: PrincipalContext | None = None,
        channel: str = "desktop",
    ) -> None:
        try:
            inspect.getattr_static(conversation, "session_id")
        except AttributeError as exc:
            raise TypeError("conversation must expose session_id") from exc
        if not callable(getattr(conversation, "messages", None)):
            raise TypeError("conversation must expose messages()")
        if not callable(getattr(conversation, "respond", None)):
            raise TypeError("conversation must expose respond(content)")
        if not isinstance(drafts, UIDraftStore):
            raise TypeError("drafts must be UIDraftStore")
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("client_id must be nonempty")
        if principal is not None and not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext or None")
        if not isinstance(channel, str) or not channel.strip():
            raise ValueError("channel must be a nonempty string")
        self._conversation = conversation
        self._drafts = drafts
        self._client_id = client_id
        self._principal = principal
        self._channel = channel.strip().casefold()

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
        """Return one bounded page; use ``history_page`` for older Main rows."""
        return self.history_page(limit=100)

    def history_page(
        self, *, before: tuple[int, int] | None = None, limit: int = 100,
    ) -> tuple[UITextMessage, ...]:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("desktop history limit must be 1..200")
        projector = getattr(self._conversation, "main_thread_projection_page", None)
        if self._principal is not None and callable(projector):
            page = projector(
                principal=self._principal, before=before, limit=limit,
            )
            result: list[UITextMessage] = []
            for item in page:
                if item.message is None:
                    result.append(UITextMessage(
                        message_id=None, session_id=None, actor="redacted",
                        content=None, created_at=item.linked_at,
                        canonical_sequence=item.canonical_sequence,
                        turn_position=item.turn_position, redacted=True,
                        unavailable_reason=item.redacted_reason,
                    ))
                else:
                    result.append(self._project_message(
                        item.message,
                        canonical_sequence=item.canonical_sequence,
                        turn_position=item.turn_position,
                    ))
            return tuple(result)
        if before is not None:
            raise ValueError("legacy session history has no canonical cursor")
        result: list[UITextMessage] = []
        source = self._conversation.messages()
        for message in source[-limit:]:
            if not isinstance(message, ConversationMessage):
                raise TypeError("conversation returned a non-ConversationMessage")
            result.append(self._project_message(message))
        return tuple(result)

    @staticmethod
    def _project_message(
        message: ConversationMessage, *,
        canonical_sequence: int | None = None,
        turn_position: int | None = None,
    ) -> UITextMessage:
        actor = (
            "user" if message.role is ConversationRole.USER else
            "sofia" if message.role is ConversationRole.ASSISTANT else None
        )
        if actor is None:
            raise ValueError("unsupported conversation role")
        return UITextMessage(
            message_id=message.id, session_id=message.session_id,
            actor=actor, content=message.content,
            created_at=message.created_at,
            canonical_sequence=canonical_sequence,
            turn_position=turn_position,
        )

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

    def send(self, content: str | None = None, *, request_id: str | None = None):
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
        if request_id is not None and (
            not isinstance(request_id, str) or not request_id.strip()
            or len(request_id) > 160
        ):
            raise ValueError("request_id must be bounded nonempty text")

        responder = self._conversation.respond
        parameters = inspect.signature(responder).parameters
        accepts_kwargs = any(
            item.kind is inspect.Parameter.VAR_KEYWORD
            for item in parameters.values()
        )
        kwargs = {}
        if self._principal is not None:
            if "principal" not in parameters and not accepts_kwargs:
                raise TypeError(
                    "conversation responder does not accept principal context"
                )
            kwargs["principal"] = self._principal
        if "channel" in parameters or accepts_kwargs:
            kwargs["channel"] = self._channel
        if self._principal is not None and (
            "source_event_id" in parameters or accepts_kwargs
        ):
            stable = request_id.strip() if request_id is not None else uuid4().hex
            kwargs["source_event_id"] = f"desktop:{self._client_id}:{stable}"
        if self._principal is not None and (
            "source_device_id" in parameters or accepts_kwargs
        ):
            kwargs["source_device_id"] = self._client_id
        response = responder(content, **kwargs)
        self.clear_draft()
        return response
