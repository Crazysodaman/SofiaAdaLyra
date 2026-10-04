"""Read-only, session-scoped exact conversation originals.

This module never reads a database, promotes a memory, or authenticates users.
The caller must establish an authorized session before passing its originals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sofia.conversation.model import ConversationMessage
from sofia.conversation.store import ConversationStore


@dataclass(frozen=True, slots=True)
class SourceMessage:
    """Unaltered original with its stable provenance and an explicit position."""

    message_id: str
    session_id: str
    role: str
    content: str
    created_at: datetime
    position: int


@dataclass(frozen=True, slots=True)
class RetrievalProjection:
    selected: tuple[SourceMessage, ...]
    omitted_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]
    budget_characters: int


def project_originals(
    *,
    session_id: str,
    originals: Iterable[ConversationMessage],
    requested_ids: Iterable[str],
    budget_characters: int,
) -> RetrievalProjection:
    """Select verified originals without merging sessions or synthesizing text.

    Requested IDs retain request order; each ID is included once. Entries
    exceeding the remaining character budget are omitted, not truncated.
    ``missing_ids`` includes IDs outside the authorized session (without
    revealing whether such IDs exist elsewhere). No fallback or broad search.
    """
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id must be a nonempty string")
    if type(budget_characters) is not int or budget_characters < 0:
        raise ValueError("budget_characters must be a nonnegative integer")

    by_id: dict[str, SourceMessage] = {}
    for position, message in enumerate(originals):
        if not isinstance(message, ConversationMessage):
            raise TypeError("originals must contain ConversationMessage instances")
        if message.session_id != session_id:
            continue
        if message.id in by_id:
            raise ValueError("duplicate original message ID in session")
        if message.created_at.tzinfo is None or message.created_at.utcoffset() is None:
            raise ValueError("original timestamps must have a timezone")
        by_id[message.id] = SourceMessage(
            message_id=message.id,
            session_id=message.session_id,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at.astimezone(timezone.utc),
            position=position,
        )

    selected: list[SourceMessage] = []
    omitted: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()
    remaining = budget_characters
    for message_id in requested_ids:
        if not isinstance(message_id, str) or not message_id.strip():
            raise ValueError("requested message IDs must be nonempty strings")
        if message_id in seen:
            continue
        seen.add(message_id)
        original = by_id.get(message_id)
        if original is None:
            missing.append(message_id)
        elif len(original.content) > remaining:
            omitted.append(message_id)
        else:
            selected.append(original)
            remaining -= len(original.content)
    return RetrievalProjection(tuple(selected), tuple(omitted), tuple(missing), budget_characters)


@dataclass(frozen=True, slots=True)
class OriginalRetrievalRequest:
    """A bounded request for originals inside one already-authorized session."""

    session_id: str
    message_ids: tuple[str, ...]
    budget_characters: int

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("session_id must be a nonempty string")
        if not isinstance(self.message_ids, tuple):
            raise TypeError("message_ids must be a tuple")
        if any(not isinstance(item, str) or not item.strip() for item in self.message_ids):
            raise ValueError("message_ids must contain nonempty strings")
        if type(self.budget_characters) is not int or self.budget_characters < 0:
            raise ValueError("budget_characters must be a nonnegative integer")


class ConversationOriginalRetriever:
    """Read exact originals from one persisted conversation session only."""

    def __init__(self, store: ConversationStore) -> None:
        if not isinstance(store, ConversationStore):
            raise TypeError("store must be a ConversationStore")
        self._store = store

    def retrieve(self, request: OriginalRetrievalRequest) -> RetrievalProjection:
        if not isinstance(request, OriginalRetrievalRequest):
            raise TypeError("request must be an OriginalRetrievalRequest")

        # Fail closed instead of treating an unknown session as an empty memory.
        if self._store.get_session(request.session_id) is None:
            raise LookupError("authorized conversation session does not exist")

        originals = self._store.list_messages(request.session_id)
        return project_originals(
            session_id=request.session_id,
            originals=originals,
            requested_ids=request.message_ids,
            budget_characters=request.budget_characters,
        )
