from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class HistoricalConversationEvidence:
    """One bounded snippet from imported historical conversation evidence."""

    source_digest: str
    conversation_id: str
    message_id: str
    role: str
    content: str
    title: str | None = None
    source_created_at: datetime | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.source_digest, "source_digest"),
            (self.conversation_id, "conversation_id"),
            (self.message_id, "message_id"),
            (self.role, "role"),
            (self.content, "content"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if self.role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        if self.title is not None and (
            not isinstance(self.title, str) or not self.title.strip()
        ):
            raise ValueError("title must be nonempty or None")
        if self.source_created_at is not None and (
            not isinstance(self.source_created_at, datetime)
            or self.source_created_at.tzinfo is None
            or self.source_created_at.utcoffset() is None
        ):
            raise ValueError("source_created_at must be timezone-aware or None")
