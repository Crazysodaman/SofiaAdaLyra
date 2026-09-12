from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MemoryRecord:
    """
    Immutable representation of a persistent memory.
    """

    id: str
    content: str
    created_at: datetime