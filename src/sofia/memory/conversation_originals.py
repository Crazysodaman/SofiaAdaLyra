"""Bridge persisted conversation originals into PKG-MEM retrieval.

This adapter is deliberately read-only. Authorization is established by the
caller before constructing a request; this module never searches other
sessions and never promotes conversation text into long-term memory.
"""
from __future__ import annotations

from dataclasses import dataclass

from sofia.conversation.store import ConversationStore
from sofia.memory.retrieval_projection import RetrievalProjection, project_originals


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
