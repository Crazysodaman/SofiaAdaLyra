from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ConversationRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ConversationSession:
    id: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError(
                "ConversationSession id must not be empty."
            )

        if not isinstance(self.created_at, datetime):
            raise TypeError(
                "ConversationSession created_at must be a datetime."
            )

        if not isinstance(self.updated_at, datetime):
            raise TypeError(
                "ConversationSession updated_at must be a datetime."
            )


@dataclass(frozen=True)
class ConversationMessage:
    id: str
    session_id: str
    role: ConversationRole
    content: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError(
                "ConversationMessage id must not be empty."
            )

        if not self.session_id:
            raise ValueError(
                "ConversationMessage session_id must not be empty."
            )

        if not isinstance(self.role, ConversationRole):
            raise ValueError(
                "ConversationMessage role must be a ConversationRole."
            )

        if not self.content:
            raise ValueError(
                "ConversationMessage content must not be empty."
            )

        if not isinstance(self.created_at, datetime):
            raise TypeError(
                "ConversationMessage created_at must be a datetime."
            )