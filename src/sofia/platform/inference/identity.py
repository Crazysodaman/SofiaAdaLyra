"""Neutral Core and conversation addressing for shared inference.

``CoreIdentity`` mirrors the future shared social contract:
``CoreIdentity(core_id UUID, platform_id, generation, display_name)``.  The
generation is part of the conversation key so a restarted Core cannot inherit
another writer's context accidentally.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from uuid import UUID

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_CONVERSATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _text(value: str, label: str, *, maximum: int) -> str:
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > maximum
        or _CONTROL.search(value) is not None
    ):
        raise ValueError(f"{label} must be bounded printable text")
    return value


@dataclass(frozen=True, slots=True)
class CoreIdentity:
    """One independently acting Core identity within the shared host."""

    core_id: UUID
    platform_id: str
    generation: int
    display_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.core_id, UUID):
            raise TypeError("core_id must be a UUID")
        if (
            type(self.platform_id) is not str
            or _IDENTIFIER.fullmatch(self.platform_id) is None
        ):
            raise ValueError("platform_id must be a bounded identifier")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be a positive integer")
        _text(self.display_name, "display_name", maximum=120)

    def conversation_key(self, conversation_id: str) -> "ConversationKey":
        return ConversationKey(
            self.core_id, self.platform_id, self.generation, conversation_id,
        )


@dataclass(frozen=True, slots=True)
class ConversationKey:
    """Exact (Core, platform, generation, conversation) address."""

    core_id: UUID
    platform_id: str
    generation: int
    conversation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.core_id, UUID):
            raise TypeError("core_id must be a UUID")
        if (
            type(self.platform_id) is not str
            or _IDENTIFIER.fullmatch(self.platform_id) is None
        ):
            raise ValueError("platform_id must be a bounded identifier")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be a positive integer")
        if (
            type(self.conversation_id) is not str
            or _CONVERSATION.fullmatch(self.conversation_id) is None
        ):
            raise ValueError("conversation_id must be a bounded identifier")

    @property
    def core_ref(self) -> str:
        return str(self.core_id)
