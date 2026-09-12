from dataclasses import dataclass
from enum import Enum


class CognitiveRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class CognitiveMessage:
    role: CognitiveRole
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, CognitiveRole):
            raise ValueError(
                "CognitiveMessage role must be a CognitiveRole."
            )


@dataclass(frozen=True)
class CognitiveRequest:
    messages: tuple[CognitiveMessage, ...]


@dataclass(frozen=True)
class CognitiveResponse:
    content: str