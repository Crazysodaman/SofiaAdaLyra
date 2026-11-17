"""Per-Core conversation context assembly with explicit isolation checks."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Iterable
from uuid import UUID

from .identity import ConversationKey, CoreIdentity
from .contract import PromptMessage


class ContextIsolationError(PermissionError):
    """Raised when a caller attempts to reuse another writer's context."""


@dataclass(frozen=True, slots=True)
class ConversationSnapshot:
    key: ConversationKey
    messages: tuple[PromptMessage, ...]


class ConversationContextStore:
    """In-memory per-conversation history; key includes Core and generation.

    The store is intentionally not a memory owner.  It holds only the message
    snapshot a caller assembles before submission.  A durable Core memory
    owner must supply those messages explicitly; this adapter never reads or
    merges another Core's memory.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._histories: dict[ConversationKey, list[PromptMessage]] = {}
        self._latest_generation: dict[tuple[UUID, str], int] = {}

    def _check_generation(self, core: CoreIdentity) -> None:
        identity = (core.core_id, core.platform_id)
        latest = self._latest_generation.get(identity)
        if latest is not None and core.generation < latest:
            raise ContextIsolationError(
                "a stale Core generation cannot read or append conversation context"
            )
        self._latest_generation[identity] = max(core.generation, latest or 0)

    def append(
        self, core: CoreIdentity, conversation_id: str,
        messages: Iterable[PromptMessage],
    ) -> ConversationSnapshot:
        if not isinstance(core, CoreIdentity):
            raise TypeError("core must be CoreIdentity")
        prepared = tuple(messages)
        if any(not isinstance(message, PromptMessage) for message in prepared):
            raise TypeError("messages must contain PromptMessage values")
        _ = core.conversation_key(conversation_id)
        with self._lock:
            self._check_generation(core)
            key = core.conversation_key(conversation_id)
            history = self._histories.setdefault(key, [])
            history.extend(prepared)
            return ConversationSnapshot(key, tuple(history))

    def snapshot(
        self, core: CoreIdentity, conversation_id: str,
    ) -> ConversationSnapshot:
        if not isinstance(core, CoreIdentity):
            raise TypeError("core must be CoreIdentity")
        with self._lock:
            self._check_generation(core)
            key = core.conversation_key(conversation_id)
            return ConversationSnapshot(key, tuple(self._histories.get(key, ())))

    def replace(
        self, core: CoreIdentity, conversation_id: str,
        messages: Iterable[PromptMessage],
    ) -> ConversationSnapshot:
        """Replace one conversation's snapshot without touching any other."""
        if not isinstance(core, CoreIdentity):
            raise TypeError("core must be CoreIdentity")
        prepared = tuple(messages)
        if any(not isinstance(message, PromptMessage) for message in prepared):
            raise TypeError("messages must contain PromptMessage values")
        with self._lock:
            self._check_generation(core)
            key = core.conversation_key(conversation_id)
            self._histories[key] = list(prepared)
            return ConversationSnapshot(key, prepared)

    def clear(self, core: CoreIdentity, conversation_id: str) -> None:
        if not isinstance(core, CoreIdentity):
            raise TypeError("core must be CoreIdentity")
        with self._lock:
            self._histories.pop(core.conversation_key(conversation_id), None)

    def conversations(self, core: CoreIdentity) -> tuple[ConversationKey, ...]:
        if not isinstance(core, CoreIdentity):
            raise TypeError("core must be CoreIdentity")
        with self._lock:
            return tuple(
                key for key in self._histories
                if key.core_id == core.core_id
                and key.platform_id == core.platform_id
                and key.generation == core.generation
            )

    def copy_for(self, core: CoreIdentity, conversation_id: str) -> ConversationSnapshot:
        """Return an independent tuple copy; later appends cannot mutate it."""
        return self.snapshot(core, conversation_id)
